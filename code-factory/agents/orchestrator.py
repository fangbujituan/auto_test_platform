"""基于 LangGraph 的 Agent 编排器 / LangGraph-based Agent Orchestrator for Code Factory.

实现 DAG 工作流执行，支持：
Implements DAG workflow execution with:
- Agent 之间的条件边 / Conditional edges between agents
- 结构化状态传递 (AgentState) / Structured state passing (AgentState)
- 带重试逻辑的输出模式验证 / Output schema validation with retry logic
- 完整的调用日志记录 / Comprehensive invocation logging

需求 / Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import time
import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.core.exceptions import AgentExecutionError, SchemaValidationError
from src.core.interfaces import AgentInterface, OrchestratorInterface
from src.core.logging import get_logger, bind_correlation_id
from src.core.models import AgentInvocationLog, AgentState, WorkflowStatus


logger = get_logger("agents.orchestrator")


@dataclass
class WorkflowEdge:
    """表示工作流 DAG 中的一条边 / Represents an edge in the workflow DAG.

    边可以是无条件的（始终执行）或有条件的
    An edge can be either unconditional (always taken) or conditional
    （由检查当前状态的函数决定）。
    (determined by a function that inspects the current state).
    """

    target: str
    condition: Optional[Callable[[AgentState], bool]] = None


@dataclass
class WorkflowDefinition:
    """将工作流定义为带边的 Agent 名称 DAG / Defines a workflow as a DAG of agent names with edges.

    属性 / Attributes:
        name: 唯一的工作流名称 / Unique workflow name.
        entry_point: 第一个执行的 Agent / The first agent to execute.
        edges: agent_name → 出边列表的映射 / Mapping of agent_name → list of outgoing edges.
        agents_order: 可选的显式拓扑顺序。如果未提供，
                      编排器会从边计算它 / Optional explicit topological order. If not provided,
                      the orchestrator computes it from edges.
    """

    name: str
    entry_point: str
    edges: dict[str, list[WorkflowEdge]] = field(default_factory=dict)


class LangGraphOrchestrator(OrchestratorInterface):
    """基于 DAG 的多 Agent 工作流编排器 / DAG-based multi-agent workflow orchestrator.

    实现 OrchestratorInterface，支持：
    Implements the OrchestratorInterface with:
    - 按名称注册 Agent / Agent registration by name
    - 使用带条件边的 DAG 定义工作流 / Workflow definition as DAGs with conditional edges
    - 拓扑执行顺序 / Topological execution order
    - 保持不可变字段的结构化状态传递 / Structured state passing preserving immutable fields
    - 最多 2 次重试的输出模式验证 / Output schema validation with up to 2 retries
    - 完整的调用日志记录 / Comprehensive invocation logging
    """

    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._agents: dict[str, AgentInterface] = {}
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._invocation_logs: list[AgentInvocationLog] = []

    # =========================================================================
    # Public API
    # =========================================================================

    def register_agent(self, name: str, agent: AgentInterface) -> None:
        """Register an agent by name.

        Args:
            name: Unique agent identifier.
            agent: Agent instance implementing AgentInterface.
        """
        self._agents[name] = agent
        logger.info("Agent registered", agent_name=name)

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow definition.

        Args:
            workflow: The workflow DAG definition.
        """
        self._workflows[workflow.name] = workflow
        logger.info(
            "Workflow registered",
            workflow_name=workflow.name,
            entry_point=workflow.entry_point,
        )

    async def run_workflow(
        self, workflow_name: str, initial_state: AgentState
    ) -> AgentState:
        """Execute a complete workflow.

        Executes agents in topological order determined by the DAG,
        passing structured state between them. Validates output schema
        after each agent and retries up to 2 times on validation failure.

        Args:
            workflow_name: Name of the registered workflow to execute.
            initial_state: The initial AgentState to start the workflow.

        Returns:
            The final AgentState after all agents have executed.

        Raises:
            AgentExecutionError: If workflow is not found or agent is not registered.
        """
        # Bind correlation_id for log propagation
        bind_correlation_id(initial_state.correlation_id)

        workflow = self._workflows.get(workflow_name)
        if workflow is None:
            raise AgentExecutionError(
                f"Workflow '{workflow_name}' not found",
                correlation_id=initial_state.correlation_id,
            )

        logger.info(
            "Workflow execution started",
            workflow_name=workflow_name,
            workflow_id=initial_state.workflow_id,
            task_id=initial_state.task_id,
        )

        # Compute execution order via topological traversal
        execution_order = self._compute_execution_order(workflow, initial_state)

        state = initial_state
        workflow_status = WorkflowStatus.RUNNING

        for agent_name in execution_order:
            agent = self._agents.get(agent_name)
            if agent is None:
                raise AgentExecutionError(
                    f"Agent '{agent_name}' not registered",
                    correlation_id=state.correlation_id,
                )

            state, success = await self._execute_agent_with_retry(
                agent_name, agent, state
            )

            if not success:
                workflow_status = WorkflowStatus.FAILED
                logger.error(
                    "Workflow failed",
                    workflow_name=workflow_name,
                    failed_agent=agent_name,
                    workflow_id=state.workflow_id,
                )
                state.metadata["workflow_status"] = workflow_status.value
                state.metadata["failed_agent"] = agent_name
                return state

        workflow_status = WorkflowStatus.COMPLETED
        state.metadata["workflow_status"] = workflow_status.value

        logger.info(
            "Workflow execution completed",
            workflow_name=workflow_name,
            workflow_id=state.workflow_id,
            status=workflow_status.value,
        )

        return state

    def get_invocation_logs(self) -> list[AgentInvocationLog]:
        """Return all invocation logs recorded during workflow execution."""
        return list(self._invocation_logs)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _compute_execution_order(
        self, workflow: WorkflowDefinition, state: AgentState
    ) -> list[str]:
        """Compute the execution order by traversing the DAG from entry_point.

        Follows conditional edges based on current state. Uses BFS traversal
        to determine which agents to execute and in what order.

        Args:
            workflow: The workflow definition.
            state: Current agent state (used for evaluating conditional edges).

        Returns:
            Ordered list of agent names to execute.
        """
        visited: set[str] = set()
        order: list[str] = []
        queue: list[str] = [workflow.entry_point]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            order.append(current)

            # Get outgoing edges for the current agent
            edges = workflow.edges.get(current, [])
            for edge in edges:
                if edge.condition is None or edge.condition(state):
                    if edge.target not in visited:
                        queue.append(edge.target)

        return order

    async def _execute_agent_with_retry(
        self, agent_name: str, agent: AgentInterface, state: AgentState
    ) -> tuple[AgentState, bool]:
        """Execute an agent with retry logic on schema validation failure.

        Retries up to MAX_RETRIES (2) times if output validation fails.
        Marks the task as failed after all retries are exhausted.

        Args:
            agent_name: Name of the agent being executed.
            agent: The agent instance.
            state: Current workflow state.

        Returns:
            Tuple of (updated_state, success_flag).
        """
        attempts = 0
        max_attempts = self.MAX_RETRIES + 1  # initial + 2 retries = 3 total

        while attempts < max_attempts:
            attempts += 1
            start_time = time.time()

            try:
                # Preserve immutable fields
                immutable_task_id = state.task_id
                immutable_correlation_id = state.correlation_id
                immutable_workflow_id = state.workflow_id
                previous_history = list(state.history)

                # Execute the agent
                new_state = await agent.execute(state)

                # Enforce immutable field integrity (Requirement 3.3)
                new_state.task_id = immutable_task_id
                new_state.correlation_id = immutable_correlation_id
                new_state.workflow_id = immutable_workflow_id

                # Ensure history is append-only
                if len(new_state.history) < len(previous_history):
                    new_state.history = previous_history + new_state.history
                elif not self._history_preserves_previous(
                    previous_history, new_state.history
                ):
                    # Restore previous entries and append any new ones
                    new_entries = new_state.history[len(previous_history):]
                    new_state.history = previous_history + new_entries

                latency_ms = (time.time() - start_time) * 1000

                # Validate output schema (Requirement 3.4)
                is_valid = agent.validate_output(new_state)

                if is_valid:
                    # Log successful invocation
                    self._log_invocation(
                        agent_name=agent_name,
                        state=new_state,
                        latency_ms=latency_ms,
                        status="success",
                    )
                    return new_state, True
                else:
                    # Validation failed — log and potentially retry
                    self._log_invocation(
                        agent_name=agent_name,
                        state=new_state,
                        latency_ms=latency_ms,
                        status="validation_failed",
                    )

                    if attempts < max_attempts:
                        logger.warning(
                            "Agent output validation failed, retrying",
                            agent_name=agent_name,
                            attempt=attempts,
                            max_attempts=max_attempts,
                        )
                        # Use the original state for retry (not the invalid output)
                        state = AgentState(
                            task_id=immutable_task_id,
                            correlation_id=immutable_correlation_id,
                            workflow_id=immutable_workflow_id,
                            input_data=state.input_data,
                            output_data=state.output_data,
                            metadata={
                                **state.metadata,
                                "retry_attempt": attempts,
                            },
                            history=previous_history,
                        )
                    else:
                        # All retries exhausted — mark as failed (Requirement 3.5)
                        logger.error(
                            "Agent output validation failed after all retries",
                            agent_name=agent_name,
                            total_attempts=attempts,
                        )
                        new_state.metadata["status"] = "failed"
                        new_state.metadata["failure_reason"] = (
                            "schema_validation_failed_after_retries"
                        )
                        return new_state, False

            except SchemaValidationError as e:
                latency_ms = (time.time() - start_time) * 1000
                self._log_invocation(
                    agent_name=agent_name,
                    state=state,
                    latency_ms=latency_ms,
                    status="schema_error",
                )

                if attempts < max_attempts:
                    logger.warning(
                        "Schema validation error, retrying",
                        agent_name=agent_name,
                        attempt=attempts,
                        errors=e.validation_errors,
                    )
                else:
                    logger.error(
                        "Schema validation error after all retries",
                        agent_name=agent_name,
                        total_attempts=attempts,
                        errors=e.validation_errors,
                    )
                    state.metadata["status"] = "failed"
                    state.metadata["failure_reason"] = (
                        "schema_validation_error_after_retries"
                    )
                    return state, False

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                self._log_invocation(
                    agent_name=agent_name,
                    state=state,
                    latency_ms=latency_ms,
                    status="error",
                )
                logger.error(
                    "Agent execution failed with unexpected error",
                    agent_name=agent_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                state.metadata["status"] = "failed"
                state.metadata["failure_reason"] = str(e)
                return state, False

        # Should not reach here, but safety fallback
        return state, False

    def _history_preserves_previous(
        self, previous: list[dict[str, Any]], current: list[dict[str, Any]]
    ) -> bool:
        """Check that current history starts with all previous entries."""
        if len(current) < len(previous):
            return False
        return current[: len(previous)] == previous

    def _log_invocation(
        self,
        agent_name: str,
        state: AgentState,
        latency_ms: float,
        status: str,
    ) -> None:
        """Log an agent invocation with all required fields.

        Requirement 3.6: Log agent_name, input_summary, output_summary,
        model_used, token_count, latency_ms.

        Args:
            agent_name: Name of the invoked agent.
            state: The agent state (used to extract summaries and metadata).
            latency_ms: Execution duration in milliseconds.
            status: Invocation status (success, validation_failed, error).
        """
        # Extract model info from state metadata if available
        model_used = state.metadata.get("model_used", "unknown")
        token_count = state.metadata.get("token_count", {"input": 0, "output": 0})

        # Generate summaries (truncated for log readability)
        input_summary = self._summarize(state.input_data)
        output_summary = self._summarize(state.output_data)

        log_entry = AgentInvocationLog(
            agent_name=agent_name,
            input_summary=input_summary,
            output_summary=output_summary,
            model_used=model_used,
            token_count=token_count,
            latency_ms=latency_ms,
            status=status,
            correlation_id=state.correlation_id,
        )

        self._invocation_logs.append(log_entry)

        # Emit structured log
        logger.info(
            "Agent invocation logged",
            agent_name=log_entry.agent_name,
            input_summary=log_entry.input_summary,
            output_summary=log_entry.output_summary,
            model_used=log_entry.model_used,
            token_count=log_entry.token_count,
            latency_ms=log_entry.latency_ms,
            status=log_entry.status,
            correlation_id=log_entry.correlation_id,
        )

    def _summarize(self, data: dict[str, Any], max_length: int = 200) -> str:
        """Create a truncated string summary of a data dict.

        Args:
            data: Dictionary to summarize.
            max_length: Maximum character length for the summary.

        Returns:
            A string representation, truncated if necessary.
        """
        if not data:
            return "{}"
        text = str(data)
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
