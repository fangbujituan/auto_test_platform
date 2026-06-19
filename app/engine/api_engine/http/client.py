"""
HttpClient：引擎唯一的 HTTP IO 出口。

设计要点：
- **薄封装** ``app.services.request_factory.RequestFactory``，不重写网络栈；
  RequestFactory 已经在 ``routes/api.py`` 中稳定使用，复用即可。
- 把 RequestFactory 的"扁平字典"输出转换成引擎契约 ``(RequestRecord,
  ResponseRecord | None, error_message, error_type)``，让 StepExecutor 不必
  关心底层格式。
- 默认 timeout 来自构造参数；当 ``RequestSpec.timeout`` 与默认不一致时，
  每次 send 临时构造一个 RequestFactory（开销忽略不计）。
- 整个引擎只允许此模块 import requests / RequestFactory，便于将来替换为
  Mock / 异步实现。

作者: yandc
"""
from __future__ import annotations

import logging
from typing import Any

from app.engine.api_engine.results import RequestRecord, ResponseRecord
from app.engine.api_engine.specs import RequestSpec
from app.services.request_factory import RequestFactory, get_request_factory

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP 调用客户端。"""

    def __init__(
        self,
        *,
        factory: RequestFactory | None = None,
        default_timeout: int = 30,
    ) -> None:
        self._default_factory: RequestFactory = factory or get_request_factory()
        self._default_timeout: int = default_timeout

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def send(
        self,
        rendered: RequestSpec,
    ) -> tuple[RequestRecord, ResponseRecord | None, str | None, str | None]:
        """发送请求。

        Returns:
            (request_record, response_record, error_message, error_type)
            - response_record / error_message 至少有一个为 None
            - 网络错误、超时、解析错误统一翻译为 error_message + error_type
        """
        factory = self._pick_factory(rendered.timeout)

        raw = factory.execute(
            method=rendered.method,
            url=rendered.url,
            headers=rendered.headers,
            params=rendered.params,
            body=rendered.body,
            body_type=rendered.body_type,
        )

        request_record = self._build_request_record(rendered, raw)

        if raw.get("success"):
            response_record = self._build_response_record(raw)
            return request_record, response_record, None, None

        # 失败路径：把 RequestFactory 的 error 字典翻译成引擎语义
        err = raw.get("error") or {}
        error_type = err.get("type") or "UnknownError"
        error_message = err.get("message") or "请求执行失败"

        # 即便失败，RequestFactory 也可能返回 response（少见，但 4xx/5xx 仍算 success=true）
        response_record = (
            self._build_response_record(raw) if raw.get("response") else None
        )

        logger.warning(
            "[api_engine] http 调用失败 method=%s url=%s type=%s msg=%s",
            rendered.method, rendered.url, error_type, error_message,
        )
        return request_record, response_record, error_message, error_type

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _pick_factory(self, timeout: int | None) -> RequestFactory:
        """timeout 与默认一致则复用，否则一次性构造（避免改动 RequestFactory）。"""
        effective = timeout if timeout and timeout > 0 else self._default_timeout
        if effective == self._default_timeout:
            return self._default_factory
        return RequestFactory(timeout=effective)

    @staticmethod
    def _build_request_record(rendered: RequestSpec, raw: dict[str, Any]) -> RequestRecord:
        """优先取 RequestFactory 实际发出的 request 字典；缺字段则从 spec 兜底。"""
        req = raw.get("request") or {}
        return RequestRecord(
            method=req.get("method") or rendered.method.upper(),
            url=req.get("url") or rendered.url,
            headers=dict(req.get("headers") or rendered.headers or {}),
            params=dict(req.get("params") or rendered.params or {}),
            body=req.get("body") if "body" in req else rendered.body,
            body_type=req.get("body_type") or rendered.body_type,
        )

    @staticmethod
    def _build_response_record(raw: dict[str, Any]) -> ResponseRecord:
        """把 RequestFactory 的 response 字典转成 ResponseRecord。"""
        resp = raw.get("response") or {}
        # duration 是秒，转毫秒，便于 ResponseTimeAssertion 直接读
        elapsed_ms = float(raw.get("duration") or 0.0) * 1000.0
        return ResponseRecord(
            status_code=int(resp.get("status_code") or 0),
            status_text=str(resp.get("status_text") or ""),
            headers=dict(resp.get("headers") or {}),
            body=resp.get("body"),
            body_raw=resp.get("body_raw"),
            size=int(resp.get("size") or 0),
            encoding=resp.get("encoding"),
            elapsed_ms=elapsed_ms,
        )
