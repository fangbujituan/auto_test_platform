"""
Correlation ID 上下文管理。

提供线程安全（基于 contextvars）的 correlation_id 传播能力，供 Agent
编排过程中跨节点串联日志、追踪同一次请求的所有调用。

迁移自 ``code-factory/src/core/logging.py`` 中的 contextvars 部分，
**剔除 structlog 依赖**——本项目统一使用 ``app.utils.debug.logs`` 桥接的
标准 logging，不引入新的日志栈。

使用方式
--------

    from app.agents.orchestration.correlation import (
        bind_correlation_id, get_correlation_id, clear_correlation_id,
    )

    bind_correlation_id("req-20260601-abc123")
    ...
    cid = get_correlation_id()  # -> "req-20260601-abc123"
    clear_correlation_id()

作者: yandc
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional


# 当前请求的 correlation_id；在异步任务和线程间通过 contextvars 安全传递
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


def bind_correlation_id(correlation_id: str) -> None:
    """把 correlation_id 绑定到当前上下文。

    Args:
        correlation_id: 当前请求的唯一标识符（建议使用 UUID 或时间戳前缀）。
    """
    _correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """获取当前上下文中的 correlation_id。

    Returns:
        当前 correlation_id，未绑定时返回 None。
    """
    return _correlation_id_ctx.get()


def clear_correlation_id() -> None:
    """清除当前上下文中的 correlation_id。"""
    _correlation_id_ctx.set(None)


__all__ = [
    "bind_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
]
