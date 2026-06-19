"""
ExecutionContext：执行上下文。

每次 ``ApiEngine.run_*`` 创建一个，按 ``run_id`` 隔离，绝不共享。

变量优先级（高 → 低）：
    extracted > initial > environment > global

设计要点：
- 引擎核心**唯一**的"DB 依赖+全局可变状态"集中点，便于单测。
- 渲染未命中变量时**不报错**，原样保留并把缺失键写入 ``warnings``。
- ``render_request`` 返回新的 ``RequestSpec``（``dataclasses.replace``），不修改入参。

作者: yandc
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.engine.api_engine.specs import RequestSpec
from app.engine.api_engine.variables.prefix_url import (
    load_project_variables,
    merge_global_params,
    resolve_prefix_url,
)
from app.engine.api_engine.variables.resolver import VariableResolver

logger = logging.getLogger(__name__)


class ExecutionContext:
    """单次运行的上下文。"""

    def __init__(
        self,
        *,
        project_id: int,
        environment_id: int | None = None,
        initial_variables: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.run_id: str = run_id or str(uuid4())
        self.project_id: int = project_id
        self.environment_id: int | None = environment_id
        self.started_at: datetime = datetime.now()

        # 变量分层存储（按优先级从低到高）
        self._initial: dict[str, Any] = dict(initial_variables or {})
        self._extracted: dict[str, Any] = {}

        # 加载项目变量（global + env），失败静默
        self._project_vars: dict[str, Any] = load_project_variables(
            project_id=project_id, environment_id=environment_id
        )

        # 累计警告（缺失变量、抽取失败等）
        self.warnings: list[str] = []

        logger.info(
            "[api_engine] context 准备就绪 run_id=%s project=%s env=%s vars=%d",
            self.run_id, project_id, environment_id, len(self._project_vars),
        )

    # ------------------------------------------------------------------
    # 变量视图（合并后的只读快照）
    # ------------------------------------------------------------------

    @property
    def variables(self) -> dict[str, Any]:
        """合并后的变量视图（按优先级覆盖）。"""
        merged: dict[str, Any] = {}
        merged.update(self._project_vars)  # global + env（已合并）
        merged.update(self._initial)
        merged.update(self._extracted)
        return merged

    def update_extracted(self, kv: dict[str, Any]) -> None:
        """把抽取到的字段写入上下文，覆盖同名旧值。"""
        if not kv:
            return
        for key, value in kv.items():
            self._extracted[key] = value
        logger.debug("[api_engine] run_id=%s 抽取写入: %s", self.run_id, list(kv.keys()))

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def render_request(self, spec: RequestSpec) -> RequestSpec:
        """对 RequestSpec 中所有"可能含 {{var}}"的字段做渲染，返回新对象。

        渲染范围：name/url/headers/params/body/base_url/module/service。
        断言/抽取规则中的 ``config`` 与 ``expression`` 暂不参与渲染（断言通常使用字面量）。
        """
        resolver = VariableResolver()
        variables = self.variables

        rendered = replace(
            spec,
            name=resolver.render_string(spec.name, variables),
            url=resolver.render_string(spec.url, variables),
            base_url=(
                resolver.render_string(spec.base_url, variables)
                if spec.base_url is not None
                else None
            ),
            headers=resolver.render_value(dict(spec.headers), variables),
            params=resolver.render_value(dict(spec.params), variables),
            body=resolver.render_value(spec.body, variables),
            module=(
                resolver.render_string(spec.module, variables)
                if spec.module is not None
                else None
            ),
            service=(
                resolver.render_string(spec.service, variables)
                if spec.service is not None
                else None
            ),
        )

        if resolver.missing_keys:
            warning = (
                f"未解析的变量占位符（已原样保留）: "
                f"{sorted(resolver.missing_keys)}"
            )
            self.warnings.append(warning)
            logger.warning("[api_engine] run_id=%s %s", self.run_id, warning)

        return rendered

    # ------------------------------------------------------------------
    # URL 拼接
    # ------------------------------------------------------------------

    def resolve_full_url(self, rendered: RequestSpec) -> str:
        """根据渲染后的 RequestSpec 解析最终 URL。

        优先级（与 routes/api.py 现有行为对齐）：
        1. 接口自带 ``base_url`` + ``url`` 拼接
        2. 若 ``base_url`` 为空，但 ``url`` 是完整 URL，则直接用 ``url``
        3. 否则尝试通过 ``prefix_url_id`` / ``module``+``service`` 解析 base_url
        """
        base_url = rendered.base_url or ""
        path = rendered.url or ""

        # 当 url 本身是完整 URL 且 base_url 为空时，直接用 url
        if not base_url and path.startswith(("http://", "https://")):
            return path

        # 当 base_url 为空但有 prefix_url_id，先查绑定的前置 URL
        if not base_url and rendered.prefix_url_id:
            base_url = self._lookup_prefix_url_by_id(rendered.prefix_url_id)

        # 仍为空则按 module/service 解析
        if not base_url:
            base_url = resolve_prefix_url(
                environment_id=self.environment_id,
                module=rendered.module,
                service=rendered.service,
                base_url="",
            )

        # 兼容 path 是绝对 URL 的情况：base_url 优先级低于完整 URL
        if path.startswith(("http://", "https://")):
            return path

        # 拼接（处理 / 边界）
        if base_url and path:
            if base_url.endswith("/") and path.startswith("/"):
                return base_url[:-1] + path
            if not base_url.endswith("/") and not path.startswith("/"):
                return f"{base_url}/{path}"
        return f"{base_url}{path}"

    @staticmethod
    def _lookup_prefix_url_by_id(prefix_url_id: int) -> str:
        """按 ID 查 PrefixUrl 表，DB 不可用时返回空串。"""
        try:
            from app.models.env_variable import PrefixUrl
        except Exception:
            return ""
        try:
            record = PrefixUrl.query.get(prefix_url_id)
            return record.url if record and record.url else ""
        except Exception as exc:  # pragma: no cover
            logger.warning("[api_engine] 查 PrefixUrl(id=%s) 失败: %s", prefix_url_id, exc)
            return ""

    # ------------------------------------------------------------------
    # 全局参数合并
    # ------------------------------------------------------------------

    def merge_global_params_into_headers(self, headers: dict[str, Any]) -> dict[str, Any]:
        """将项目 GlobalParam 合并到 Header（已有同名 Header 不被覆盖）。"""
        return merge_global_params(project_id=self.project_id, headers=headers)
