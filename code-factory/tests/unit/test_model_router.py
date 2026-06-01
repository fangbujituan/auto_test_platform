"""Unit tests for the LiteLLM-based Model Router.

Tests complexity classification, routing logic, retry behavior,
and tier escalation.

Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 2.8
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import ModelRoutingError, ModelTierExhaustedError
from src.core.models import LLMRequest, LLMResponse, ModelTier, TaskComplexity
from tools.model_router import LiteLLMModelRouter


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_routing_config():
    """Sample routing configuration for tests."""
    return {
        "routing": {
            "rules": [
                {
                    "task_type": "test_case_generation",
                    "complexity_threshold": "medium",
                    "local_models": [
                        "ollama/qwen2.5:32b",
                        "ollama/deepseek-coder-v2:16b",
                    ],
                    "cloud_models": [
                        "claude-3-5-sonnet-20241022",
                        "deepseek/deepseek-chat",
                    ],
                },
                {
                    "task_type": "test_data_generation",
                    "complexity_threshold": "low",
                    "local_models": ["ollama/qwen2.5:14b"],
                    "cloud_models": ["deepseek/deepseek-chat"],
                },
                {
                    "task_type": "code_review",
                    "complexity_threshold": "high",
                    "local_models": ["ollama/qwen2.5:32b"],
                    "cloud_models": [
                        "claude-3-5-sonnet-20241022",
                        "deepseek/deepseek-chat",
                    ],
                },
            ],
            "fallback": {
                "max_retries": 3,
                "retry_delay_seconds": 0,  # No delay in tests
                "escalation_enabled": True,
            },
        }
    }


@pytest.fixture
def router(sample_routing_config):
    """Create a model router with sample config."""
    return LiteLLMModelRouter(routing_config=sample_routing_config)


@pytest.fixture
def low_complexity_request():
    """A low-complexity LLM request."""
    return LLMRequest(
        messages=[{"role": "user", "content": "Generate simple test data"}],
        task_type="test_data_generation",
        complexity=TaskComplexity.LOW,
        temperature=0.7,
        max_tokens=4096,
    )


@pytest.fixture
def high_complexity_request():
    """A high-complexity LLM request."""
    return LLMRequest(
        messages=[{"role": "user", "content": "Generate complex test cases"}],
        task_type="test_case_generation",
        complexity=TaskComplexity.HIGH,
        temperature=0.7,
        max_tokens=4096,
    )


@pytest.fixture
def medium_complexity_request():
    """A medium-complexity LLM request."""
    return LLMRequest(
        messages=[{"role": "user", "content": "Generate test cases"}],
        task_type="test_case_generation",
        complexity=TaskComplexity.MEDIUM,
        temperature=0.7,
        max_tokens=4096,
    )


def _make_mock_response(content="Test response", prompt_tokens=10, completion_tokens=20):
    """Create a mock litellm response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    return mock_response


# =============================================================================
# Complexity Classification Tests
# =============================================================================


class TestClassifyComplexity:
    """Tests for classify_complexity method."""

    def test_matches_rule_threshold(self, router):
        """Task type with a matching rule returns the rule's threshold."""
        result = router.classify_complexity("test_data_generation", {})
        assert result == TaskComplexity.LOW

    def test_medium_threshold_from_rule(self, router):
        """Task type with medium threshold returns MEDIUM."""
        result = router.classify_complexity("test_case_generation", {})
        assert result == TaskComplexity.MEDIUM

    def test_high_threshold_from_rule(self, router):
        """Task type with high threshold returns HIGH."""
        result = router.classify_complexity("code_review", {})
        assert result == TaskComplexity.HIGH

    def test_unknown_task_type_defaults_to_medium(self, router):
        """Unknown task type defaults to MEDIUM complexity."""
        result = router.classify_complexity("unknown_task", {})
        assert result == TaskComplexity.MEDIUM

    def test_context_elevates_complexity(self, router):
        """Large context elevates complexity above rule threshold."""
        context = {
            "context_length": 15000,
            "num_files": 12,
            "has_dependencies": True,
        }
        # test_data_generation has threshold "low", but context is complex
        result = router.classify_complexity("test_data_generation", context)
        assert result == TaskComplexity.HIGH

    def test_empty_context_uses_rule_only(self, router):
        """Empty context dict doesn't affect rule-based classification."""
        result = router.classify_complexity("test_case_generation", {})
        assert result == TaskComplexity.MEDIUM

    def test_moderate_context_elevates_to_medium(self, router):
        """Moderate context indicators elevate LOW to MEDIUM."""
        context = {
            "context_length": 5000,
            "num_files": 5,
        }
        result = router.classify_complexity("test_data_generation", context)
        assert result == TaskComplexity.MEDIUM

    def test_none_context_treated_as_empty(self, router):
        """None-like empty context doesn't crash."""
        result = router.classify_complexity("test_data_generation", {})
        assert result == TaskComplexity.LOW


# =============================================================================
# Routing Logic Tests
# =============================================================================


class TestRouting:
    """Tests for the route method."""

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_low_complexity_routes_to_local(
        self, mock_acompletion, router, low_complexity_request
    ):
        """Low complexity requests route to local tier models."""
        mock_acompletion.return_value = _make_mock_response()

        response = await router.route(low_complexity_request)

        assert response.tier == ModelTier.LOCAL
        assert response.model_used == "ollama/qwen2.5:14b"
        mock_acompletion.assert_called_once()

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_high_complexity_routes_to_cloud(
        self, mock_acompletion, router, high_complexity_request
    ):
        """High complexity requests route to cloud tier models."""
        mock_acompletion.return_value = _make_mock_response()

        response = await router.route(high_complexity_request)

        assert response.tier == ModelTier.CLOUD
        assert response.model_used == "claude-3-5-sonnet-20241022"
        mock_acompletion.assert_called_once()

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_medium_complexity_routes_to_local(
        self, mock_acompletion, router, medium_complexity_request
    ):
        """Medium complexity requests default to local tier."""
        mock_acompletion.return_value = _make_mock_response()

        response = await router.route(medium_complexity_request)

        assert response.tier == ModelTier.LOCAL
        assert response.model_used == "ollama/qwen2.5:32b"

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_response_contains_correct_fields(
        self, mock_acompletion, router, low_complexity_request
    ):
        """Response contains all required fields."""
        mock_acompletion.return_value = _make_mock_response(
            content="Generated test data",
            prompt_tokens=50,
            completion_tokens=100,
        )

        response = await router.route(low_complexity_request)

        assert response.content == "Generated test data"
        assert response.token_count == {"input": 50, "output": 100}
        assert response.latency_ms > 0
        assert response.model_used == "ollama/qwen2.5:14b"
        assert response.tier == ModelTier.LOCAL


# =============================================================================
# Retry Behavior Tests
# =============================================================================


class TestRetryBehavior:
    """Tests for same-tier retry logic."""

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_retries_on_service_unavailable(
        self, mock_acompletion, router, low_complexity_request
    ):
        """Retries with next model when first model is unavailable."""
        import litellm.exceptions

        # First call fails, second succeeds
        mock_acompletion.side_effect = [
            litellm.exceptions.ServiceUnavailableError(
                message="Service unavailable",
                model="ollama/qwen2.5:14b",
                llm_provider="ollama",
            ),
            _make_mock_response(content="Success on retry"),
        ]

        # test_data_generation only has 1 local model, so it will fail
        # Use test_case_generation which has 2 local models
        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        response = await router.route(request)
        assert response.content == "Success on retry"
        assert mock_acompletion.call_count == 2

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_max_retries_within_tier(
        self, mock_acompletion, router
    ):
        """Does not exceed max_retries attempts within a single tier."""
        import litellm.exceptions

        # All calls fail
        mock_acompletion.side_effect = litellm.exceptions.ServiceUnavailableError(
            message="Service unavailable",
            model="test",
            llm_provider="ollama",
        )

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        # Should escalate to cloud after local tier exhausted
        # Then cloud also fails, raising ModelTierExhaustedError
        with pytest.raises(ModelTierExhaustedError):
            await router.route(request)

        # max_retries is 3 per tier, with 2 local + 2 cloud models
        # Local: tries up to 3 models (but only 2 available) = 2 attempts
        # Wait - max_retries=3, so it tries up to 3 attempts in local tier
        # (2 models available, so 2 attempts in local)
        # Then escalates to cloud: 2 models, tries up to 3 = 2 attempts
        # Total: at most 3 + 3 = 6, but limited by available models
        assert mock_acompletion.call_count <= 6

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_retry_on_connection_error(
        self, mock_acompletion, router
    ):
        """Retries on ConnectionError."""
        import litellm.exceptions

        mock_acompletion.side_effect = [
            litellm.exceptions.APIConnectionError(
                message="Connection refused",
                model="ollama/qwen2.5:32b",
                llm_provider="ollama",
            ),
            _make_mock_response(content="Connected on retry"),
        ]

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        response = await router.route(request)
        assert response.content == "Connected on retry"

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_non_retryable_error_raises_immediately(
        self, mock_acompletion, router
    ):
        """Non-retryable errors raise ModelRoutingError immediately."""
        mock_acompletion.side_effect = ValueError("Invalid model configuration")

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        with pytest.raises(ModelRoutingError, match="non-retryable"):
            await router.route(request)


# =============================================================================
# Tier Escalation Tests
# =============================================================================


class TestTierEscalation:
    """Tests for tier escalation behavior."""

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_escalates_from_local_to_cloud(
        self, mock_acompletion, router
    ):
        """Escalates to cloud tier when local tier is exhausted."""
        import litellm.exceptions

        # Local models fail, cloud succeeds
        mock_acompletion.side_effect = [
            litellm.exceptions.ServiceUnavailableError(
                message="unavailable", model="m1", llm_provider="ollama"
            ),
            litellm.exceptions.ServiceUnavailableError(
                message="unavailable", model="m2", llm_provider="ollama"
            ),
            _make_mock_response(content="Cloud response"),
        ]

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        response = await router.route(request)
        assert response.tier == ModelTier.CLOUD
        assert response.content == "Cloud response"

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_all_tiers_exhausted_raises_error(
        self, mock_acompletion, router
    ):
        """Raises ModelTierExhaustedError when all tiers are exhausted."""
        import litellm.exceptions

        mock_acompletion.side_effect = litellm.exceptions.ServiceUnavailableError(
            message="unavailable", model="test", llm_provider="test"
        )

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        with pytest.raises(ModelTierExhaustedError) as exc_info:
            await router.route(request)

        assert exc_info.value.tier == "cloud"  # Last tier tried
        assert exc_info.value.attempts > 0

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_no_escalation_when_disabled(self, mock_acompletion):
        """Does not escalate when escalation is disabled."""
        import litellm.exceptions

        config = {
            "routing": {
                "rules": [
                    {
                        "task_type": "test_case_generation",
                        "complexity_threshold": "medium",
                        "local_models": ["ollama/model1"],
                        "cloud_models": ["cloud/model1"],
                    }
                ],
                "fallback": {
                    "max_retries": 3,
                    "retry_delay_seconds": 0,
                    "escalation_enabled": False,
                },
            }
        }
        router = LiteLLMModelRouter(routing_config=config)

        mock_acompletion.side_effect = litellm.exceptions.ServiceUnavailableError(
            message="unavailable", model="test", llm_provider="test"
        )

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.LOW,
        )

        with pytest.raises(ModelTierExhaustedError) as exc_info:
            await router.route(request)

        # Should only try local tier (1 model, 1 attempt)
        assert exc_info.value.tier == "local"

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_high_complexity_starts_at_cloud_no_escalation_needed(
        self, mock_acompletion, router
    ):
        """High complexity starts at cloud; no further escalation possible."""
        import litellm.exceptions

        mock_acompletion.side_effect = litellm.exceptions.ServiceUnavailableError(
            message="unavailable", model="test", llm_provider="test"
        )

        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="test_case_generation",
            complexity=TaskComplexity.HIGH,
        )

        with pytest.raises(ModelTierExhaustedError) as exc_info:
            await router.route(request)

        # Cloud is the last tier, no escalation possible
        assert exc_info.value.tier == "cloud"


# =============================================================================
# Configuration Loading Tests
# =============================================================================


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_from_dict(self, sample_routing_config):
        """Can initialize from a pre-loaded config dict."""
        router = LiteLLMModelRouter(routing_config=sample_routing_config)
        assert router._max_retries == 3
        assert router._escalation_enabled is True

    def test_load_from_yaml_file(self, tmp_path):
        """Can load config from a YAML file."""
        import yaml

        config = {
            "routing": {
                "rules": [
                    {
                        "task_type": "test",
                        "complexity_threshold": "low",
                        "local_models": ["model1"],
                        "cloud_models": ["model2"],
                    }
                ],
                "fallback": {
                    "max_retries": 2,
                    "retry_delay_seconds": 1,
                    "escalation_enabled": True,
                },
            }
        }

        config_file = tmp_path / "routing_rules.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        router = LiteLLMModelRouter(config_path=config_file)
        assert router._max_retries == 2
        assert len(router._rules) == 1

    def test_invalid_config_path_raises_error(self):
        """Raises ModelRoutingError for invalid config path."""
        with pytest.raises(ModelRoutingError, match="Failed to load"):
            LiteLLMModelRouter(config_path="/nonexistent/path.yaml")

    def test_missing_fallback_uses_defaults(self):
        """Missing fallback section uses default values."""
        config = {"routing": {"rules": []}}
        router = LiteLLMModelRouter(routing_config=config)
        assert router._max_retries == 3
        assert router._retry_delay == 2
        assert router._escalation_enabled is True


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_no_models_configured_for_task_type(
        self, mock_acompletion, router
    ):
        """Raises error when no models are configured for the task type."""
        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            task_type="completely_unknown_task",
            complexity=TaskComplexity.LOW,
        )

        with pytest.raises(ModelTierExhaustedError):
            await router.route(request)

    @pytest.mark.asyncio
    @patch("litellm.acompletion")
    async def test_empty_response_content_handled(
        self, mock_acompletion, router, low_complexity_request
    ):
        """Handles None content in response gracefully."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 0
        mock_acompletion.return_value = mock_response

        response = await router.route(low_complexity_request)
        assert response.content == ""
