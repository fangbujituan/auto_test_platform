"""
AutomationDbReporter：把引擎执行结果写入 ``task_executions`` + ``task_execution_details``。

替代老 ``AutomationExecutor`` 中的写库逻辑，行为对齐：
- ``on_collection_started``  插入一行 ``TaskExecution(status='running')``，记 ``started_at``
- ``on_step_completed``      每步插一行 ``TaskExecutionDetail``
- ``on_collection_finished`` 更新 TaskExecution 的总数 / 状态 / 耗时 / 错误信息

外部访问入口：
- ``execution_id``           reporter 创建出来的执行记录 ID（由 AutomationExecutor.execute_task 拿来查实体返回）

设计要点：
- 每个钩子内部独立 commit；任何一个失败不影响后续步骤继续
- 异常自吞 + 日志，确保 reporter 不阻塞执行管道
- 引擎核心不感知 ORM；本 reporter 是引擎与 ``app/models/automation.py`` 的桥梁

作者: yandc
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from app.engine.api_engine.reporters._step_mapping import (
    compose_error_message,
    map_step_status,
)

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.results import CollectionResult, StepResult
    from app.engine.api_engine.specs import CollectionSpec

logger = logging.getLogger(__name__)


class AutomationDbReporter:
    """写 ``task_executions`` / ``task_execution_details`` 的 Reporter。"""

    def __init__(self, *, task_id: int, trigger_source: str = "manual"):
        self.task_id: int = task_id
        self.trigger_source: str = trigger_source
        # on_collection_started 后被填充；外部用它查实体返回
        self.execution_id: int | None = None

    # ------------------------------------------------------------------
    # Reporter Protocol 实现
    # ------------------------------------------------------------------

    def on_collection_started(
        self,
        spec: CollectionSpec,  # noqa: ARG002
        ctx: ExecutionContext,
    ) -> None:
        try:
            from app.models.automation import TaskExecution
            from app.models.base import db

            execution = TaskExecution(
                task_id=self.task_id,
                status="running",
                trigger_source=self.trigger_source,
                started_at=datetime.now(),
            )
            db.session.add(execution)
            db.session.commit()
            self.execution_id = execution.id
            logger.info(
                "[api_engine] AutomationDbReporter 创建 TaskExecution id=%s task_id=%s run_id=%s",
                execution.id, self.task_id, ctx.run_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[api_engine] on_collection_started 写入 TaskExecution 失败: %s", exc
            )
            self._safe_rollback()

    def on_step_completed(
        self,
        step: StepResult,
        ctx: ExecutionContext,
    ) -> None:
        if self.execution_id is None:
            logger.warning(
                "[api_engine] on_step_completed 跳过：execution_id 为空 run_id=%s step=%d",
                ctx.run_id, step.step_index,
            )
            return

        try:
            from app.models.automation import TaskExecutionDetail
            from app.models.base import db

            detail = TaskExecutionDetail(
                execution_id=self.execution_id,
                # 优先 case_id；若是 ad-hoc 通过 api 跑的也兼容（取 api_id）
                case_id=step.case_id if step.case_id is not None else step.api_id,
                case_name=step.name,
                status=map_step_status(step),
                actual_status=(step.response.status_code if step.response else None),
                actual_response=(step.response.body if step.response else None),
                duration=step.duration,
                error_message=compose_error_message(step),
            )
            db.session.add(detail)
            db.session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[api_engine] on_step_completed 写入 TaskExecutionDetail 失败 step=%d: %s",
                step.step_index, exc,
            )
            self._safe_rollback()

    def on_collection_finished(
        self,
        result: CollectionResult,
        ctx: ExecutionContext,
    ) -> None:
        if self.execution_id is None:
            logger.warning(
                "[api_engine] on_collection_finished 跳过：execution_id 为空 run_id=%s",
                ctx.run_id,
            )
            return

        try:
            from app.models.automation import TaskExecution
            from app.models.base import db

            execution = TaskExecution.query.get(self.execution_id)
            if execution is None:
                logger.warning(
                    "[api_engine] TaskExecution(id=%s) 不存在，无法更新", self.execution_id
                )
                return

            execution.status = "failed" if result.error_message else "completed"
            execution.finished_at = result.finished_at
            execution.duration = result.duration
            execution.total_cases = result.total
            execution.passed_count = result.passed
            execution.failed_count = result.failed
            execution.error_count = result.error
            execution.error_message = result.error_message
            db.session.commit()
            logger.info(
                "[api_engine] AutomationDbReporter 更新 TaskExecution(id=%s) "
                "status=%s total=%d passed=%d failed=%d error=%d",
                execution.id, execution.status,
                execution.total_cases, execution.passed_count,
                execution.failed_count, execution.error_count,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[api_engine] on_collection_finished 更新 TaskExecution 失败: %s", exc
            )
            self._safe_rollback()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_rollback() -> None:
        try:
            from app.models.base import db
            db.session.rollback()
        except Exception:  # pragma: no cover
            pass
