"""
自动化任务执行引擎。

作者: yandc
创建时间: 2026-01-20
"""
import time
import traceback
from datetime import datetime

from app.models.base import db
from app.models.automation import AutomationTask, AutomationTaskCase, TaskExecution, TaskExecutionDetail
from app.models.case import TestCase
from app.services.executor import TestExecutor
from app.services.variable_replacer import replace_in_request, resolve_prefix_url, merge_global_params


class AutomationExecutor:
    """自动化任务执行引擎，按顺序执行关联用例并记录结果。"""

    def __init__(self, timeout=30):
        self.timeout = timeout

    def execute_task(self, task_id, environment_id=None,
                     trigger_source="manual"):
        """
        执行自动化任务，返回执行记录。

        Args:
            task_id: 自动化任务ID
            environment_id: 可选环境ID，覆盖任务默认环境
            trigger_source: 触发来源 (manual/cron/webhook)

        Returns:
            TaskExecution 记录
        """
        # 防止重复执行
        if self._check_running(task_id):
            raise DuplicateExecutionError("任务正在执行中，请勿重复触发")

        task = AutomationTask.query.get(task_id)
        if not task:
            raise ValueError(f"自动化任务不存在: {task_id}")

        # 确定执行环境：参数优先，否则使用任务默认环境
        env_id = environment_id if environment_id is not None else task.environment_id

        # 创建执行记录
        execution = TaskExecution(
            task_id=task_id,
            status="pending",
            trigger_source=trigger_source,
            started_at=datetime.now(),
        )
        db.session.add(execution)
        db.session.commit()

        try:
            # 更新为 running
            execution.status = "running"
            db.session.commit()

            # 获取关联用例（按 sort_order 排序）
            task_cases = AutomationTaskCase.query.filter_by(
                task_id=task_id
            ).order_by(AutomationTaskCase.sort_order.asc()).all()

            # 执行用例
            self._execute_cases(execution, task_cases, env_id, task.project_id)

            # 汇总结果
            self._summarize(execution)

            execution.status = "completed"
            execution.finished_at = datetime.now()
            db.session.commit()

        except Exception as e:
            execution.status = "failed"
            execution.finished_at = datetime.now()
            execution.error_message = traceback.format_exc()
            self._summarize(execution)
            db.session.commit()

        return execution

    def _check_running(self, task_id):
        """检查任务是否正在执行中，防止重复执行。"""
        running = TaskExecution.query.filter_by(
            task_id=task_id, status="running"
        ).first()
        return running is not None

    def _execute_cases(self, execution, task_cases, environment_id, project_id):
        """
        按顺序执行关联的测试用例并记录结果。

        单个用例异常不中断整体执行。
        """
        executor = TestExecutor(timeout=self.timeout)

        for task_case in task_cases:
            case = TestCase.query.get(task_case.case_id) if task_case.case_id else None
            if not case:
                # 用例不存在，记录为 error
                detail = TaskExecutionDetail(
                    execution_id=execution.id,
                    case_id=task_case.case_id,
                    case_name="未知用例",
                    status="error",
                    duration=0,
                    error_message=f"用例不存在: {task_case.case_id}",
                )
                db.session.add(detail)
                db.session.commit()
                continue

            start_time = time.time()
            try:
                # 环境变量替换
                base_url, path, headers, params, body = self._prepare_case(
                    case, environment_id, project_id
                )

                # 构建临时用例对象用于执行（替换后的值）
                case.url = base_url + path if path else base_url
                case.headers = headers
                case.params = params
                case.body = body

                # 复用 TestExecutor 执行
                result = executor.run_case(case)
                duration = time.time() - start_time

                detail = TaskExecutionDetail(
                    execution_id=execution.id,
                    case_id=case.id,
                    case_name=case.name,
                    status=result.status,
                    actual_status=result.actual_status,
                    actual_response=result.actual_response,
                    duration=duration,
                    error_message=result.error_message,
                )
            except Exception as e:
                duration = time.time() - start_time
                detail = TaskExecutionDetail(
                    execution_id=execution.id,
                    case_id=case.id if case else task_case.case_id,
                    case_name=case.name if case else "未知用例",
                    status="error",
                    duration=duration,
                    error_message=str(e),
                )

            db.session.add(detail)
            db.session.commit()

    def _prepare_case(self, case, environment_id, project_id):
        """
        为用例准备执行数据：解析前缀URL、替换环境变量、合并全局参数。

        Returns:
            (base_url, path, headers, params, body)
        """
        url = case.url or ""
        headers = case.headers or {}
        params = case.params or {}
        body = case.body
        body_type = "json"

        if environment_id:
            # 解析前缀URL
            base_url = resolve_prefix_url(environment_id, base_url=url)
            # 如果 resolve_prefix_url 返回了前缀URL，path 为原始 url；否则 base_url 就是原始 url
            if base_url != url:
                path = url
            else:
                path = ""
                base_url = url

            # 替换环境变量
            base_url, path, headers, params, body = replace_in_request(
                project_id, base_url, path, headers, params, body, body_type,
                environment_id=environment_id
            )

            # 合并全局参数到 headers
            headers = merge_global_params(project_id, headers)
        else:
            base_url = url
            path = ""

        return base_url, path, headers, params, body

    def _summarize(self, execution):
        """汇总执行结果（total_cases、passed_count、failed_count、error_count、duration）。"""
        details = TaskExecutionDetail.query.filter_by(execution_id=execution.id).all()

        execution.total_cases = len(details)
        execution.passed_count = sum(1 for d in details if d.status == "passed")
        execution.failed_count = sum(1 for d in details if d.status == "failed")
        execution.error_count = sum(1 for d in details if d.status == "error")

        if execution.started_at and execution.finished_at:
            execution.duration = (execution.finished_at - execution.started_at).total_seconds()
        elif execution.started_at:
            execution.duration = (datetime.now() - execution.started_at).total_seconds()


class DuplicateExecutionError(Exception):
    """任务正在执行中，拒绝重复执行。"""
    pass
