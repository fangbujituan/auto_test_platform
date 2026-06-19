"""
Reporter 框架基础：Protocol 定义。

引擎为每次 collection 执行依次发出三类事件：
- ``on_collection_started``  开始（创建 DB 行 / 打印开始横幅）
- ``on_step_completed``      每步完成（写 detail 行 / 增量打印）
- ``on_collection_finished`` 结束（更新汇总 / 打印总结）

任意 Reporter 实现 SHALL 满足：
- 所有钩子异常必须自吞，**不能**让 reporter 错误炸掉执行管道
- SequenceRunner 已经为此做了双重兜底（try/except 包钩子调用），但 reporter
  内部仍应自行处理异常，便于日志定位

作者: yandc
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.results import CollectionResult, StepResult
    from app.engine.api_engine.specs import CollectionSpec


@runtime_checkable
class Reporter(Protocol):
    """报告器协议（鸭子类型）。"""

    def on_collection_started(
        self,
        spec: CollectionSpec,
        ctx: ExecutionContext,
    ) -> None:
        """整批执行开始。"""

    def on_step_completed(
        self,
        step: StepResult,
        ctx: ExecutionContext,
    ) -> None:
        """单步执行完成。"""

    def on_collection_finished(
        self,
        result: CollectionResult,
        ctx: ExecutionContext,
    ) -> None:
        """整批执行结束。"""


class NoopReporter:
    """空实现：测试或无需 reporter 时使用，避免 None 判空。"""

    def on_collection_started(self, spec, ctx) -> None:  # noqa: ARG002
        return None

    def on_step_completed(self, step, ctx) -> None:  # noqa: ARG002
        return None

    def on_collection_finished(self, result, ctx) -> None:  # noqa: ARG002
        return None
