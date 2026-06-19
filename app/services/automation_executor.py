"""
自动化任务执行入口。

Phase 3 起内部委托给 ``app.engine.api_engine.ApiEngine.run_automation_task``，
对外接口（``execute_task`` / ``DuplicateExecutionError``）**完全不变**：

- 路由层、调度器、Webhook 一行代码不用改
- 历史 ``task_executions`` / ``task_execution_details`` 字段语义保持一致
  （写库由 ``AutomationDbReporter`` 接管）

历史的 ``_execute_cases`` / ``_prepare_case`` / ``_summarize`` 方法已被引擎吸收，
本文件只保留：
- ``execute_task``         对外稳定签名
- ``_check_running``       重复触发保护（在调用引擎之前完成）
- ``DuplicateExecutionError`` 老异常类型

作者: yandc
创建时间: 2026-01-20（Phase 3 重构）
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime

from app.engine.api_engine import LoaderError, get_api_engine
from app.models.automation import AutomationTask, TaskExecution
from app.models.base import db

logger = logging.getLogger(__name__)


class AutomationExecutor:
    """自动化任务执行入口（薄壳）。"""

    def __init__(self, timeout: int = 30):
        # 保留构造参数兼容老代码；超时实际由引擎默认 HttpClient 控制。
        self.timeout = timeout

    def execute_task(
        self,
        task_id: int,
        environment_id: int | None = None,
        trigger_source: str = "manual",
    ) -> TaskExecution:
        """执行自动化任务，返回 ``TaskExecution`` 实体。

        Args:
            task_id:        ``automation_tasks.id``
            environment_id: 覆盖任务默认环境；为 None 时使用 ``task.environment_id``
            trigger_source: ``manual / cron / webhook``

        Raises:
            DuplicateExecutionError: 任务正在执行中
            ValueError:              任务不存在
        """
        # 1. 重复触发保护（与历史行为一致，在调用引擎之前）
        if self._check_running(task_id):
            raise DuplicateExecutionError("任务正在执行中，请勿重复触发")

        # 2. 任务存在性校验（与历史行为一致）
        task = AutomationTask.query.get(task_id)
        if not task:
            raise ValueError(f"自动化任务不存在: {task_id}")

        # 3. 委托引擎；引擎内部由 AutomationDbReporter 写库，最后查实体返回
        try:
            engine = get_api_engine()
            execution = engine.run_automation_task(
                task_id=task_id,
                environment_id=environment_id,
                trigger_source=trigger_source,
            )
            return execution

        except DuplicateExecutionError:
            raise
        except LoaderError as exc:
            # 与历史行为对齐：找不到任务统一抛 ValueError
            raise ValueError(exc.message) from exc
        except Exception as exc:  # noqa: BLE001 顶层兜底
            # 引擎内部 reporter 已经做了多层 try/except 与事务回滚；
            # 这里只对"reporter 也崩了"的极端情况做最后兜底，写一条 failed 记录返回，
            # 与老 AutomationExecutor 的"except Exception" 兜底语义对齐。
            logger.exception(
                "[AutomationExecutor] 引擎执行未捕获异常 task_id=%s: %s",
                task_id, exc,
            )
            return self._record_emergency_failure(
                task_id=task_id,
                trigger_source=trigger_source,
                error=traceback.format_exc(),
            )

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _check_running(task_id: int) -> bool:
        """检查任务是否正在执行中，防止重复执行。"""
        running = TaskExecution.query.filter_by(
            task_id=task_id, status="running"
        ).first()
        return running is not None

    @staticmethod
    def _record_emergency_failure(
        *,
        task_id: int,
        trigger_source: str,
        error: str,
    ) -> TaskExecution:
        """极端兜底：reporter 也崩了，手动写一条 failed 行返回。"""
        try:
            db.session.rollback()
        except Exception:  # pragma: no cover
            pass

        execution = TaskExecution(
            task_id=task_id,
            status="failed",
            trigger_source=trigger_source,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration=0,
            total_cases=0,
            passed_count=0,
            failed_count=0,
            error_count=0,
            error_message=error,
        )
        db.session.add(execution)
        db.session.commit()
        return execution


class DuplicateExecutionError(Exception):
    """任务正在执行中，拒绝重复执行。"""
    pass
