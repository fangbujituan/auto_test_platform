"""
ApiModelLoader：``apis`` 表 → RequestSpec / CollectionSpec。

职责：
- 把数据库中保存的接口配置（含 Phase 2 新增的 ``assertions / extracts / timeout``）
  转换成引擎的运行时 DTO
- 支持调用方传 ``overrides``（前端调试时的临时改动），覆盖 DB 中的字段
- 单接口转换 ``load_request``；批量转换 ``load_collection``（按 api_ids 顺序）

设计要点：
- 引擎核心**不**依赖 ORM；这里是引擎与 ``app/models/api.py`` 的唯一桥梁
- ``overrides`` 字段命名严格对齐前端老接口（base_url / path / headers / params / body / body_type / method）
- 找不到记录时抛 ``LoaderError``，路由层翻译为 404

作者: yandc
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.engine.api_engine.exceptions import InvalidRequestSpecError, LoaderError
from app.engine.api_engine.loaders.base import BaseLoader
from app.engine.api_engine.specs import (
    AssertionRule,
    CollectionSpec,
    ExtractRule,
    RequestSpec,
)

logger = logging.getLogger(__name__)


class ApiModelLoader(BaseLoader):
    """``apis`` 表 → RequestSpec。"""

    # ------------------------------------------------------------------
    # 单条转换
    # ------------------------------------------------------------------

    def load_request(
        self,
        *,
        api_id: int,
        project_id: int,
        overrides: dict[str, Any] | None = None,
    ) -> RequestSpec:
        """根据 ``api_id`` + ``project_id`` 从数据库取记录并转 RequestSpec。

        Args:
            api_id:     apis.id
            project_id: 用于权限和数据隔离校验
            overrides:  前端调试态的临时覆盖，可包含
                        ``method/base_url/path/headers/params/body/body_type/timeout/prefix_url_id``

        Raises:
            LoaderError: 找不到对应 (api_id, project_id) 的记录
        """
        api = self._fetch(api_id=api_id, project_id=project_id)
        return self._to_spec(api, overrides=overrides or {})

    # ------------------------------------------------------------------
    # 批量转换
    # ------------------------------------------------------------------

    def load_collection(
        self,
        *,
        api_ids: list[int],
        project_id: int,
        environment_id: int | None = None,
        fail_strategy: str = "continue",
        name: str = "api-sequence",
        per_api_overrides: dict[int, dict[str, Any]] | None = None,
        initial_variables: dict[str, Any] | None = None,
    ) -> CollectionSpec:
        """根据 ``api_ids`` 顺序构造 CollectionSpec。

        Args:
            api_ids:           待执行接口 ID 顺序数组
            project_id:        用于校验所有 api 都属于该项目
            environment_id:    可选环境 ID，写入 spec 但不在此处加载变量
            fail_strategy:     fail_fast / continue
            per_api_overrides: 每个 api 的局部覆盖（可选）；key=api_id
            initial_variables: 调用方注入的临时初始变量
        """
        if not api_ids:
            raise InvalidRequestSpecError(
                "api_ids 不能为空",
                details={"received_count": 0},
            )

        per_api_overrides = per_api_overrides or {}
        specs: list[RequestSpec] = []
        for api_id in api_ids:
            spec = self.load_request(
                api_id=api_id,
                project_id=project_id,
                overrides=per_api_overrides.get(api_id),
            )
            specs.append(spec)

        return CollectionSpec(
            name=name,
            project_id=project_id,
            environment_id=environment_id,
            requests=specs,
            fail_strategy=fail_strategy,
            initial_variables=dict(initial_variables or {}),
        )

    # ------------------------------------------------------------------
    # 数据访问 + 转换核心
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch(*, api_id: int, project_id: int):
        """从 DB 取 Api 实体，找不到抛 LoaderError。"""
        try:
            from app.models.api import Api
        except Exception as exc:  # pragma: no cover - 极端环境（无 Flask）
            raise LoaderError(
                "无法导入 Api 模型；ApiModelLoader 需要 Flask 上下文",
                details={"reason": str(exc)},
            ) from exc

        api = Api.query.filter_by(id=api_id, project_id=project_id).first()
        if api is None:
            raise LoaderError(
                f"接口不存在: api_id={api_id}, project_id={project_id}",
                details={"api_id": api_id, "project_id": project_id},
            )
        return api

    def _to_spec(self, api, *, overrides: dict[str, Any]) -> RequestSpec:
        """把 ``Api`` 实例 + overrides 合并成 RequestSpec。"""
        # 1. method / path / base_url：overrides > 模型字段
        method = (overrides.get("method") or api.method or "GET").upper()
        path = overrides.get("path") if "path" in overrides else api.path
        base_url = overrides.get("base_url") if "base_url" in overrides else (api.base_url or None)

        # 2. 当 path 是完整 URL 且 base_url 为空时，拆出 base_url（与老路由 ApiTestView 行为一致）
        if not base_url and path and isinstance(path, str) and path.startswith(("http://", "https://")):
            parsed = urlparse(path)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")

        # 3. headers / params / body / body_type：overrides 替换整体
        headers = (
            overrides.get("headers") if "headers" in overrides else (api.headers or {})
        )
        params = (
            overrides.get("params") if "params" in overrides else (api.params or {})
        )
        body = overrides.get("body") if "body" in overrides else api.body
        body_type = (overrides.get("body_type") or api.body_type or "json").lower()

        # 4. assertions / extracts：overrides 优先
        raw_assertions = (
            overrides.get("assertions")
            if "assertions" in overrides
            else (api.assertions or [])
        )
        raw_extracts = (
            overrides.get("extracts")
            if "extracts" in overrides
            else (api.extracts or [])
        )

        # 5. 其他控制字段
        timeout = overrides.get("timeout") if "timeout" in overrides else api.timeout
        timeout = int(timeout) if timeout else 30
        prefix_url_id = (
            overrides.get("prefix_url_id")
            if "prefix_url_id" in overrides
            else api.prefix_url_id
        )
        delay_ms = int(overrides.get("delay_ms") or 0)
        on_failure = self._normalize_on_failure(overrides.get("on_failure"))

        spec = RequestSpec(
            name=overrides.get("name") or api.name or f"api-{api.id}",
            method=method,
            url=path or "",
            headers=dict(headers or {}),
            params=dict(params or {}),
            body=body,
            body_type=body_type,
            timeout=timeout,
            delay_ms=delay_ms,
            on_failure=on_failure,
            extracts=[self._coerce_extract(e) for e in (raw_extracts or [])],
            assertions=[self._coerce_assertion(a) for a in (raw_assertions or [])],
            api_id=api.id,
            module=api.module,
            service=api.service,
            prefix_url_id=prefix_url_id,
            base_url=base_url,
        )

        logger.debug(
            "[api_engine] ApiModelLoader 转换完成 api_id=%s assertions=%d extracts=%d",
            api.id, len(spec.assertions), len(spec.extracts),
        )
        return spec

    # ------------------------------------------------------------------
    # 子结构兼容转换（DB 里读出来的是 dict，需变成 dataclass）
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_assertion(raw: Any) -> AssertionRule:
        """DB 中存的 assertions JSON 元素 → AssertionRule。

        DB 数据由前端写入，理论上字段齐全；但仍做兜底，缺 ``type`` 时直接抛错。
        """
        if isinstance(raw, AssertionRule):
            return raw
        if not isinstance(raw, dict):
            raise InvalidRequestSpecError(
                "apis.assertions 元素必须是 dict",
                details={"got_type": type(raw).__name__},
            )
        if not raw.get("type"):
            raise InvalidRequestSpecError(
                "apis.assertions 元素缺少 type",
                details={"received": raw},
            )
        return AssertionRule(
            type=str(raw["type"]),
            config=dict(raw.get("config") or {}),
            name=str(raw.get("name") or ""),
        )

    @staticmethod
    def _coerce_extract(raw: Any) -> ExtractRule:
        """DB 中存的 extracts JSON 元素 → ExtractRule。"""
        if isinstance(raw, ExtractRule):
            return raw
        if not isinstance(raw, dict):
            raise InvalidRequestSpecError(
                "apis.extracts 元素必须是 dict",
                details={"got_type": type(raw).__name__},
            )
        missing = [k for k in ("name", "type", "expression") if not raw.get(k)]
        if missing:
            raise InvalidRequestSpecError(
                f"apis.extracts 元素缺少必填字段: {missing}",
                details={"missing": missing, "received": raw},
            )
        return ExtractRule(
            name=str(raw["name"]),
            type=str(raw["type"]),
            expression=str(raw["expression"]),
            default=raw.get("default"),
        )

    @staticmethod
    def _normalize_on_failure(value: Any) -> str:
        if not value:
            return "inherit"
        normalized = str(value).strip().lower()
        if normalized in ("stop", "continue", "inherit"):
            return normalized
        return "inherit"
