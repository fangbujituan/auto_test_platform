"""
SequenceRunner：collection 顺序执行驱动。

职责：
1. 调用 ``reporter.on_collection_started``
2. 逐 step 调用 ``StepExecutor.execute``
3. 每步完成调用 ``reporter.on_step_completed``
4. 按 ``FailureStrategy`` 决定是否中断（结合 step.spec.on_failure）
5. ``RequestSpec.delay_ms > 0`` 时在下一步前 sleep
6. 当 ``CollectionSpec.iterations > 1`` 时，整批步骤循环执行 N 次；fail_fast
   触发的中断会终止所有剩余迭代
7. 整批结束调用 ``reporter.on_collection_finished``，返回 ``CollectionResult``

设计要点：
- reporter 钩子异常**自吞** + 日志，不影响主流程
- 整批顶层 try/except，把未捕获异常落到 ``CollectionResult.error_message``

作者: yandc
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from app.engine.api_engine.results import CollectionResult, StepResult
from app.engine.api_engine.runner.step_executor import StepExecutor
from app.engine.api_engine.strategies.failure_strategy import FailureStrategy, make_strategy

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.http.client import HttpClient
    from app.engine.api_engine.reporters.base import Reporter
    from app.engine.api_engine.specs import CollectionSpec, RequestSpec

logger = logging.getLogger(__name__)


class SequenceRunner:
    """顺序执行多步的驱动。"""

    def __init__(
        self,
        *,
        http_client: HttpClient,
        strategy: FailureStrategy | None = None,
        reporters: list[Reporter] | None = None,
    ) -> None:
        self._step_executor = StepExecutor(http_client)
        self._strategy: FailureStrategy = strategy or make_strategy("continue")
        self._reporters: list[Reporter] = list(reporters or [])

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def run(self, spec: CollectionSpec, ctx: ExecutionContext) -> CollectionResult:
        """执行一个 collection。

        永不抛异常；任何顶层异常都落到 ``CollectionResult.error_message``。
        """
        # spec 自带的 fail_strategy 优先于构造时的默认策略
        strategy = make_strategy(spec.fail_strategy) if spec.fail_strategy else self._strategy

        iterations = max(1, int(spec.iterations or 1))

        started_at = datetime.now()
        steps: list[StepResult] = []
        error_message: str | None = None
        aborted = False

        logger.info(
            "[api_engine] run_id=%s collection=%s 开始 | strategy=%s, total=%d, iterations=%d",
            ctx.run_id, spec.name, strategy.name, len(spec.requests), iterations,
        )
        self._fire_started(spec, ctx)

        try:
            for iteration in range(iterations):
                if aborted:
                    break

                if iteration > 0 and iterations > 1:
                    logger.debug(
                        "[api_engine] run_id=%s collection=%s 进入第 %d/%d 轮",
                        ctx.run_id, spec.name, iteration + 1, iterations,
                    )

                for index, req_spec in enumerate(spec.requests):
                    step_result = self._step_executor.execute(
                        req_spec, ctx, step_index=index,
                    )
                    steps.append(step_result)
                    self._fire_step_completed(step_result, ctx)

                    # 失败策略判断
                    if not step_result.passed and strategy.should_stop(
                        step_result, req_spec
                    ):
                        logger.warning(
                            "[api_engine] run_id=%s 触发中断 iteration=%d step=%d "
                            "| strategy=%s, on_failure=%s",
                            ctx.run_id, iteration, index, strategy.name,
                            req_spec.on_failure,
                        )
                        aborted = True
                        break

                    # 步间延迟
                    if req_spec.delay_ms and req_spec.delay_ms > 0:
                        time.sleep(req_spec.delay_ms / 1000.0)
        except Exception as exc:  # noqa: BLE001  顶层兜底
            error_message = f"{exc.__class__.__name__}: {exc}"
            logger.exception(
                "[api_engine] run_id=%s collection 顶层异常: %s", ctx.run_id, exc
            )

        finished_at = datetime.now()
        result = self._summarize(
            spec=spec, ctx=ctx, steps=steps,
            started_at=started_at, finished_at=finished_at,
            iterations=iterations,
            strategy_name=strategy.name, error_message=error_message,
        )
        self._fire_collection_finished(result, ctx)
        logger.info(
            "[api_engine] run_id=%s collection=%s 结束 | total=%d passed=%d failed=%d error=%d",
            ctx.run_id, spec.name, result.total, result.passed, result.failed, result.error,
        )
        return result

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize(
        *,
        spec: CollectionSpec,
        ctx: ExecutionContext,
        steps: list[StepResult],
        started_at: datetime,
        finished_at: datetime,
        iterations: int,
        strategy_name: str,
        error_message: str | None,
    ) -> CollectionResult:
        """汇总各 step 状态到 CollectionResult。

        统计口径：
        - total = len(spec.requests) * iterations
        - passed = step.passed == True
        - error  = step.error 不为 None（断言失败但 HTTP 成功不算 error）
        - failed = !passed 且非 error
        - skipped = 中断后剩下未跑的步骤
        """
        total = len(spec.requests) * max(1, iterations)
        executed = len(steps)
        passed = sum(1 for s in steps if s.passed)
        error_cnt = sum(1 for s in steps if s.error is not None)
        failed = sum(1 for s in steps if not s.passed and s.error is None)
        skipped = max(0, total - executed)

        duration = (finished_at - started_at).total_seconds()
        return CollectionResult(
            run_id=ctx.run_id,
            name=spec.name,
            project_id=spec.project_id,
            environment_id=spec.environment_id,
            started_at=started_at,
            finished_at=finished_at,
            duration=duration,
            total=total,
            passed=passed,
            failed=failed,
            error=error_cnt,
            skipped=skipped,
            fail_strategy=strategy_name,
            steps=steps,
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # Reporter 钩子调用（自吞异常）
    # ------------------------------------------------------------------

    def _fire_started(self, spec: CollectionSpec, ctx: ExecutionContext) -> None:
        for reporter in self._reporters:
            try:
                reporter.on_collection_started(spec, ctx)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[api_engine] reporter %s on_collection_started 异常: %s",
                    reporter.__class__.__name__, exc,
                )

    def _fire_step_completed(self, step: StepResult, ctx: ExecutionContext) -> None:
        for reporter in self._reporters:
            try:
                reporter.on_step_completed(step, ctx)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[api_engine] reporter %s on_step_completed 异常: %s",
                    reporter.__class__.__name__, exc,
                )

    def _fire_collection_finished(
        self, result: CollectionResult, ctx: ExecutionContext
    ) -> None:
        for reporter in self._reporters:
            try:
                reporter.on_collection_finished(result, ctx)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[api_engine] reporter %s on_collection_finished 异常: %s",
                    reporter.__class__.__name__, exc,
                )
