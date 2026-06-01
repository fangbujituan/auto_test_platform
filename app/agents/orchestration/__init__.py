"""
Agent 编排层。

承载 DAG 编排引擎与 Agent 模板基类。

公开符号
--------

数据 / 状态：
- :class:`AgentState`              跨 Agent 流转的共享状态
- :class:`AgentInvocationLog`      单次调用的结构化日志
- :class:`WorkflowStatus`          工作流生命周期状态

接口 / 异常：
- :class:`AgentInterface`          Agent 抽象接口
- :class:`OrchestratorInterface`   编排器抽象接口
- :class:`AgentExecutionError`     Agent 执行异常
- :class:`SchemaValidationError`   输出 Schema 校验失败

实现：
- :class:`BaseAgent`               所有业务 Agent 的模板方法基类
- :class:`LangGraphOrchestrator`   DAG 编排器实现
- :class:`WorkflowDefinition`      工作流定义
- :class:`WorkflowEdge`            条件 / 无条件边

工具：
- :func:`bind_correlation_id`      把 correlation_id 绑到当前上下文
- :func:`get_correlation_id`       取当前上下文中的 correlation_id
- :func:`clear_correlation_id`     清除当前上下文中的 correlation_id

作者: yandc
"""
from app.agents.orchestration.base_agent import BaseAgent
from app.agents.orchestration.correlation import (
    bind_correlation_id,
    clear_correlation_id,
    get_correlation_id,
)
from app.agents.orchestration.exceptions import (
    AgentExecutionError,
    AgentFrameworkError,
    SchemaValidationError,
)
from app.agents.orchestration.interfaces import (
    AgentInterface,
    OrchestratorInterface,
)
from app.agents.orchestration.orchestrator import (
    LangGraphOrchestrator,
    WorkflowDefinition,
    WorkflowEdge,
)
from app.agents.orchestration.state import (
    AgentInvocationLog,
    AgentState,
    WorkflowStatus,
)

__all__ = [
    # 数据 / 状态
    "AgentState",
    "AgentInvocationLog",
    "WorkflowStatus",
    # 接口 / 异常
    "AgentInterface",
    "OrchestratorInterface",
    "AgentFrameworkError",
    "AgentExecutionError",
    "SchemaValidationError",
    # 实现
    "BaseAgent",
    "LangGraphOrchestrator",
    "WorkflowDefinition",
    "WorkflowEdge",
    # 工具
    "bind_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
]
