"""
Agent 模板方法基类。

提供所有业务 Agent 的统一脚手架：

- 执行前后的结构化日志
- 计时（latency_ms）
- 不可变字段（task_id / correlation_id / workflow_id）保护
- history 仅追加（append-only）跟踪
- JSON Schema 风格的输出校验（轻量自实现，无第三方依赖）

子类只需实现两件事：

1. ``name`` 属性 —— Agent 的唯一标识
2. ``_process(state)`` —— 业务核心逻辑（异步），返回更新后的 state
3. （可选）覆盖 ``output_schema`` 属性来声明 ``output_data`` 的 schema

迁移自 ``code-factory/agents/base_agent.py``：
- 把 ``structlog`` 替换为项目现有的 ``app.utils.debug.logs``
- 异常类型改为本项目的 ``AgentExecutionError``

作者: yandc
"""
from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any

from app.agents.orchestration.exceptions import AgentExecutionError
from app.agents.orchestration.interfaces import AgentInterface
from app.agents.orchestration.state import AgentState
from app.utils.debug import logs


# 全局单例 ModelRouter（按 routing_rules.yaml 默认配置加载）
# 延迟初始化避免循环 import
_default_router = None


def _get_default_router():
    """惰性获取全局 ModelRouter 单例。"""
    global _default_router
    if _default_router is None:
        from app.agents.routing import ModelRouter

        _default_router = ModelRouter()
    return _default_router


# ---------------------------------------------------------------------------
# 轻量 JSON Schema 校验器
# ---------------------------------------------------------------------------
_PY_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _validate_against_schema(data: Any, schema: dict[str, Any]) -> list[str]:
    """对 ``data`` 按简化版 JSON Schema 做校验，返回错误列表（空列表表示通过）。

    支持的字段：

    - ``type``       目前只支持 ``object``（其他直接放行）
    - ``required``   必填 key 列表
    - ``properties`` 子字段类型描述（仅检查存在的字段）
    """
    errors: list[str] = []

    if schema.get("type") == "object":
        if not isinstance(data, dict):
            errors.append(
                f"Expected type 'object' (dict), got '{type(data).__name__}'"
            )
            return errors

    for key in schema.get("required", []):
        if not isinstance(data, dict) or key not in data:
            errors.append(f"Missing required field: '{key}'")

    if isinstance(data, dict):
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if prop_name not in data:
                continue
            expected = _PY_TYPE_MAP.get(prop_schema.get("type", ""))
            if expected and not isinstance(data[prop_name], expected):
                errors.append(
                    f"Field '{prop_name}' expected type "
                    f"'{prop_schema.get('type')}', "
                    f"got '{type(data[prop_name]).__name__}'"
                )

    return errors


# ---------------------------------------------------------------------------
# BaseAgent 模板方法基类
# ---------------------------------------------------------------------------
class BaseAgent(AgentInterface):
    """业务 Agent 的统一基类（模板方法模式）。

    使用方式
    --------

    ::

        class MyAgent(BaseAgent):
            name = "my_agent"

            output_schema = {
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
            }

            async def _process(self, state: AgentState) -> AgentState:
                state.output_data["result"] = "hello"
                return state
    """

    #: 子类必须覆盖；用于日志、注册、审核闸定位
    name: str = "base_agent"

    #: 子类可覆盖；默认接受任意 dict 作为 output_data
    output_schema: dict[str, Any] = {"type": "object"}

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    async def execute(self, state: AgentState) -> AgentState:
        """执行 Agent 的模板方法（不可被子类覆盖，子类只实现 ``_process``）。

        负责：日志、计时、不可变字段保护、history 追加、异常包装。
        """
        # 不可变字段快照
        task_id = state.task_id
        correlation_id = state.correlation_id
        workflow_id = state.workflow_id

        input_summary = self._summarize(state.input_data)
        logs.info(
            f"[agent:{self.name}] execute start | "
            f"task_id={task_id} correlation_id={correlation_id} "
            f"input_summary={input_summary}"
        )

        start_ts = time.perf_counter()
        model_used = "unknown"

        try:
            updated = await self._process(state)

            # 强制还原不可变字段（即使子类不小心改了也能纠正）
            updated.task_id = task_id
            updated.correlation_id = correlation_id
            updated.workflow_id = workflow_id

            latency_ms = (time.perf_counter() - start_ts) * 1000
            model_used = updated.metadata.get("model_used", "unknown")
            output_summary = self._summarize(updated.output_data)

            logs.info(
                f"[agent:{self.name}] execute done | "
                f"latency_ms={latency_ms:.2f} model={model_used} "
                f"output_summary={output_summary}"
            )

            updated.history.append(
                {
                    "agent_name": self.name,
                    "input_summary": input_summary,
                    "output_summary": output_summary,
                    "model_used": model_used,
                    "latency_ms": round(latency_ms, 2),
                    "status": "completed",
                }
            )
            return updated

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_ts) * 1000
            logs.error(
                f"[agent:{self.name}] execute failed | "
                f"latency_ms={latency_ms:.2f} error={exc}"
            )
            state.history.append(
                {
                    "agent_name": self.name,
                    "input_summary": input_summary,
                    "output_summary": "",
                    "model_used": model_used,
                    "latency_ms": round(latency_ms, 2),
                    "status": "failed",
                    "error": str(exc),
                }
            )
            raise AgentExecutionError(
                f"Agent '{self.name}' failed: {exc}",
                correlation_id=correlation_id,
            ) from exc

    def validate_output(self, state: AgentState) -> bool:
        """校验 ``state.output_data`` 是否符合 ``output_schema``。

        失败时打印 warning 但不抛异常；具体重试策略由编排器决定。
        """
        errors = _validate_against_schema(state.output_data, self.output_schema)
        if errors:
            logs.warning(
                f"[agent:{self.name}] output validation failed | "
                f"correlation_id={state.correlation_id} errors={errors}"
            )
            return False
        return True

    # ------------------------------------------------------------------
    # 子类必须实现
    # ------------------------------------------------------------------
    @abstractmethod
    async def _process(self, state: AgentState) -> AgentState:
        """子类实现真正的业务逻辑，返回更新后的 state。"""

    # ------------------------------------------------------------------
    # 便捷方法：通过 ModelRouter 调 LLM（Step 4 引入）
    # ------------------------------------------------------------------
    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        *,
        task_type: str | None = None,
        context: dict[str, Any] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        state: AgentState | None = None,
    ) -> str:
        """通过 :class:`ModelRouter` 调 LLM，按复杂度自动选择模型。

        所有业务 Agent 应优先使用本方法而不是直接 ``llm_gateway.get_model``，
        这样 ``routing_rules.yaml`` 才能真正生效。

        Args:
            messages:    OpenAI 风格的 ``[{"role": ..., "content": ...}]``
            task_type:   路由 key；不传时使用 ``self.name``
            context:     用于复杂度评估的上下文（``context_length`` /
                         ``num_files`` / ``has_dependencies`` /
                         ``language_count``）
            temperature: 采样温度
            max_tokens:  最大生成 token 数
            state:       可选；命中模型后会把 ``model_used`` / ``token_count``
                         写回 ``state.metadata``，方便编排器统一统计

        Returns:
            模型生成的纯文本。
        """
        from app.agents.routing import LLMRequest

        router = _get_default_router()
        effective_task_type = task_type or self.name
        complexity = router.classify_complexity(
            task_type=effective_task_type,
            context=context or {},
        )
        request = LLMRequest(
            messages=messages,
            task_type=effective_task_type,
            complexity=complexity,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response = await router.route(request)

        # 把模型与 token 用量回写到 state.metadata，让 orchestrator 的
        # invocation_log 可以拿到准确数字
        if state is not None:
            state.metadata["model_used"] = response.model_used
            state.metadata["token_count"] = response.token_count
            state.metadata["model_tier"] = response.tier.value

        logs.info(
            f"[agent:{self.name}] _call_llm | "
            f"task={effective_task_type} complexity={complexity.value} "
            f"-> model={response.model_used} tier={response.tier.value} "
            f"tokens={response.token_count}"
        )
        return response.content

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    @staticmethod
    def _summarize(data: Any, max_length: int = 200) -> str:
        """把任意 dict / 对象转成简短字符串摘要，用于日志。"""
        if not data:
            return "{}"
        text = str(data)
        if len(text) <= max_length:
            return text
        return text[: max_length] + "..."


__all__ = ["BaseAgent"]
