"""Unit tests for the LangGraph-based Agent Orchestrator.

Tests cover:
- Agent registration
- Workflow registration and execution
- Structured state passing with immutable field preservation
- Output schema validation with retry logic
- Failure marking after retries exhausted
- Invocation logging completeness
- Conditional edges in DAG workflows
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.orchestrator import (
    LangGraphOrchestrator,
    WorkflowDefinition,
    WorkflowEdge,
)
from src.core.exceptions import AgentExecutionError, SchemaValidationError
from src.core.interfaces import AgentInterface
from src.core.models import AgentState, AgentInvocationLog, WorkflowStatus


# =============================================================================
# Test Fixtures
# =============================================================================


class MockAgent(AgentInterface):
    """A mock agent that returns a modified state."""

    def __init__(self, output_data=None, valid_output=True):
        self._output_data = output_data or {"result": "done"}
        self._valid_output = valid_output
        self.execute_count = 0

    async def execute(self, state: AgentState) -> AgentState:
        self.execute_count += 1
        new_state = AgentState(
            task_id=state.task_id,
            correlation_id=state.correlation_id,
            workflow_id=state.workflow_id,
            input_data=state.input_data,
            output_data=self._output_data,
            metadata={**state.metadata, "model_used": "test-model", "token_count": {"input": 10, "output": 20}},
            history=state.history + [{"agent": "mock", "action": "executed"}],
        )
        return new_state

    def validate_output(self, state: AgentState) -> bool:
        return self._valid_output


class FailingValidationAgent(AgentInterface):
    """Agent that fails validation N times then succeeds."""

    def __init__(self, fail_count=2):
        self._fail_count = fail_count
        self._call_count = 0

    async def execute(self, state: AgentState) -> AgentState:
        self._call_count += 1
        return AgentState(
            task_id=state.task_id,
            correlation_id=state.correlation_id,
            workflow_id=state.workflow_id,
            input_data=state.input_data,
            output_data={"result": f"attempt_{self._call_count}"},
            metadata={**state.metadata, "model_used": "test-model", "token_count": {"input": 5, "output": 5}},
            history=state.history + [{"attempt": self._call_count}],
        )

    def validate_output(self, state: AgentState) -> bool:
        return self._call_count > self._fail_count


class ExceptionAgent(AgentInterface):
    """Agent that raises SchemaValidationError."""

    def __init__(self, fail_count=3):
        self._fail_count = fail_count
        self._call_count = 0

    async def execute(self, state: AgentState) -> AgentState:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise SchemaValidationError(
                agent_name="exception_agent",
                errors=["field 'x' is required"],
                correlation_id=state.correlation_id,
            )
        return AgentState(
            task_id=state.task_id,
            correlation_id=state.correlation_id,
            workflow_id=state.workflow_id,
            input_data=state.input_data,
            output_data={"result": "recovered"},
            metadata=state.metadata,
            history=state.history,
        )

    def validate_output(self, state: AgentState) -> bool:
        return True


@pytest.fixture
def orchestrator():
    return LangGraphOrchestrator()


@pytest.fixture
def initial_state():
    return AgentState(
        task_id="task-001",
        correlation_id="corr-001",
        workflow_id="wf-001",
        input_data={"prompt": "generate test cases"},
    )


# =============================================================================
# Tests: Agent Registration
# =============================================================================


class TestAgentRegistration:
    def test_register_agent(self, orchestrator):
        agent = MockAgent()
        orchestrator.register_agent("test_agent", agent)
        assert "test_agent" in orchestrator._agents
        assert orchestrator._agents["test_agent"] is agent

    def test_register_multiple_agents(self, orchestrator):
        agent1 = MockAgent(output_data={"type": "a"})
        agent2 = MockAgent(output_data={"type": "b"})
        orchestrator.register_agent("agent_a", agent1)
        orchestrator.register_agent("agent_b", agent2)
        assert len(orchestrator._agents) == 2


# =============================================================================
# Tests: Workflow Registration and Execution
# =============================================================================


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self, orchestrator, initial_state):
        """Test a simple single-agent workflow."""
        agent = MockAgent(output_data={"test_cases": ["tc1", "tc2"]})
        orchestrator.register_agent("testcase_agent", agent)

        workflow = WorkflowDefinition(
            name="simple_workflow",
            entry_point="testcase_agent",
            edges={},
        )
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("simple_workflow", initial_state)

        assert result.output_data == {"test_cases": ["tc1", "tc2"]}
        assert result.metadata["workflow_status"] == WorkflowStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_multi_agent_workflow(self, orchestrator, initial_state):
        """Test a workflow with multiple agents in sequence."""
        agent_a = MockAgent(output_data={"step": "a_done"})
        agent_b = MockAgent(output_data={"step": "b_done"})

        orchestrator.register_agent("agent_a", agent_a)
        orchestrator.register_agent("agent_b", agent_b)

        workflow = WorkflowDefinition(
            name="multi_workflow",
            entry_point="agent_a",
            edges={
                "agent_a": [WorkflowEdge(target="agent_b")],
            },
        )
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("multi_workflow", initial_state)

        assert result.metadata["workflow_status"] == WorkflowStatus.COMPLETED.value
        # Both agents should have been executed
        assert agent_a.execute_count == 1
        assert agent_b.execute_count == 1

    @pytest.mark.asyncio
    async def test_workflow_not_found(self, orchestrator, initial_state):
        """Test that running a non-existent workflow raises an error."""
        with pytest.raises(AgentExecutionError, match="not found"):
            await orchestrator.run_workflow("nonexistent", initial_state)

    @pytest.mark.asyncio
    async def test_agent_not_registered(self, orchestrator, initial_state):
        """Test that referencing an unregistered agent raises an error."""
        workflow = WorkflowDefinition(
            name="bad_workflow",
            entry_point="missing_agent",
            edges={},
        )
        orchestrator.register_workflow(workflow)

        with pytest.raises(AgentExecutionError, match="not registered"):
            await orchestrator.run_workflow("bad_workflow", initial_state)


# =============================================================================
# Tests: State Passing and Immutable Fields (Requirement 3.3)
# =============================================================================


class TestStateIntegrity:
    @pytest.mark.asyncio
    async def test_immutable_fields_preserved(self, orchestrator, initial_state):
        """Immutable fields (task_id, correlation_id, workflow_id) must not change."""
        # Agent that tries to modify immutable fields
        class MutatingAgent(AgentInterface):
            async def execute(self, state: AgentState) -> AgentState:
                return AgentState(
                    task_id="MODIFIED",
                    correlation_id="MODIFIED",
                    workflow_id="MODIFIED",
                    input_data=state.input_data,
                    output_data={"mutated": True},
                    metadata={"model_used": "m", "token_count": {"input": 1, "output": 1}},
                    history=state.history,
                )

            def validate_output(self, state: AgentState) -> bool:
                return True

        orchestrator.register_agent("mutator", MutatingAgent())
        workflow = WorkflowDefinition(name="mut_wf", entry_point="mutator", edges={})
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("mut_wf", initial_state)

        # Immutable fields should be preserved from initial_state
        assert result.task_id == "task-001"
        assert result.correlation_id == "corr-001"
        assert result.workflow_id == "wf-001"

    @pytest.mark.asyncio
    async def test_history_is_append_only(self, orchestrator, initial_state):
        """History should only grow, never lose previous entries."""
        initial_state.history = [{"step": "initial"}]

        agent = MockAgent()
        orchestrator.register_agent("appender", agent)
        workflow = WorkflowDefinition(name="hist_wf", entry_point="appender", edges={})
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("hist_wf", initial_state)

        # Original history entry must still be present
        assert result.history[0] == {"step": "initial"}
        assert len(result.history) > 1


# =============================================================================
# Tests: Output Validation and Retry (Requirements 3.4, 3.5)
# =============================================================================


class TestValidationRetry:
    @pytest.mark.asyncio
    async def test_retry_on_validation_failure_then_succeed(self, orchestrator, initial_state):
        """Agent retries up to 2 times; succeeds on 2nd retry (3rd attempt)."""
        agent = FailingValidationAgent(fail_count=2)
        orchestrator.register_agent("retry_agent", agent)

        workflow = WorkflowDefinition(name="retry_wf", entry_point="retry_agent", edges={})
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("retry_wf", initial_state)

        assert result.metadata["workflow_status"] == WorkflowStatus.COMPLETED.value
        assert agent._call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_fail_after_all_retries_exhausted(self, orchestrator, initial_state):
        """Task marked as failed after all retries (3 attempts) produce invalid output."""
        agent = MockAgent(valid_output=False)
        orchestrator.register_agent("always_invalid", agent)

        workflow = WorkflowDefinition(name="fail_wf", entry_point="always_invalid", edges={})
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("fail_wf", initial_state)

        assert result.metadata["workflow_status"] == WorkflowStatus.FAILED.value
        assert result.metadata.get("failed_agent") == "always_invalid"
        assert agent.execute_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_on_schema_validation_exception(self, orchestrator, initial_state):
        """SchemaValidationError triggers retry logic."""
        # Fails 2 times then succeeds on 3rd
        agent = ExceptionAgent(fail_count=2)
        orchestrator.register_agent("exc_agent", agent)

        workflow = WorkflowDefinition(name="exc_wf", entry_point="exc_agent", edges={})
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("exc_wf", initial_state)

        assert result.metadata["workflow_status"] == WorkflowStatus.COMPLETED.value
        assert result.output_data == {"result": "recovered"}

    @pytest.mark.asyncio
    async def test_schema_exception_exhausts_retries(self, orchestrator, initial_state):
        """SchemaValidationError that persists marks task as failed."""
        agent = ExceptionAgent(fail_count=5)  # Always fails
        orchestrator.register_agent("always_exc", agent)

        workflow = WorkflowDefinition(name="exc_fail_wf", entry_point="always_exc", edges={})
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("exc_fail_wf", initial_state)

        assert result.metadata["workflow_status"] == WorkflowStatus.FAILED.value
        assert "schema_validation_error" in result.metadata.get("failure_reason", "")


# =============================================================================
# Tests: Invocation Logging (Requirement 3.6)
# =============================================================================


class TestInvocationLogging:
    @pytest.mark.asyncio
    async def test_log_entry_contains_all_required_fields(self, orchestrator, initial_state):
        """Each invocation log must have: agent_name, input_summary, output_summary,
        model_used, token_count, latency_ms."""
        agent = MockAgent()
        orchestrator.register_agent("logged_agent", agent)

        workflow = WorkflowDefinition(name="log_wf", entry_point="logged_agent", edges={})
        orchestrator.register_workflow(workflow)

        await orchestrator.run_workflow("log_wf", initial_state)

        logs = orchestrator.get_invocation_logs()
        assert len(logs) >= 1

        log = logs[0]
        assert log.agent_name == "logged_agent"
        assert log.input_summary  # non-empty
        assert log.output_summary  # non-empty
        assert log.model_used == "test-model"
        assert log.token_count == {"input": 10, "output": 20}
        assert log.latency_ms >= 0
        assert log.status == "success"
        assert log.correlation_id == "corr-001"

    @pytest.mark.asyncio
    async def test_failed_invocations_are_logged(self, orchestrator, initial_state):
        """Failed invocations (validation failures) should also be logged."""
        agent = MockAgent(valid_output=False)
        orchestrator.register_agent("fail_log_agent", agent)

        workflow = WorkflowDefinition(name="fail_log_wf", entry_point="fail_log_agent", edges={})
        orchestrator.register_workflow(workflow)

        await orchestrator.run_workflow("fail_log_wf", initial_state)

        logs = orchestrator.get_invocation_logs()
        # Should have 3 log entries (1 initial + 2 retries)
        assert len(logs) == 3
        for log in logs:
            assert log.status == "validation_failed"


# =============================================================================
# Tests: Conditional Edges (Requirement 3.2)
# =============================================================================


class TestConditionalEdges:
    @pytest.mark.asyncio
    async def test_conditional_edge_taken(self, orchestrator, initial_state):
        """Conditional edge is followed when condition returns True."""
        agent_a = MockAgent(output_data={"route": "b"})
        agent_b = MockAgent(output_data={"final": True})

        orchestrator.register_agent("cond_a", agent_a)
        orchestrator.register_agent("cond_b", agent_b)

        workflow = WorkflowDefinition(
            name="cond_wf",
            entry_point="cond_a",
            edges={
                "cond_a": [
                    WorkflowEdge(
                        target="cond_b",
                        condition=lambda s: True,
                    )
                ],
            },
        )
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("cond_wf", initial_state)

        assert agent_a.execute_count == 1
        assert agent_b.execute_count == 1

    @pytest.mark.asyncio
    async def test_conditional_edge_not_taken(self, orchestrator, initial_state):
        """Conditional edge is skipped when condition returns False."""
        agent_a = MockAgent(output_data={"route": "skip"})
        agent_b = MockAgent(output_data={"should_not_run": True})

        orchestrator.register_agent("skip_a", agent_a)
        orchestrator.register_agent("skip_b", agent_b)

        workflow = WorkflowDefinition(
            name="skip_wf",
            entry_point="skip_a",
            edges={
                "skip_a": [
                    WorkflowEdge(
                        target="skip_b",
                        condition=lambda s: False,
                    )
                ],
            },
        )
        orchestrator.register_workflow(workflow)

        result = await orchestrator.run_workflow("skip_wf", initial_state)

        assert agent_a.execute_count == 1
        assert agent_b.execute_count == 0  # Should not have been executed
