"""
Agent 编排过程中跨节点流转的状态对象与日志结构。

本模块只承载 **数据模型**（dataclass / Enum），不含任何业务逻辑。被
``orchestration.orchestrator`` / ``orchestration.base_agent`` 等运行时模块
共享使用。

迁移自 ``code-factory/src/core/models.py`` 中的 Agent Orchestrator 部分，
**剔除** RAG / 文档加载 / 向量存储相关字段——那些与本项目无关。

数据结构概览
------------

- :class:`WorkflowStatus`         工作流生命周期状态
- :class:`AgentState`             跨 Agent 流转的共享状态包
- :class:`AgentInvocationLog`     单次 Agent 调用的结构化日志条目

作者: yandc
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    """工作流生命周期状态。

    继承自 ``str`` 以便直接用于 JSON 序列化与比较。
    """

    PENDING = "pending"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentState:
    """跨 Agent 节点流转的共享状态包。

    设计原则
    --------
    1. ``task_id`` / ``correlation_id`` / ``workflow_id`` 是**不可变字段**，
       一旦由编排器创建后，任何 Agent 都不应修改它们；编排器会在每次
       Agent 执行后强制还原这三个字段（见 ``orchestrator._execute_agent_with_retry``）。
    2. ``input_data`` / ``output_data`` 由 Agent 自由读写，前者为输入，后者为产出。
    3. ``metadata`` 用于沉淀辅助信息（如 model_used、token_count、retry_attempt）。
    4. ``history`` 仅追加（append-only），由 BaseAgent 模板方法在每次执行后写入。
    """

    task_id: str
    correlation_id: str
    workflow_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentInvocationLog:
    """单次 Agent 调用的结构化日志条目。

    由 ``LangGraphOrchestrator`` 在每次 Agent 执行后写入，便于事后审计
    与 token 消耗分析。
    """

    agent_name: str
    input_summary: str
    output_summary: str
    model_used: str
    token_count: dict[str, int]   # {"input": N, "output": M}
    latency_ms: float
    status: str                    # success / validation_failed / schema_error / error
    correlation_id: str


__all__ = [
    "WorkflowStatus",
    "AgentState",
    "AgentInvocationLog",
]
