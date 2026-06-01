"""
LangGraph 风格的 Agent 工作流编排器。

提供 DAG 编排、条件边、状态保留、Schema 校验失败重试、完整调用日志
五大能力。本类不依赖 LangGraph 库本身（命名只是延续 code-factory 习惯），
保持零外部依赖，让单测和小流程可以零成本启动。

迁移自 ``code-factory/agents/orchestrator.py``：

- 把 ``structlog`` 替换为项目现有的 ``app.utils.debug.logs``
- 异常类型改为本项目的 ``AgentExecutionError`` / ``SchemaValidationError``
- 依赖从 ``src.core.*`` 改为 ``app.agents.orchestration.*``

核心保证
--------

1. **拓扑执行**：从 ``entry_point`` 开始 BFS，按 DAG 顺序执行 Agent
2. **条件边**：边可以挂一个 ``condition(state) -> bool`` 决定是否启用
3. **不可变字段保护**：每次 Agent 执行后强制还原 task_id / correlation_id / workflow_id
4. **History 仅追加**：禁止 Agent 删除历史记录
5. **校验失败最多重试 2 次**（共 3 次尝试），全部失败则把工作流标记为 FAILED
6. **完整调用日志**：每次 Agent 执行后产出 :class:`AgentInvocationLog`，可批量取出审计

作者: yandc
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.agents.orchestration.correlation import bind_correlation_id
from app.agents.orchestration.exceptions import (
    AgentExecutionError,
    SchemaValidationError,
)
from app.agents.orchestration.interfaces import (
    AgentInterface,
    OrchestratorInterface,
)
from app.agents.orchestration.state import (
    AgentInvocationLog,
    AgentState,
    WorkflowStatus,
)
from app.utils.debug import logs


# ---------------------------------------------------------------------------
# 工作流定义结构
# ---------------------------------------------------------------------------
@dataclass
class WorkflowEdge:
    """工作流 DAG 中的一条边。

    Attributes:
        target: 目标 Agent 名称
        condition: 可选的条件函数；返回 True 时本边才生效，None 表示无条件
    """

    target: str
    condition: Optional[Callable[[AgentState], bool]] = None


@dataclass
class WorkflowDefinition:
    """工作流定义。

    Attributes:
        name: 工作流唯一名称
        entry_point: 入口 Agent 名称
        edges: 邻接表 ``{agent_name: [WorkflowEdge, ...]}``
    """

    name: str
    entry_point: str
    edges: dict[str, list[WorkflowEdge]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------
class LangGraphOrchestrator(OrchestratorInterface):
    """基于 DAG 的多 Agent 工作流编排器。

    See module docstring for design details.
    """

    #: Schema 校验失败时的额外重试次数（不含首次执行）
    MAX_RETRIES: int = 2

    def __init__(self) -> None:
        self._agents: dict[str, AgentInterface] = {}
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._invocation_logs: list[AgentInvocationLog] = []

    # ------------------------------------------------------------------
    # 注册 API
    # ------------------------------------------------------------------
    def register_agent(self, name: str, agent: AgentInterface) -> None:
        """按名称注册 Agent。"""
        self._agents[name] = agent
        logs.info(f"[orchestrator] agent registered | name={name}")

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        """注册工作流定义。"""
        self._workflows[workflow.name] = workflow
        logs.info(
            f"[orchestrator] workflow registered | "
            f"name={workflow.name} entry={workflow.entry_point}"
        )

    # ------------------------------------------------------------------
    # 执行 API
    # ------------------------------------------------------------------
    async def run_workflow(
        self, workflow_name: str, initial_state: AgentState
    ) -> AgentState:
        """执行工作流，返回最终状态。

        采用 **运行时驱动** 调度：从 ``entry_point`` 开始，每个节点完成后
        用最新 state 重新评估出边的 condition，决定下一步走哪。这样条件
        边能感知到上游 Agent 的产出（例如审核闸的决策），实现真正意义
        上的"短路"与"分支"。

        Raises:
            AgentExecutionError: 工作流未注册 / 引用了未注册的 Agent
        """
        bind_correlation_id(initial_state.correlation_id)

        workflow = self._workflows.get(workflow_name)
        if workflow is None:
            raise AgentExecutionError(
                f"Workflow '{workflow_name}' not found",
                correlation_id=initial_state.correlation_id,
            )

        logs.info(
            f"[orchestrator] workflow start | "
            f"name={workflow_name} workflow_id={initial_state.workflow_id} "
            f"task_id={initial_state.task_id}"
        )

        state = initial_state
        visited: set[str] = set()
        current: Optional[str] = workflow.entry_point

        while current is not None:
            if current in visited:
                # 防御：DAG 不应有环；如果出现，停下来避免死循环
                logs.warning(
                    f"[orchestrator] cycle detected, stopping | "
                    f"agent={current} workflow={workflow_name}"
                )
                break
            visited.add(current)

            agent = self._agents.get(current)
            if agent is None:
                raise AgentExecutionError(
                    f"Agent '{current}' not registered",
                    correlation_id=state.correlation_id,
                )

            state, ok = await self._execute_agent_with_retry(current, agent, state)
            if not ok:
                logs.error(
                    f"[orchestrator] workflow failed | "
                    f"name={workflow_name} failed_agent={current} "
                    f"workflow_id={state.workflow_id}"
                )
                state.metadata["workflow_status"] = WorkflowStatus.FAILED.value
                state.metadata["failed_agent"] = current
                return state

            # 用最新 state 决定下一站
            current = self._next_agent(workflow, current, state, visited)

        state.metadata["workflow_status"] = WorkflowStatus.COMPLETED.value
        logs.info(
            f"[orchestrator] workflow completed | "
            f"name={workflow_name} workflow_id={state.workflow_id}"
        )
        return state

    def _next_agent(
        self,
        workflow: WorkflowDefinition,
        current: str,
        state: AgentState,
        visited: set[str],
    ) -> Optional[str]:
        """挑选下一个要执行的 Agent。

        遍历 ``current`` 的出边，返回第一个 condition 为 True（或
        condition 为 None）且尚未访问的目标。无满足条件的边时返回 None
        表示工作流结束。
        """
        for edge in workflow.edges.get(current, []):
            if edge.target in visited:
                continue
            if edge.condition is None or edge.condition(state):
                return edge.target
        return None

    def get_invocation_logs(self) -> list[AgentInvocationLog]:
        """返回本编排器实例累计的所有调用日志（拷贝）。"""
        return list(self._invocation_logs)

    # ------------------------------------------------------------------
    # 内部：单 Agent 执行 + 重试
    # ------------------------------------------------------------------
    async def _execute_agent_with_retry(
        self,
        agent_name: str,
        agent: AgentInterface,
        state: AgentState,
    ) -> tuple[AgentState, bool]:
        """执行单个 Agent，校验失败时最多重试 ``MAX_RETRIES`` 次。

        Returns:
            (updated_state, success_flag)
        """
        max_attempts = self.MAX_RETRIES + 1  # 1 + 2 = 3
        attempts = 0

        # 不可变字段快照（一旦本方法开始就锁定）
        immutable_task_id = state.task_id
        immutable_correlation_id = state.correlation_id
        immutable_workflow_id = state.workflow_id

        while attempts < max_attempts:
            attempts += 1
            start_ts = time.time()
            previous_history = list(state.history)

            try:
                new_state = await agent.execute(state)

                # 强制还原不可变字段
                new_state.task_id = immutable_task_id
                new_state.correlation_id = immutable_correlation_id
                new_state.workflow_id = immutable_workflow_id

                # 强制保证 history 仅追加
                if not self._history_preserves_previous(
                    previous_history, new_state.history
                ):
                    new_entries = new_state.history[len(previous_history):]
                    new_state.history = previous_history + new_entries

                latency_ms = (time.time() - start_ts) * 1000
                is_valid = agent.validate_output(new_state)

                if is_valid:
                    self._log_invocation(
                        agent_name=agent_name,
                        state=new_state,
                        latency_ms=latency_ms,
                        status="success",
                    )
                    return new_state, True

                # 校验未通过
                self._log_invocation(
                    agent_name=agent_name,
                    state=new_state,
                    latency_ms=latency_ms,
                    status="validation_failed",
                )

                if attempts < max_attempts:
                    logs.warning(
                        f"[orchestrator] output validation failed, retrying | "
                        f"agent={agent_name} attempt={attempts}/{max_attempts}"
                    )
                    # 重试时回到原始 state（避免脏数据被累积）
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
                    continue

                logs.error(
                    f"[orchestrator] output validation failed after retries | "
                    f"agent={agent_name} attempts={attempts}"
                )
                new_state.metadata["status"] = "failed"
                new_state.metadata["failure_reason"] = (
                    "schema_validation_failed_after_retries"
                )
                return new_state, False

            except SchemaValidationError as e:
                latency_ms = (time.time() - start_ts) * 1000
                self._log_invocation(
                    agent_name=agent_name,
                    state=state,
                    latency_ms=latency_ms,
                    status="schema_error",
                )

                if attempts < max_attempts:
                    logs.warning(
                        f"[orchestrator] schema error, retrying | "
                        f"agent={agent_name} attempt={attempts} "
                        f"errors={e.validation_errors}"
                    )
                    continue

                logs.error(
                    f"[orchestrator] schema error after retries | "
                    f"agent={agent_name} attempts={attempts} "
                    f"errors={e.validation_errors}"
                )
                state.metadata["status"] = "failed"
                state.metadata["failure_reason"] = (
                    "schema_validation_error_after_retries"
                )
                return state, False

            except Exception as e:  # noqa: BLE001
                latency_ms = (time.time() - start_ts) * 1000
                self._log_invocation(
                    agent_name=agent_name,
                    state=state,
                    latency_ms=latency_ms,
                    status="error",
                )
                logs.error(
                    f"[orchestrator] agent raised unexpected error | "
                    f"agent={agent_name} error={e}"
                )
                state.metadata["status"] = "failed"
                state.metadata["failure_reason"] = str(e)
                return state, False

        # 兜底（实际不会走到）
        return state, False

    # ------------------------------------------------------------------
    # 内部：辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _history_preserves_previous(
        previous: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> bool:
        """确认 ``current`` 以 ``previous`` 为前缀（即历史只增不删不改）。"""
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
        """把一次 Agent 调用沉淀到 ``self._invocation_logs``，并记结构化日志。"""
        model_used = state.metadata.get("model_used", "unknown")
        token_count = state.metadata.get(
            "token_count", {"input": 0, "output": 0}
        )

        log_entry = AgentInvocationLog(
            agent_name=agent_name,
            input_summary=self._summarize(state.input_data),
            output_summary=self._summarize(state.output_data),
            model_used=model_used,
            token_count=token_count,
            latency_ms=latency_ms,
            status=status,
            correlation_id=state.correlation_id,
        )
        self._invocation_logs.append(log_entry)

        logs.info(
            f"[orchestrator] invocation | "
            f"agent={log_entry.agent_name} status={log_entry.status} "
            f"model={log_entry.model_used} tokens={log_entry.token_count} "
            f"latency_ms={log_entry.latency_ms:.2f} "
            f"correlation_id={log_entry.correlation_id}"
        )

    @staticmethod
    def _summarize(data: dict[str, Any], max_length: int = 200) -> str:
        if not data:
            return "{}"
        text = str(data)
        if len(text) <= max_length:
            return text
        return text[: max_length] + "..."


__all__ = [
    "LangGraphOrchestrator",
    "WorkflowDefinition",
    "WorkflowEdge",
]
