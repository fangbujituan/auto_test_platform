"""
StepResult → DB 行 的字段映射工具（reporter 共用）。

下划线前缀表示内部模块，不在 ``reporters/__init__.py`` 中导出。
``AutomationDbReporter`` 与 ``TestResultDbReporter`` 共享这两个函数，
确保 ``task_execution_details`` 与 ``test_results`` 的状态/错误消息口径完全一致。

作者: yandc
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.api_engine.results import StepResult


def map_step_status(step: StepResult) -> str:
    """``StepResult`` → 历史状态字符串（passed / failed / error）。

    映射：
    - ``step.error`` 非空     → ``"error"``
    - ``step.passed`` 为 True → ``"passed"``
    - 否则                    → ``"failed"``

    与老 ``AutomationExecutor`` / ``TestExecutor`` 的状态语义一致。
    """
    if step.error is not None:
        return "error"
    return "passed" if step.passed else "failed"


def compose_error_message(step: StepResult) -> str | None:
    """把 step 的错误/失败断言汇总成一条 error_message。

    优先级：
    1. ``step.error``（HTTP / 抽取 / 引擎层错误）
    2. 失败断言列表：``[type] 名称: 消息`` 用 ``"; "`` 拼接
    3. ``None``
    """
    if step.error:
        return step.error if not step.error_type else f"[{step.error_type}] {step.error}"

    failed_assertions = [a for a in step.assertions if not a.passed]
    if failed_assertions:
        parts = [
            f"[{a.type}] {a.name or a.type}: {a.message}"
            for a in failed_assertions
        ]
        return "; ".join(parts)

    return None
