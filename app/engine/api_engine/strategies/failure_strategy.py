"""
失败策略：决定一个 step 失败后，SequenceRunner 是否应中断后续 step。

设计要点：
- 策略与 step 的 ``on_failure`` 字段配合：
  - ``stop``      该 step 失败 SHALL 立即中断（无论整体策略）
  - ``continue``  该 step 失败 SHALL 继续（无论整体策略）
  - ``inherit``   遵循整体策略（默认）
- 整体策略由 ``CollectionSpec.fail_strategy`` 决定，构造时翻译为对象。

未来扩展：``RetryStrategy``（重试 N 次后再判失败）、``DelayBackoffStrategy``。

作者: yandc
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.api_engine.results import StepResult
    from app.engine.api_engine.specs import RequestSpec


class FailureStrategy(ABC):
    """整体失败策略抽象。"""

    name: str = ""

    @abstractmethod
    def should_stop(self, step: StepResult, spec: RequestSpec) -> bool:
        """step 失败后是否应中断后续 step。

        子类实现 SHALL 先尊重 spec.on_failure 的显式值，再回退到自身策略。
        """


class ContinueOnError(FailureStrategy):
    """失败继续策略（默认）。

    - spec.on_failure == "stop"   → 中断
    - 其他                         → 继续
    """

    name = "continue"

    def should_stop(self, step: StepResult, spec: RequestSpec) -> bool:  # noqa: ARG002
        return spec.on_failure == "stop"


class FailFast(FailureStrategy):
    """快速失败策略。

    - spec.on_failure == "continue" → 继续
    - 其他（含 inherit）             → 中断
    """

    name = "fail_fast"

    def should_stop(self, step: StepResult, spec: RequestSpec) -> bool:  # noqa: ARG002
        return spec.on_failure != "continue"


def make_strategy(name: str | None) -> FailureStrategy:
    """字符串 → 策略对象的工厂。

    未识别名称时回退到 ``ContinueOnError``，与 CollectionSpec 默认值一致。
    """
    key = (name or "").lower()
    if key in ("fail_fast", "failfast", "stop"):
        return FailFast()
    return ContinueOnError()
