"""
HTTP API 测试 MCP Server。

为 API 自动化测试场景提供一组**通用、零依赖**的 HTTP 工具，让外部 / 本地
Agent 能够：发请求、做断言、按 OpenAPI 探索接口、做链式调用。

设计原则
--------

1. **零侵入主平台**：本 MCP 与 ``auto-test-platform`` MCP 并列存在，
   只做"通用 HTTP 调用"，不查 ATP 数据库——查 ATP 走 ``query_apis`` 等
   专用工具。
2. **会话变量自管理**：内置一个轻量 ``SessionStore`` 在进程内保存上下文
   变量（用于链式调用：``$response.body.token`` → 下一次请求的
   ``Authorization`` header）。
3. **断言只产事实，不抛异常**：所有断言工具返回 ``{"passed": bool,
   "actual": ..., "expected": ...}``，让 Agent 拿到结果后自由决定
   下一步（重试 / 写 bug / 终止），不用 except 包裹。

工具清单（10 个）
-----------------

::

    1.  http_request                 通用请求（GET/POST/PUT/DELETE/PATCH）
    2.  http_get / http_post         便捷别名（提升 Agent prompt 可读性）
    3.  load_openapi                 拉取 OpenAPI 文档并缓存
    4.  list_openapi_endpoints       列出已加载文档的所有端点
    5.  request_from_openapi         按 operationId 自动拼参数发请求
    6.  assert_status                断言响应状态码
    7.  assert_json_path             用 JSONPath 取值并断言
    8.  assert_response_time         断言响应时间不超过阈值
    9.  set_session_variable         手动设置会话变量
    10. get_session_variable         读会话变量
    11. clear_session                清空会话变量

启动方式
--------

::

    python -m app.mcp_server.http_api_server                # stdio
    python -m app.mcp_server.http_api_server --transport sse --port 7801

作者: yandc
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from mcp.server.fastmcp import FastMCP


logger = logging.getLogger(__name__)


# ============================================================================
# 会话存储
# ============================================================================

@dataclass
class SessionStore:
    """进程内会话变量存储。"""

    variables: Dict[str, Any] = field(default_factory=dict)
    openapi_specs: Dict[str, dict] = field(default_factory=dict)  # name -> spec
    last_response: Optional[Dict[str, Any]] = None

    def render(self, value: str) -> str:
        """把 ``{{var_name}}`` 占位符替换为变量实际值（仅字符串值）。"""
        if not isinstance(value, str):
            return value

        def _sub(m: re.Match) -> str:
            key = m.group(1).strip()
            v = self.variables.get(key)
            return str(v) if v is not None else m.group(0)

        return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", _sub, value)


_session = SessionStore()


# ============================================================================
# 工具：请求发送 + 响应封装
# ============================================================================

def _send_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
    data: Optional[Any] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """统一请求入口；返回结构化响应字典。"""
    rendered_url = _session.render(url)
    rendered_headers = (
        {k: _session.render(v) for k, v in (headers or {}).items()} or None
    )

    start = time.perf_counter()
    try:
        resp = requests.request(
            method=method.upper(),
            url=rendered_url,
            headers=rendered_headers,
            params=params,
            json=json_body,
            data=data,
            timeout=timeout,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 尽力把响应体解析为 JSON
        try:
            body: Any = resp.json()
        except (ValueError, json.JSONDecodeError):
            body = resp.text

        result: Dict[str, Any] = {
            "ok": True,
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": body,
            "elapsed_ms": round(elapsed_ms, 2),
            "url": resp.url,
            "method": method.upper(),
        }
        _session.last_response = result
        return result
    except requests.RequestException as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "ok": False,
            "error": str(e),
            "elapsed_ms": round(elapsed_ms, 2),
            "url": rendered_url,
            "method": method.upper(),
        }


# ============================================================================
# JSONPath 取值（轻量自实现，避免引入新依赖）
# ============================================================================

def _resolve_path(data: Any, path: str) -> Any:
    """按 ``a.b.0.c`` 风格路径取值；不存在返回 ``None``。

    支持：
    - 点分路径：``user.name``
    - 数组下标：``items.0.id`` 或 ``items[0].id``
    """
    cur: Any = data
    # 把 [n] 转成 .n
    normalized = re.sub(r"\[(\d+)\]", r".\1", path)
    parts = [p for p in normalized.split(".") if p]
    for part in parts:
        if cur is None:
            return None
        if part.isdigit() and isinstance(cur, list):
            idx = int(part)
            cur = cur[idx] if 0 <= idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


# ============================================================================
# MCP Server 工厂
# ============================================================================

def create_http_api_mcp_server(name: str = "http-api-mcp") -> FastMCP:
    """构建 HTTP API 测试 MCP Server。"""
    mcp = FastMCP(name)

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    @mcp.tool(description="健康检查，返回 http-api-mcp 运行状态")
    def ping() -> Dict[str, Any]:
        return {"status": "ok", "server": name}

    # ------------------------------------------------------------------
    # 1. 通用请求
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "发起一次 HTTP 请求并返回结构化响应。"
            "URL / headers 中的 ``{{var_name}}`` 会自动被会话变量替换，"
            "便于链式调用（先登录拿 token，再带 token 发后续请求）。"
        )
    )
    def http_request(
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        data: Optional[Any] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        return _send_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
            data=data,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # 2. GET / POST 便捷别名
    # ------------------------------------------------------------------
    @mcp.tool(description="HTTP GET（http_request 的便捷别名）")
    def http_get(
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        return _send_request("GET", url, headers=headers, params=params, timeout=timeout)

    @mcp.tool(description="HTTP POST（http_request 的便捷别名）")
    def http_post(
        url: str,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        return _send_request(
            "POST", url,
            headers=headers, params=params,
            json_body=json_body,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # 3. OpenAPI 加载
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "拉取 OpenAPI / Swagger 文档（JSON 或 YAML 都支持），缓存到本会话。"
            "后续可用 ``list_openapi_endpoints`` 和 ``request_from_openapi`` 操作。"
        )
    )
    def load_openapi(
        url: str,
        spec_name: str = "default",
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        try:
            resp = requests.get(_session.render(url), timeout=timeout)
            text = resp.text
        except requests.RequestException as e:
            return {"ok": False, "error": str(e)}

        # 尝试解析 JSON；失败再尝试 YAML
        try:
            spec = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml  # PyYAML 已在 requirements
                spec = yaml.safe_load(text)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": f"OpenAPI 解析失败: {e}"}

        _session.openapi_specs[spec_name] = spec
        return {
            "ok": True,
            "spec_name": spec_name,
            "title": (spec.get("info") or {}).get("title", "(unknown)"),
            "version": (spec.get("info") or {}).get("version", "(unknown)"),
            "endpoint_count": sum(
                len(methods) for methods in (spec.get("paths") or {}).values()
            ),
        }

    @mcp.tool(
        description=(
            "列出已加载 OpenAPI 文档的所有端点（method + path + operationId + summary）。"
        )
    )
    def list_openapi_endpoints(spec_name: str = "default") -> Dict[str, Any]:
        spec = _session.openapi_specs.get(spec_name)
        if not spec:
            return {"ok": False, "error": f"未加载 spec: {spec_name}"}

        endpoints: List[Dict[str, Any]] = []
        for path, methods in (spec.get("paths") or {}).items():
            for method, op in methods.items():
                if not isinstance(op, dict):
                    continue
                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "operation_id": op.get("operationId", ""),
                    "summary": op.get("summary", ""),
                    "tags": op.get("tags", []),
                })
        return {"ok": True, "spec_name": spec_name, "endpoints": endpoints}

    # ------------------------------------------------------------------
    # 4. 按 operationId 发请求
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "按 OpenAPI 中的 operationId 自动拼装并发送请求。"
            "Path 参数通过 ``path_params`` 替换（如 ``{user_id}`` -> ``42``），"
            "Query / Body 通过 ``params`` / ``json_body`` 传入。"
        )
    )
    def request_from_openapi(
        operation_id: str,
        spec_name: str = "default",
        path_params: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        spec = _session.openapi_specs.get(spec_name)
        if not spec:
            return {"ok": False, "error": f"未加载 spec: {spec_name}"}

        # 找 operationId
        target_method = ""
        target_path = ""
        for path, methods in (spec.get("paths") or {}).items():
            for method, op in methods.items():
                if not isinstance(op, dict):
                    continue
                if op.get("operationId") == operation_id:
                    target_method = method.upper()
                    target_path = path
                    break
            if target_path:
                break

        if not target_path:
            return {"ok": False, "error": f"未找到 operationId={operation_id}"}

        # 替换 {var} 路径参数
        full_path = target_path
        for k, v in (path_params or {}).items():
            full_path = full_path.replace("{" + k + "}", str(v))

        # 拼 URL
        servers = spec.get("servers") or []
        spec_base = base_url or (servers[0].get("url") if servers else "")
        url = (spec_base.rstrip("/") + full_path) if spec_base else full_path

        return _send_request(
            method=target_method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # 5. 断言：状态码 / JSONPath / 响应时间
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "断言上一次请求或指定响应的状态码。"
            "传入 ``response`` 字典则断言它，否则断言会话最后一次响应。"
        )
    )
    def assert_status(
        expected: int,
        response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        target = response or _session.last_response
        if not target:
            return {"passed": False, "error": "没有可断言的响应"}
        actual = target.get("status_code")
        return {
            "passed": actual == expected,
            "actual": actual,
            "expected": expected,
        }

    @mcp.tool(
        description=(
            "用点分路径从响应 body 取值并断言。"
            "示例：path=``data.user.id`` expected=42。"
            "比较使用 ``==``（数值与字符串比较时不做隐式转换）。"
        )
    )
    def assert_json_path(
        path: str,
        expected: Any,
        response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        target = response or _session.last_response
        if not target:
            return {"passed": False, "error": "没有可断言的响应"}
        body = target.get("body")
        actual = _resolve_path(body, path)
        return {
            "passed": actual == expected,
            "actual": actual,
            "expected": expected,
            "path": path,
        }

    @mcp.tool(
        description=(
            "断言响应时间不超过指定毫秒数。"
            "传入 ``response`` 字典则断言它，否则断言会话最后一次响应。"
        )
    )
    def assert_response_time(
        max_ms: float,
        response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        target = response or _session.last_response
        if not target:
            return {"passed": False, "error": "没有可断言的响应"}
        actual = target.get("elapsed_ms", 0.0)
        return {
            "passed": actual <= max_ms,
            "actual_ms": actual,
            "max_ms": max_ms,
        }

    # ------------------------------------------------------------------
    # 6. 会话变量
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "设置会话变量。可手动给 value，也可用 ``from_path`` 从最近一次响应里抽取。"
            "示例：set_session_variable(name='token', from_path='data.access_token')"
        )
    )
    def set_session_variable(
        name: str,
        value: Optional[Any] = None,
        from_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if from_path:
            if not _session.last_response:
                return {"ok": False, "error": "无最近响应可抽取"}
            value = _resolve_path(_session.last_response.get("body"), from_path)
        _session.variables[name] = value
        return {"ok": True, "name": name, "value": value}

    @mcp.tool(description="读取会话变量。")
    def get_session_variable(name: str) -> Dict[str, Any]:
        if name not in _session.variables:
            return {"ok": False, "error": f"变量 {name} 不存在"}
        return {"ok": True, "name": name, "value": _session.variables[name]}

    @mcp.tool(description="清空所有会话变量与 OpenAPI 缓存。")
    def clear_session() -> Dict[str, Any]:
        _session.variables.clear()
        _session.openapi_specs.clear()
        _session.last_response = None
        return {"ok": True}

    return mcp


__all__ = ["create_http_api_mcp_server"]


# ============================================================================
# CLI 入口
# ============================================================================

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.mcp_server.http_api_server",
        description="HTTP API 测试 MCP Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7801)
    parser.add_argument("--name", default="http-api-mcp")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    log_handler = logging.StreamHandler(stream=sys.stderr)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[log_handler],
        force=True,
    )

    server = create_http_api_mcp_server(name=args.name)
    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "sse":
        server.settings.host = args.host
        server.settings.port = args.port
        server.run(transport="sse")
    else:
        server.settings.host = args.host
        server.settings.port = args.port
        server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
