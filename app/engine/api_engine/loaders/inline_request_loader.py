"""
InlineRequestLoader：前端临时 dict → RequestSpec。

应用场景：
- 接口未保存（"调试模式"），前端直接传 JSON 跑一次
- 多接口顺序执行的"步骤覆盖"

校验语义：
- ``method`` / ``url`` 必填
- ``assertions`` / ``extracts`` 数组中每项必须是 dict 且字段齐全
- 字段类型不匹配时抛 ``InvalidRequestSpecError``，并在 details 中给出原因

设计要点：
- 不读数据库；纯函数式转换
- 抛出的异常 SHALL 携带 ``details`` 结构化信息，便于路由层翻译为有用的错误响应

作者: yandc
"""
from __future__ import annotations

from typing import Any

from app.engine.api_engine.exceptions import InvalidRequestSpecError
from app.engine.api_engine.loaders.base import BaseLoader
from app.engine.api_engine.specs import (
    AssertionRule,
    CollectionSpec,
    ExtractRule,
    RequestSpec,
)

# 允许的字段集合（白名单），用于在校验阶段提示拼写错误
_ALLOWED_REQUEST_KEYS: set[str] = {
    "name", "method", "url", "headers", "params", "body", "body_type",
    "timeout", "delay_ms", "on_failure", "extracts", "assertions",
    "api_id", "module", "service", "prefix_url_id", "base_url",
}


class InlineRequestLoader(BaseLoader):
    """dict → RequestSpec / list[dict] → CollectionSpec。"""

    # ------------------------------------------------------------------
    # 单条转换
    # ------------------------------------------------------------------

    def load_request(
        self,
        payload: dict[str, Any],
        *,
        default_name: str = "ad-hoc-request",
    ) -> RequestSpec:
        """单个 dict → ``RequestSpec``。

        Raises:
            InvalidRequestSpecError: payload 非 dict / 缺必填 / 字段类型非法
        """
        self._guard_dict("payload", payload)
        self._warn_unknown_keys(payload)

        missing = [k for k in ("method", "url") if not payload.get(k)]
        if missing:
            raise InvalidRequestSpecError(
                f"payload 缺少必填字段: {missing}",
                details={"missing": missing, "payload_keys": list(payload.keys())},
            )

        return RequestSpec(
            name=str(payload.get("name") or default_name),
            method=str(payload["method"]).upper(),
            url=str(payload["url"]),
            headers=self._guard_dict("headers", payload.get("headers"), allow_none=True) or {},
            params=self._guard_dict("params", payload.get("params"), allow_none=True) or {},
            body=payload.get("body"),
            body_type=str(payload.get("body_type") or "json"),
            timeout=self._coerce_int("timeout", payload.get("timeout"), default=30),
            delay_ms=self._coerce_int("delay_ms", payload.get("delay_ms"), default=0),
            on_failure=self._normalize_on_failure(payload.get("on_failure")),
            extracts=[self._build_extract(r) for r in (payload.get("extracts") or [])],
            assertions=[self._build_assertion(r) for r in (payload.get("assertions") or [])],
            api_id=payload.get("api_id"),
            module=payload.get("module"),
            service=payload.get("service"),
            prefix_url_id=payload.get("prefix_url_id"),
            base_url=payload.get("base_url"),
        )

    # ------------------------------------------------------------------
    # 批量转换
    # ------------------------------------------------------------------

    def load_collection(
        self,
        *,
        payloads: list[dict[str, Any]],
        project_id: int,
        environment_id: int | None = None,
        name: str = "ad-hoc-sequence",
        fail_strategy: str = "continue",
        initial_variables: dict[str, Any] | None = None,
    ) -> CollectionSpec:
        if not payloads:
            raise InvalidRequestSpecError(
                "payloads 不能为空",
                details={"received_count": 0},
            )
        if not isinstance(payloads, list):
            raise InvalidRequestSpecError(
                "payloads 必须是 list",
                details={"got_type": type(payloads).__name__},
            )

        specs = [
            self.load_request(p, default_name=f"step-{i + 1}")
            for i, p in enumerate(payloads)
        ]
        return CollectionSpec(
            name=name,
            project_id=project_id,
            environment_id=environment_id,
            requests=specs,
            fail_strategy=fail_strategy,
            initial_variables=dict(initial_variables or {}),
        )

    # ------------------------------------------------------------------
    # 子结构构造
    # ------------------------------------------------------------------

    @staticmethod
    def _build_extract(raw: Any) -> ExtractRule:
        if not isinstance(raw, dict):
            raise InvalidRequestSpecError(
                "extracts 数组元素必须是 dict",
                details={"got_type": type(raw).__name__},
            )
        missing = [k for k in ("name", "type", "expression") if not raw.get(k)]
        if missing:
            raise InvalidRequestSpecError(
                f"ExtractRule 缺少必填字段: {missing}",
                details={"missing": missing, "received": raw},
            )
        return ExtractRule(
            name=str(raw["name"]),
            type=str(raw["type"]),
            expression=str(raw["expression"]),
            default=raw.get("default"),
        )

    @staticmethod
    def _build_assertion(raw: Any) -> AssertionRule:
        if not isinstance(raw, dict):
            raise InvalidRequestSpecError(
                "assertions 数组元素必须是 dict",
                details={"got_type": type(raw).__name__},
            )
        if not raw.get("type"):
            raise InvalidRequestSpecError(
                "AssertionRule 缺少必填字段: type",
                details={"received": raw},
            )
        return AssertionRule(
            type=str(raw["type"]),
            config=dict(raw.get("config") or {}),
            name=str(raw.get("name") or ""),
        )

    # ------------------------------------------------------------------
    # 字段校验工具
    # ------------------------------------------------------------------

    @staticmethod
    def _guard_dict(field: str, value: Any, *, allow_none: bool = False):
        if value is None:
            if allow_none:
                return None
            raise InvalidRequestSpecError(
                f"{field} 不能为 None",
                details={"field": field},
            )
        if not isinstance(value, dict):
            raise InvalidRequestSpecError(
                f"{field} 必须是 dict",
                details={"field": field, "got_type": type(value).__name__},
            )
        return value

    @staticmethod
    def _coerce_int(field: str, value: Any, *, default: int) -> int:
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise InvalidRequestSpecError(
                f"{field} 必须是整数",
                details={"field": field, "got": repr(value)},
            ) from exc

    @staticmethod
    def _normalize_on_failure(value: Any) -> str:
        """规整 on_failure 取值，非法值回退到 'inherit' 并不报错（兼容性）。"""
        if not value:
            return "inherit"
        normalized = str(value).strip().lower()
        if normalized in ("stop", "continue", "inherit"):
            return normalized
        return "inherit"

    @staticmethod
    def _warn_unknown_keys(payload: dict[str, Any]) -> None:
        """对未知字段不报错，仅在 logger 里提示，便于前端逐步迁移。"""
        unknown = set(payload.keys()) - _ALLOWED_REQUEST_KEYS
        if unknown:
            import logging
            logging.getLogger(__name__).debug(
                "[api_engine] InlineRequestLoader 收到未知字段 %s（已忽略）", unknown
            )
