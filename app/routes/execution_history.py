"""
执行历史与统计路由。

作者: yandc
创建时间: 2026-01-20
"""
from datetime import datetime, timedelta

from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.automation import (
    AutomationTask,
    TaskExecution,
    TaskExecutionDetail,
)
from app.utils.permission import require_permission
from app.schemas.common import MessageResponseSchema

execution_history_blp = Blueprint(
    "execution_history",
    __name__,
    url_prefix="/api",
    description="执行历史与统计",
)


@execution_history_blp.route("/automations/<int:task_id>/executions")
class ExecutionListView(MethodView):
    """执行历史列表"""

    @execution_history_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    def get(self, task_id):
        """获取指定自动化任务的执行历史列表（分页，按创建时间倒序）。"""
        task = AutomationTask.query.filter_by(
            id=task_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        query = TaskExecution.query.filter(
            TaskExecution.task_id == task_id,
            TaskExecution.status != "deleted",
        ).order_by(TaskExecution.created_at.desc())

        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            "code": 0,
            "data": [e.to_dict() for e in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
        })


@execution_history_blp.route("/executions/<int:exec_id>")
class ExecutionDetailView(MethodView):
    """执行详情"""

    @execution_history_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    def get(self, exec_id):
        """获取执行详情，包含每个用例的执行状态、耗时和错误信息。"""
        execution = TaskExecution.query.filter(
            TaskExecution.id == exec_id,
            TaskExecution.status != "deleted",
        ).first()
        if not execution:
            return jsonify({
                "code": 1,
                "message": "执行记录不存在"
            }), 404

        exec_dict = execution.to_dict()
        details = TaskExecutionDetail.query.filter_by(
            execution_id=execution.id
        ).order_by(TaskExecutionDetail.id.asc()).all()
        exec_dict["details"] = [d.to_dict() for d in details]

        return jsonify({"code": 0, "data": exec_dict})


@execution_history_blp.route("/automations/<int:task_id>/statistics")
class ExecutionStatisticsView(MethodView):
    """执行统计"""

    @execution_history_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    def get(self, task_id):
        """获取最近 30 天的执行统计：执行次数、平均通过率、平均耗时。"""
        task = AutomationTask.query.filter_by(
            id=task_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        since = datetime.utcnow() - timedelta(days=30)

        executions = TaskExecution.query.filter(
            TaskExecution.task_id == task_id,
            TaskExecution.status == "completed",
            TaskExecution.created_at >= since,
        ).all()

        execution_count = len(executions)

        if execution_count == 0:
            return jsonify({
                "code": 0,
                "data": {
                    "execution_count": 0,
                    "avg_pass_rate": 0.0,
                    "avg_duration": 0.0,
                },
            })

        total_pass_rate = 0.0
        total_duration = 0.0
        for ex in executions:
            if ex.total_cases and ex.total_cases > 0:
                total_pass_rate += ex.passed_count / ex.total_cases
            total_duration += ex.duration or 0.0

        avg_pass_rate = round(total_pass_rate / execution_count, 4)
        avg_duration = round(total_duration / execution_count, 2)

        return jsonify({
            "code": 0,
            "data": {
                "execution_count": execution_count,
                "avg_pass_rate": avg_pass_rate,
                "avg_duration": avg_duration,
            },
        })
