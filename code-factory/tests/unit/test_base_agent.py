"""agents/base_agent.py 文件中 BaseAgent 类的单元测试。

测试内容包括：
- execute() 模板方法：日志记录、计时、状态保存、历史记录
- validate_output()：包含必填字段和类型检查的模式验证
- 错误处理和 AgentExecutionError 传播
"""

import pytest

from agents.base_agent import BaseAgent
from src.core.exceptions import AgentExecutionError
from src.core.models import AgentState


# =============================================================================
# Concrete test subclass
# =============================================================================


class EchoAgent(BaseAgent):
    """Simple agent that copies input_data to output_data for testing."""

    @property
    def name(self) -> str:
        return "echo_agent"

    @property
    def output_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["result"],
            "properties": {
                "result": {"type": "string"},
            },
        }

    async def _process(self, state: AgentState) -> AgentState:
        state.output_data = {"result": state.input_data.get("message", "")}
        state.metadata["model_used"] = "test-model-v1"
        return state


class FailingAgent(BaseAgent):
    """Agent that always raises an error for testing error handling."""

    @property
    def name(self) -> str:
        return "failing_agent"

    async def _process(self, state: AgentState) -> AgentState:
        raise ValueError("Something went wrong")


class NoSchemaAgent(BaseAgent):
    """Agent with default (permissive) output schema."""

    @property
    def name(self) -> str:
        return "no_schema_agent"

    async def _process(self, state: AgentState) -> AgentState:
        state.output_data = {"anything": "goes"}
        return state


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_state() -> AgentState:
    return AgentState(
        task_id="task-001",
        correlation_id="corr-abc-123",
        workflow_id="wf-xyz-789",
        input_data={"message": "hello world"},
    )


@pytest.fixture
def echo_agent() -> EchoAgent:
    return EchoAgent()


@pytest.fixture
def failing_agent() -> FailingAgent:
    return FailingAgent()


@pytest.fixture
def no_schema_agent() -> NoSchemaAgent:
    return NoSchemaAgent()


# =============================================================================
# Tests: execute() template method
# =============================================================================


class TestExecuteMethod:
    """Tests for the execute() template method."""

    @pytest.mark.asyncio
    async def test_execute_returns_updated_state(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        assert result.output_data == {"result": "hello world"}

    @pytest.mark.asyncio
    async def test_execute_preserves_task_id(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        assert result.task_id == "task-001"

    @pytest.mark.asyncio
    async def test_execute_preserves_correlation_id(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        assert result.correlation_id == "corr-abc-123"

    @pytest.mark.asyncio
    async def test_execute_preserves_workflow_id(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        assert result.workflow_id == "wf-xyz-789"

    @pytest.mark.asyncio
    async def test_execute_appends_to_history(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        assert len(result.history) == 1
        entry = result.history[0]
        assert entry["agent_name"] == "echo_agent"
        assert entry["status"] == "completed"
        assert entry["model_used"] == "test-model-v1"
        assert "latency_ms" in entry
        assert entry["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_history_is_append_only(self, echo_agent, sample_state):
        # Pre-populate history
        sample_state.history = [{"agent_name": "previous_agent", "status": "completed"}]
        result = await echo_agent.execute(sample_state)
        assert len(result.history) == 2
        assert result.history[0] == {"agent_name": "previous_agent", "status": "completed"}
        assert result.history[1]["agent_name"] == "echo_agent"

    @pytest.mark.asyncio
    async def test_execute_history_entry_has_input_summary(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        entry = result.history[0]
        assert "input_summary" in entry
        assert "message" in entry["input_summary"]

    @pytest.mark.asyncio
    async def test_execute_history_entry_has_output_summary(self, echo_agent, sample_state):
        result = await echo_agent.execute(sample_state)
        entry = result.history[0]
        assert "output_summary" in entry
        assert "result" in entry["output_summary"]


# =============================================================================
# Tests: Error handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in execute()."""

    @pytest.mark.asyncio
    async def test_execute_raises_agent_execution_error(self, failing_agent, sample_state):
        with pytest.raises(AgentExecutionError) as exc_info:
            await failing_agent.execute(sample_state)
        assert "failing_agent" in str(exc_info.value)
        assert exc_info.value.correlation_id == "corr-abc-123"

    @pytest.mark.asyncio
    async def test_execute_failure_appends_to_history(self, failing_agent, sample_state):
        with pytest.raises(AgentExecutionError):
            await failing_agent.execute(sample_state)
        # History should have the failure entry
        assert len(sample_state.history) == 1
        entry = sample_state.history[0]
        assert entry["status"] == "failed"
        assert entry["agent_name"] == "failing_agent"
        assert "error" in entry


# =============================================================================
# Tests: validate_output()
# =============================================================================


class TestValidateOutput:
    """Tests for the validate_output() method."""

    def test_valid_output_returns_true(self, echo_agent, sample_state):
        sample_state.output_data = {"result": "valid string"}
        assert echo_agent.validate_output(sample_state) is True

    def test_missing_required_field_returns_false(self, echo_agent, sample_state):
        sample_state.output_data = {"other_field": "value"}
        assert echo_agent.validate_output(sample_state) is False

    def test_wrong_type_returns_false(self, echo_agent, sample_state):
        sample_state.output_data = {"result": 123}  # Should be string
        assert echo_agent.validate_output(sample_state) is False

    def test_non_dict_output_returns_false(self, echo_agent, sample_state):
        sample_state.output_data = "not a dict"  # type: ignore
        assert echo_agent.validate_output(sample_state) is False

    def test_default_schema_accepts_any_dict(self, no_schema_agent, sample_state):
        sample_state.output_data = {"anything": [1, 2, 3], "nested": {"a": "b"}}
        assert no_schema_agent.validate_output(sample_state) is True

    def test_default_schema_rejects_non_dict(self, no_schema_agent, sample_state):
        sample_state.output_data = [1, 2, 3]  # type: ignore
        assert no_schema_agent.validate_output(sample_state) is False

    def test_empty_dict_passes_default_schema(self, no_schema_agent, sample_state):
        sample_state.output_data = {}
        assert no_schema_agent.validate_output(sample_state) is True


# =============================================================================
# Tests: Agent name property
# =============================================================================


class TestAgentName:
    """Tests for the name property."""

    def test_echo_agent_name(self, echo_agent):
        assert echo_agent.name == "echo_agent"

    def test_failing_agent_name(self, failing_agent):
        assert failing_agent.name == "failing_agent"
