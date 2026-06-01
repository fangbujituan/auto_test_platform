"""基于 LiteLLM 的模型路由器实现 / LiteLLM-based Model Router implementation.

根据任务复杂度将 LLM 请求路由到合适的模型，
Routes LLM requests to appropriate models based on task complexity,
支持同层级重试和资源耗尽时的层级升级。
with same-tier retry and tier escalation on exhaustion.

需求 / Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
"""

import asyncio
import time
from pathlib import Path
from typing import Any

import litellm
import yaml

from src.core.exceptions import ModelRoutingError, ModelTierExhaustedError
from src.core.interfaces import ModelRouterInterface
from src.core.logging import get_logger
from src.core.models import (
    LLMRequest,
    LLMResponse,
    ModelTier,
    TaskComplexity,
)

logger = get_logger("tools.model_router")

# Tier escalation order: LOCAL -> CLOUD
_TIER_ESCALATION_ORDER = [ModelTier.LOCAL, ModelTier.CLOUD]


class LiteLLMModelRouter(ModelRouterInterface):
    """使用 LiteLLM 进行统一 LLM 访问的模型路由器 / Model router using LiteLLM for unified LLM access.

    根据任务复杂度分类路由请求：
    Routes requests based on task complexity classification:
    - LOW 复杂度 → LOCAL 层级模型 / LOW complexity → LOCAL tier models
    - HIGH 复杂度 → CLOUD 层级模型 / HIGH complexity → CLOUD tier models
    - MEDIUM 复杂度 → 可配置（默认为 LOCAL）/ MEDIUM complexity → configurable (defaults to LOCAL)

    实现同层级重试（最多 3 次）和层级升级
    Implements same-tier retry (up to 3 attempts) and tier escalation
    当某个层级的所有模型都不可用时。
    when all models in a tier are exhausted.
    """

    def __init__(
        self,
        routing_config: dict[str, Any] | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """Initialize the model router.

        Args:
            routing_config: Pre-loaded routing configuration dict.
                If None, loads from config_path.
            config_path: Path to routing_rules.yaml.
                Defaults to 'config/routing_rules.yaml' if neither is provided.
        """
        if routing_config is not None:
            self._config = routing_config
        else:
            if config_path is None:
                config_path = Path("config/routing_rules.yaml")
            self._config = self._load_config(Path(config_path))

        self._rules = self._config.get("routing", {}).get("rules", [])
        self._fallback = self._config.get("routing", {}).get("fallback", {})
        self._max_retries = self._fallback.get("max_retries", 3)
        self._retry_delay = self._fallback.get("retry_delay_seconds", 2)
        self._escalation_enabled = self._fallback.get("escalation_enabled", True)

    @staticmethod
    def _load_config(config_path: Path) -> dict[str, Any]:
        """Load routing configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            Parsed configuration dictionary.

        Raises:
            ModelRoutingError: If the config file cannot be loaded.
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            raise ModelRoutingError(
                f"Failed to load routing config from '{config_path}': {e}"
            )

    def classify_complexity(self, task_type: str, context: dict) -> TaskComplexity:
        """Classify task complexity based on task_type and context.

        Classification logic:
        1. Match task_type against routing rules to find complexity_threshold
        2. Evaluate context indicators (size, nested structures, etc.)
        3. Return the higher of rule-based and context-based complexity
        4. Default to MEDIUM if no rule matches

        Args:
            task_type: The type of task (e.g., "test_case_generation").
            context: Additional context dict with complexity indicators.

        Returns:
            The classified TaskComplexity level.
        """
        # Step 1: Find matching rule for this task_type
        rule_complexity = self._get_rule_complexity(task_type)

        # Step 2: Evaluate context-based complexity
        context_complexity = self._evaluate_context_complexity(context)

        # Step 3: Return the higher complexity level
        complexity_order = {
            TaskComplexity.LOW: 0,
            TaskComplexity.MEDIUM: 1,
            TaskComplexity.HIGH: 2,
        }

        if complexity_order.get(context_complexity, 1) > complexity_order.get(
            rule_complexity, 1
        ):
            return context_complexity

        return rule_complexity

    def _get_rule_complexity(self, task_type: str) -> TaskComplexity:
        """Get complexity from routing rules for a given task_type.

        Args:
            task_type: The task type to look up.

        Returns:
            TaskComplexity from the matching rule, or MEDIUM if no match.
        """
        for rule in self._rules:
            if rule.get("task_type") == task_type:
                threshold = rule.get("complexity_threshold", "medium")
                return self._parse_complexity(threshold)
        return TaskComplexity.MEDIUM

    def _evaluate_context_complexity(self, context: dict) -> TaskComplexity:
        """Evaluate complexity based on context indicators.

        Indicators considered:
        - context_length: number of tokens/chars in context
        - num_files: number of files involved
        - has_dependencies: whether cross-file dependencies exist
        - language_count: number of programming languages involved

        Args:
            context: Dict with complexity indicator fields.

        Returns:
            Inferred TaskComplexity from context analysis.
        """
        if not context:
            return TaskComplexity.LOW

        score = 0

        # Context length indicator
        context_length = context.get("context_length", 0)
        if context_length > 10000:
            score += 2
        elif context_length > 3000:
            score += 1

        # Number of files indicator
        num_files = context.get("num_files", 0)
        if num_files > 10:
            score += 2
        elif num_files > 3:
            score += 1

        # Cross-file dependencies
        if context.get("has_dependencies", False):
            score += 1

        # Multiple languages
        language_count = context.get("language_count", 1)
        if language_count > 2:
            score += 1

        # Map score to complexity
        if score >= 4:
            return TaskComplexity.HIGH
        elif score >= 2:
            return TaskComplexity.MEDIUM
        return TaskComplexity.LOW

    def _parse_complexity(self, value: str) -> TaskComplexity:
        """Parse a string complexity value into TaskComplexity enum.

        Args:
            value: String like "low", "medium", "high".

        Returns:
            Corresponding TaskComplexity enum value.
        """
        mapping = {
            "low": TaskComplexity.LOW,
            "medium": TaskComplexity.MEDIUM,
            "high": TaskComplexity.HIGH,
        }
        return mapping.get(value.lower(), TaskComplexity.MEDIUM)

    def _get_tier_for_complexity(self, complexity: TaskComplexity) -> ModelTier:
        """Determine which tier to use for a given complexity level.

        Args:
            complexity: The task complexity.

        Returns:
            The target ModelTier.
        """
        if complexity == TaskComplexity.LOW:
            return ModelTier.LOCAL
        elif complexity == TaskComplexity.HIGH:
            return ModelTier.CLOUD
        else:
            # MEDIUM defaults to LOCAL (local-first strategy)
            return ModelTier.LOCAL

    def _get_models_for_tier(
        self, task_type: str, tier: ModelTier
    ) -> list[str]:
        """Get the ordered list of models for a task_type and tier.

        Args:
            task_type: The task type to look up.
            tier: The model tier (LOCAL or CLOUD).

        Returns:
            List of model identifiers in priority order.
        """
        for rule in self._rules:
            if rule.get("task_type") == task_type:
                if tier == ModelTier.LOCAL:
                    return rule.get("local_models", [])
                else:
                    return rule.get("cloud_models", [])

        # No matching rule - return empty list
        return []

    async def route(self, request: LLMRequest) -> LLMResponse:
        """Route an LLM request to the appropriate model.

        Routing logic:
        1. Classify complexity (if not already determined from request)
        2. Select initial tier based on complexity
        3. Try models in the selected tier in priority order
        4. On failure: retry same tier (up to max_retries total attempts)
        5. If tier exhausted and escalation enabled: escalate to next tier
        6. If all tiers exhausted: raise ModelTierExhaustedError

        Args:
            request: The LLM request to route.

        Returns:
            LLMResponse with the model's output.

        Raises:
            ModelTierExhaustedError: If all models in all tiers are exhausted.
            ModelRoutingError: If routing fails for other reasons.
        """
        complexity = request.complexity
        initial_tier = self._get_tier_for_complexity(complexity)

        # Determine tier order for escalation
        tier_order = self._get_escalation_order(initial_tier)

        total_attempts = 0

        for tier in tier_order:
            models = self._get_models_for_tier(request.task_type, tier)

            if not models:
                logger.debug(
                    "No models configured for tier",
                    tier=tier.value,
                    task_type=request.task_type,
                )
                continue

            # Try models in this tier (up to max_retries total attempts for this tier)
            tier_attempts = 0
            for model in models:
                if tier_attempts >= self._max_retries:
                    break

                tier_attempts += 1
                total_attempts += 1

                try:
                    response = await self._call_model(request, model, tier)
                    return response
                except (litellm.exceptions.ServiceUnavailableError,
                        litellm.exceptions.APIConnectionError,
                        litellm.exceptions.Timeout,
                        litellm.exceptions.RateLimitError,
                        ConnectionError,
                        TimeoutError) as e:
                    logger.warning(
                        "Model endpoint unavailable, retrying",
                        model=model,
                        tier=tier.value,
                        attempt=tier_attempts,
                        max_retries=self._max_retries,
                        error=str(e),
                    )
                    # Add delay between retries
                    if tier_attempts < self._max_retries:
                        await asyncio.sleep(self._retry_delay)
                    continue
                except Exception as e:
                    # Non-retryable error
                    raise ModelRoutingError(
                        f"Model call failed with non-retryable error: {e}"
                    )

            # Tier exhausted - log warning and try escalation
            if tier != tier_order[-1] and self._escalation_enabled:
                logger.warning(
                    "All models in tier exhausted, escalating to next tier",
                    exhausted_tier=tier.value,
                    attempts=tier_attempts,
                    task_type=request.task_type,
                )

        # All tiers exhausted
        raise ModelTierExhaustedError(
            tier=tier_order[-1].value,
            attempts=total_attempts,
        )

    def _get_escalation_order(self, initial_tier: ModelTier) -> list[ModelTier]:
        """Get the tier escalation order starting from the initial tier.

        Args:
            initial_tier: The tier to start with.

        Returns:
            Ordered list of tiers to try.
        """
        if not self._escalation_enabled:
            return [initial_tier]

        # Start from the initial tier and include subsequent tiers
        try:
            start_idx = _TIER_ESCALATION_ORDER.index(initial_tier)
            return _TIER_ESCALATION_ORDER[start_idx:]
        except ValueError:
            return [initial_tier]

    async def _call_model(
        self, request: LLMRequest, model: str, tier: ModelTier
    ) -> LLMResponse:
        """Call a specific model via LiteLLM.

        Args:
            request: The LLM request.
            model: The model identifier (e.g., "ollama/qwen2.5:32b").
            tier: The tier this model belongs to.

        Returns:
            LLMResponse with the model's output.

        Raises:
            Various litellm exceptions on failure.
        """
        start_time = time.perf_counter()

        response = await litellm.acompletion(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Extract token usage
        usage = response.usage
        token_count = {
            "input": usage.prompt_tokens if usage else 0,
            "output": usage.completion_tokens if usage else 0,
        }

        content = response.choices[0].message.content or ""

        logger.info(
            "Model call completed",
            model=model,
            tier=tier.value,
            task_type=request.task_type,
            latency_ms=round(elapsed_ms, 2),
            input_tokens=token_count["input"],
            output_tokens=token_count["output"],
        )

        return LLMResponse(
            content=content,
            model_used=model,
            tier=tier,
            token_count=token_count,
            latency_ms=elapsed_ms,
        )
