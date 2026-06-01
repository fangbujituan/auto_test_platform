"""
基于复杂度的模型路由器（桥接到项目现有 llm_gateway）。

迁移自 ``code-factory/tools/model_router.py``，针对本项目做了三点调整：

1. **桥接 ``llm_gateway``**：``_call_model`` 直接调
   :func:`app.services.llm_gateway.get_model` 取 ChatOpenAI 实例并 invoke，
   无需 litellm。
2. **日志统一**：用 ``app.utils.debug.logs`` 替换 structlog。
3. **配置默认路径**：``app/agents/config/routing_rules.yaml``。

核心特性
--------

- **复杂度分类**：根据 task_type + context 自动评估为 LOW / MEDIUM / HIGH
- **分层路由**：LOW → LOCAL；HIGH → CLOUD；MEDIUM → 默认 LOCAL（本地优先）
- **同层重试**：单层内最多 ``max_retries`` 次（来自 fallback 配置）
- **跨层升级**：本层全部失败时升级到下一层，直到耗尽 → ``ModelTierExhaustedError``

作者: yandc
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from app.agents.orchestration.exceptions import (
    ModelRoutingError,
    ModelTierExhaustedError,
)
from app.agents.orchestration.interfaces import ModelRouterInterface
from app.agents.routing.routing_models import (
    LLMRequest,
    LLMResponse,
    ModelTier,
    TaskComplexity,
)
from app.utils.debug import logs


# 层级升级顺序
_TIER_ESCALATION_ORDER: list[ModelTier] = [ModelTier.LOCAL, ModelTier.CLOUD]

# 默认配置文件路径
_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "routing_rules.yaml"
)


class ModelRouter(ModelRouterInterface):
    """按任务复杂度路由 LLM 请求的统一入口。

    使用方式::

        router = ModelRouter()
        complexity = router.classify_complexity(
            task_type="testcase",
            context={"context_length": 4000},
        )
        request = LLMRequest(
            messages=[{"role": "user", "content": "..."}],
            task_type="testcase",
            complexity=complexity,
        )
        response = await router.route(request)
    """

    def __init__(
        self,
        routing_config: Optional[dict[str, Any]] = None,
        config_path: Optional[str | Path] = None,
    ) -> None:
        """构造路由器。

        Args:
            routing_config: 已加载的配置字典（优先级最高）
            config_path:    YAML 配置路径；不传时用项目内置默认值
        """
        if routing_config is not None:
            self._config = routing_config
        else:
            self._config = self._load_config(
                Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
            )

        routing = self._config.get("routing", {})
        self._rules: list[dict[str, Any]] = routing.get("rules", [])
        fallback = routing.get("fallback", {})
        self._max_retries: int = fallback.get("max_retries", 3)
        self._retry_delay_seconds: int = fallback.get("retry_delay_seconds", 2)
        self._escalation_enabled: bool = fallback.get("escalation_enabled", True)

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    @staticmethod
    def _load_config(config_path: Path) -> dict[str, Any]:
        """从 YAML 加载配置。"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            raise ModelRoutingError(
                f"Failed to load routing config from '{config_path}': {e}"
            )

    # ------------------------------------------------------------------
    # 复杂度分类
    # ------------------------------------------------------------------
    def classify_complexity(
        self, task_type: str, context: dict
    ) -> TaskComplexity:
        """根据 task_type 与 context 推断任务复杂度。

        策略
        ----

        1. 在路由规则里查 task_type 对应的 ``complexity_threshold``
        2. 同时根据 context 字段（context_length / num_files / has_dependencies /
           language_count）做一次启发式打分
        3. 取两者中**较高**的复杂度返回（保证宁可杀鸡用牛刀，不要小马拉大车）
        4. 没匹配规则时默认 ``MEDIUM``
        """
        rule_complexity = self._get_rule_complexity(task_type)
        context_complexity = self._evaluate_context_complexity(context or {})

        order = {
            TaskComplexity.LOW: 0,
            TaskComplexity.MEDIUM: 1,
            TaskComplexity.HIGH: 2,
        }
        if order[context_complexity] > order[rule_complexity]:
            return context_complexity
        return rule_complexity

    def _get_rule_complexity(self, task_type: str) -> TaskComplexity:
        for rule in self._rules:
            if rule.get("task_type") == task_type:
                return self._parse_complexity(
                    rule.get("complexity_threshold", "medium")
                )
        return TaskComplexity.MEDIUM

    def _evaluate_context_complexity(self, context: dict) -> TaskComplexity:
        if not context:
            return TaskComplexity.LOW

        score = 0

        ctx_len = context.get("context_length", 0)
        if ctx_len > 10000:
            score += 2
        elif ctx_len > 3000:
            score += 1

        num_files = context.get("num_files", 0)
        if num_files > 10:
            score += 2
        elif num_files > 3:
            score += 1

        if context.get("has_dependencies", False):
            score += 1

        if context.get("language_count", 1) > 2:
            score += 1

        if score >= 4:
            return TaskComplexity.HIGH
        if score >= 2:
            return TaskComplexity.MEDIUM
        return TaskComplexity.LOW

    @staticmethod
    def _parse_complexity(value: str) -> TaskComplexity:
        return {
            "low": TaskComplexity.LOW,
            "medium": TaskComplexity.MEDIUM,
            "high": TaskComplexity.HIGH,
        }.get(value.lower(), TaskComplexity.MEDIUM)

    # ------------------------------------------------------------------
    # 模型选择
    # ------------------------------------------------------------------
    def _get_tier_for_complexity(
        self, complexity: TaskComplexity
    ) -> ModelTier:
        """LOW → LOCAL；HIGH → CLOUD；MEDIUM → LOCAL（本地优先）。"""
        if complexity == TaskComplexity.LOW:
            return ModelTier.LOCAL
        if complexity == TaskComplexity.HIGH:
            return ModelTier.CLOUD
        return ModelTier.LOCAL

    def _get_models_for_tier(
        self, task_type: str, tier: ModelTier
    ) -> list[str]:
        """从规则里取出某 task_type 在某层级下的候选模型列表。"""
        for rule in self._rules:
            if rule.get("task_type") == task_type:
                if tier == ModelTier.LOCAL:
                    return rule.get("local_models", []) or []
                return rule.get("cloud_models", []) or []
        return []

    def _get_escalation_order(
        self, initial_tier: ModelTier
    ) -> list[ModelTier]:
        """从初始层级开始的升级顺序。"""
        if not self._escalation_enabled:
            return [initial_tier]
        try:
            start = _TIER_ESCALATION_ORDER.index(initial_tier)
        except ValueError:
            return [initial_tier]
        return _TIER_ESCALATION_ORDER[start:]

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    async def route(self, request: LLMRequest) -> LLMResponse:
        """按规则选择模型并发起调用。

        Raises:
            ModelTierExhaustedError: 所有层级都无可用模型
            ModelRoutingError:       不可重试错误
        """
        initial_tier = self._get_tier_for_complexity(request.complexity)
        tier_order = self._get_escalation_order(initial_tier)

        total_attempts = 0

        for tier in tier_order:
            models = self._get_models_for_tier(request.task_type, tier)
            if not models:
                logs.debug(
                    f"[router] no models configured | "
                    f"tier={tier.value} task_type={request.task_type}"
                )
                continue

            tier_attempts = 0
            for model in models:
                if tier_attempts >= self._max_retries:
                    break
                tier_attempts += 1
                total_attempts += 1

                try:
                    return await self._call_model(request, model, tier)
                except _RETRYABLE_ERRORS as e:
                    logs.warning(
                        f"[router] model unavailable, retrying | "
                        f"model={model} tier={tier.value} "
                        f"attempt={tier_attempts}/{self._max_retries} "
                        f"error={e}"
                    )
                    if tier_attempts < self._max_retries:
                        await asyncio.sleep(self._retry_delay_seconds)
                except Exception as e:  # noqa: BLE001
                    raise ModelRoutingError(
                        f"Model call failed with non-retryable error: {e}"
                    )

            if tier != tier_order[-1] and self._escalation_enabled:
                logs.warning(
                    f"[router] tier exhausted, escalating | "
                    f"exhausted_tier={tier.value} attempts={tier_attempts} "
                    f"task_type={request.task_type}"
                )

        raise ModelTierExhaustedError(
            tier=tier_order[-1].value if tier_order else "unknown",
            attempts=total_attempts,
        )

    # ------------------------------------------------------------------
    # 实际模型调用（桥接到项目现有 llm_gateway，避免硬依赖 litellm）
    # ------------------------------------------------------------------
    async def _call_model(
        self,
        request: LLMRequest,
        model: str,
        tier: ModelTier,
    ) -> LLMResponse:
        """调用具体模型。

        Step 4 实现：把请求桥接到项目现有的 :func:`app.services.llm_gateway.get_model`，
        统一走 4 个网关（aiop / kiro / aiclient / local），自动接 token 统计回调。

        - ``llm_gateway.get_model`` 返回的是 LangChain ``ChatOpenAI``，
          其 ``invoke`` 是同步的；这里用 ``asyncio.to_thread`` 把它推到
          线程池里执行，整体保持异步语义。
        - ``model`` 来自 ``routing_rules.yaml``，格式是
          ``"<gateway>/<provider>/<model>"`` 或 ``"<gateway>/<model>"``，
          直接透传给 ``get_model``。
        - Token 统计：``llm_gateway`` 内部已挂 ``TokenCallback``，
          会自动按 thread_id / agent_name 入库；这里只负责把 OpenAI
          风格的 ``response_metadata.token_usage`` 镜像到 :class:`LLMResponse`，
          供调用方做即时观测。

        Raises:
            ModelRoutingError: 调用失败但被识别为不可重试错误时抛出。
        """
        from app.services.llm_gateway import get_model
        from langchain_core.messages import (
            AIMessage,
            HumanMessage,
            SystemMessage,
        )

        start_ts = time.perf_counter()

        # 把 OpenAI 风格的 messages 列表转成 LangChain BaseMessage
        cls_map = {
            "system": SystemMessage,
            "user": HumanMessage,
            "human": HumanMessage,
            "assistant": AIMessage,
            "ai": AIMessage,
        }
        lc_messages = [
            cls_map.get(m.get("role", "user"), HumanMessage)(content=m.get("content", ""))
            for m in request.messages
        ]

        # ChatOpenAI 是同步的，用线程池避免阻塞事件循环
        llm = get_model(model=model, agent_name=request.task_type)
        response = await asyncio.to_thread(llm.invoke, lc_messages)

        elapsed_ms = (time.perf_counter() - start_ts) * 1000

        # 抽 token 用量（兼容 OpenAI / Claude / DeepSeek 多种 metadata 风格）
        token_count = _extract_token_usage(response)
        content = getattr(response, "content", "") or ""
        if isinstance(content, list):
            # Claude 等模型会返回 [{"type": "text", "text": "..."}]
            content = "".join(
                seg.get("text", "")
                for seg in content
                if isinstance(seg, dict) and seg.get("type") == "text"
            )

        logs.info(
            f"[router] model call | "
            f"model={model} tier={tier.value} task={request.task_type} "
            f"latency_ms={elapsed_ms:.2f} "
            f"in_tokens={token_count['input']} out_tokens={token_count['output']}"
        )

        return LLMResponse(
            content=content,
            model_used=model,
            tier=tier,
            token_count=token_count,
            latency_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# 工具：从 LangChain 响应里抽 token 用量
# ---------------------------------------------------------------------------
def _extract_token_usage(response: Any) -> dict[str, int]:
    """兼容 OpenAI / Anthropic / DeepSeek 的 token 用量抽取。

    LangChain 的 ``AIMessage`` 把 token 用量放在两个不同的位置（取决于上游
    协议），这里统一抽出 ``{"input": N, "output": M}``。
    """
    # 优先走 LangChain 标准字段 usage_metadata
    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        return {
            "input": int(usage_metadata.get("input_tokens") or 0),
            "output": int(usage_metadata.get("output_tokens") or 0),
        }

    # 兜底：response_metadata.token_usage（OpenAI 风格）
    response_metadata = getattr(response, "response_metadata", None) or {}
    usage = response_metadata.get("token_usage") or {}
    return {
        "input": int(usage.get("prompt_tokens") or 0),
        "output": int(usage.get("completion_tokens") or 0),
    }


# 可重试异常元组：底层 ChatOpenAI 失败时通常是连接 / 超时类错误，按本地化关键字判断
_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
)


__all__ = ["ModelRouter", "LiteLLMModelRouter"]


# 向后兼容别名（旧代码可能用这个名字 import）
LiteLLMModelRouter = ModelRouter
