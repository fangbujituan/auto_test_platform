"""
SchedulerService 单元测试。

验证 cron 表达式校验、任务添加/移除、数据库恢复等核心功能。
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.scheduler_service import SchedulerService


class TestValidateCron:
    """validate_cron 静态方法测试。"""

    def test_valid_standard_expressions(self):
        """合法的标准 5 段 cron 表达式应返回 True。"""
        valid = [
            "* * * * *",
            "0 0 * * *",
            "*/5 * * * *",
            "0 9 * * 1-5",
            "30 2 1 * *",
            "0 0 1 1 *",
        ]
        for expr in valid:
            assert SchedulerService.validate_cron(expr) is True, (
                f"应为合法: {expr}"
            )

    def test_invalid_expressions(self):
        """非法的 cron 表达式应返回 False。"""
        invalid = [
            "",
            "not a cron",
            "60 * * * *",
            "* 25 * * *",
            "* * 32 * *",
            "* * * 13 *",
        ]
        for expr in invalid:
            assert SchedulerService.validate_cron(expr) is False, (
                f"应为非法: {expr}"
            )

    def test_none_and_non_string(self):
        """None 和非字符串输入应返回 False。"""
        assert SchedulerService.validate_cron(None) is False
        assert SchedulerService.validate_cron(123) is False
        assert SchedulerService.validate_cron([]) is False


class TestAddAndRemoveJob:
    """add_cron_job / remove_job 测试。"""

    def test_add_cron_job_registers_job(self):
        """添加 cron 任务后，调度器中应存在对应 job。"""
        svc = SchedulerService()
        svc.scheduler.start()
        try:
            svc.add_cron_job(42, "*/10 * * * *")
            job = svc.scheduler.get_job("automation_task_42")
            assert job is not None
        finally:
            svc.scheduler.shutdown(wait=False)

    def test_add_cron_job_replaces_existing(self):
        """重复添加同一 task_id 应替换而非重复。"""
        svc = SchedulerService()
        svc.scheduler.start()
        try:
            svc.add_cron_job(1, "0 0 * * *")
            svc.add_cron_job(1, "0 6 * * *")
            jobs = svc.scheduler.get_jobs()
            matching = [
                j for j in jobs
                if j.id == "automation_task_1"
            ]
            assert len(matching) == 1
        finally:
            svc.scheduler.shutdown(wait=False)

    def test_remove_job_removes_existing(self):
        """移除已存在的 job 后，调度器中不应再有该 job。"""
        svc = SchedulerService()
        svc.scheduler.start()
        try:
            svc.add_cron_job(7, "0 0 * * *")
            svc.remove_job(7)
            job = svc.scheduler.get_job("automation_task_7")
            assert job is None
        finally:
            svc.scheduler.shutdown(wait=False)

    def test_remove_nonexistent_job_no_error(self):
        """移除不存在的 job 不应抛出异常。"""
        svc = SchedulerService()
        svc.scheduler.start()
        try:
            svc.remove_job(999)  # should not raise
        finally:
            svc.scheduler.shutdown(wait=False)


class TestRestoreJobs:
    """init_app 恢复数据库 cron 任务测试。"""

    def test_restore_jobs_from_database(self):
        """init_app 应从数据库恢复启用的 cron 任务。"""
        from flask import Flask
        from app.models.base import db as real_db

        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        real_db.init_app(app)

        with app.app_context():
            real_db.create_all()

            # 插入一条启用的 cron 任务
            from app.models.automation import AutomationTask
            task = AutomationTask(
                task_no="AT-1-0001",
                name="test-cron-task",
                project_id=1,
                trigger_type="cron",
                cron_expression="*/5 * * * *",
                status=1,
                is_deleted=0,
            )
            real_db.session.add(task)
            real_db.session.commit()
            task_id = task.id

        svc = SchedulerService()
        svc.init_app(app)
        try:
            job = svc.scheduler.get_job(
                f"automation_task_{task_id}"
            )
            assert job is not None
        finally:
            svc.scheduler.shutdown(wait=False)
