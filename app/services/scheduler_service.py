"""
Cron 调度服务。

使用 APScheduler (BackgroundScheduler) 管理定时任务，
使用 croniter 校验 Cron 表达式合法性。

作者: yandc
创建时间: 2026-01-20
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter

logger = logging.getLogger(__name__)


class SchedulerService:
    """Cron 调度管理服务。"""

    def __init__(self, app=None):
        self.scheduler = BackgroundScheduler()
        self._app = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        绑定 Flask app，启动调度器并从数据库恢复已有 cron 任务。
        """
        self._app = app

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler 已启动")

        # 从数据库恢复已有的 cron 任务
        self._restore_jobs(app)

    def add_cron_job(self, task_id, cron_expression):
        """
        添加或更新 cron 定时任务。

        如果该 task_id 对应的 job 已存在，则先移除再重新添加。

        Args:
            task_id: 自动化任务 ID
            cron_expression: 标准 5 段 cron 表达式
        """
        job_id = self._make_job_id(task_id)

        # 如果已存在则先移除
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

        trigger = self._parse_cron(cron_expression)
        self.scheduler.add_job(
            func=self._execute_task,
            trigger=trigger,
            id=job_id,
            args=[task_id],
            replace_existing=True,
        )
        logger.info(
            "已添加 cron 任务: task_id=%s, cron=%s",
            task_id, cron_expression,
        )

    def remove_job(self, task_id):
        """
        移除定时任务。

        Args:
            task_id: 自动化任务 ID
        """
        job_id = self._make_job_id(task_id)
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)
            logger.info("已移除 cron 任务: task_id=%s", task_id)

    @staticmethod
    def validate_cron(expression):
        """
        使用 croniter 校验 cron 表达式是否合法。

        Args:
            expression: cron 表达式字符串

        Returns:
            True 表示合法，False 表示非法
        """
        if not expression or not isinstance(expression, str):
            return False
        return croniter.is_valid(expression)

    # ------ 内部方法 ------

    @staticmethod
    def _make_job_id(task_id):
        """生成 APScheduler job ID。"""
        return f"automation_task_{task_id}"

    @staticmethod
    def _parse_cron(cron_expression):
        """将 5 段 cron 表达式解析为 APScheduler CronTrigger。"""
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Cron 表达式格式无效，需要 5 段: {cron_expression}"
            )
        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )

    def _execute_task(self, task_id):
        """
        调度器触发时的回调：在 Flask 应用上下文中执行任务。
        """
        if self._app is None:
            logger.error("Flask app 未绑定，无法执行任务 %s", task_id)
            return

        with self._app.app_context():
            try:
                from app.services.automation_executor import (
                    AutomationExecutor,
                    DuplicateExecutionError,
                )
                executor = AutomationExecutor()
                executor.execute_task(task_id)
                logger.info("Cron 触发执行完成: task_id=%s", task_id)
            except DuplicateExecutionError:
                logger.warning(
                    "Cron 触发跳过（任务正在执行中）: task_id=%s",
                    task_id,
                )
            except Exception:
                logger.exception(
                    "Cron 触发执行异常: task_id=%s", task_id,
                )

    def _restore_jobs(self, app):
        """从数据库恢复所有启用的 cron 类型任务到调度器。"""
        with app.app_context():
            try:
                from app.models.automation import AutomationTask
                tasks = AutomationTask.query.filter_by(
                    trigger_type="cron",
                    status=1,
                    is_deleted=0,
                ).all()

                for task in tasks:
                    if task.cron_expression and self.validate_cron(
                        task.cron_expression
                    ):
                        self.add_cron_job(
                            task.id, task.cron_expression
                        )

                logger.info(
                    "已从数据库恢复 %d 个 cron 任务", len(tasks),
                )
            except Exception:
                logger.exception("恢复 cron 任务失败")
