"""
Agent 编排相关的异常层次。

迁移自 ``code-factory/src/core/exceptions.py``，**剔除** RAG / 文档加载
等无关异常，只保留 Agent / 模型路由两条主线。

所有异常都携带 ``correlation_id``，便于在分布式日志中关联同一请求。

异常树
------

::

    AgentFrameworkError
    ├── AgentExecutionError
    │   └── SchemaValidationError
    └── ModelRoutingError
        └── ModelTierExhaustedError

作者: yandc
"""
from __future__ import annotations

from typing import Optional


class AgentFrameworkError(Exception):
    """Agent 框架基础异常。

    所有运行时异常都应继承自此类，便于上层统一捕获。
    """

    def __init__(self, message: str, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id
        super().__init__(message)


# ---------------------------------------------------------------------------
# Agent 执行相关
# ---------------------------------------------------------------------------
class AgentExecutionError(AgentFrameworkError):
    """Agent 执行过程中发生的错误。"""


class SchemaValidationError(AgentExecutionError):
    """Agent 输出未通过 JSON Schema 校验。

    Attributes:
        agent_name: 校验失败的 Agent 名称。
        validation_errors: 校验失败的详细原因列表。
    """

    def __init__(
        self,
        agent_name: str,
        errors: list[str],
        correlation_id: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.validation_errors = errors
        super().__init__(
            f"Agent '{agent_name}' output validation failed: {errors}",
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# 模型路由相关
# ---------------------------------------------------------------------------
class ModelRoutingError(AgentFrameworkError):
    """模型路由层的通用错误（配置错误、不可重试错误等）。"""


class ModelTierExhaustedError(ModelRoutingError):
    """某一层级（local / cloud）所有候选模型均不可用。

    Attributes:
        tier: 已耗尽的层级名称。
        attempts: 累计尝试次数。
    """

    def __init__(
        self,
        tier: str,
        attempts: int,
        correlation_id: Optional[str] = None,
    ):
        self.tier = tier
        self.attempts = attempts
        super().__init__(
            f"All models in tier '{tier}' exhausted after {attempts} attempts",
            correlation_id=correlation_id,
        )


__all__ = [
    "AgentFrameworkError",
    "AgentExecutionError",
    "SchemaValidationError",
    "ModelRoutingError",
    "ModelTierExhaustedError",
]
