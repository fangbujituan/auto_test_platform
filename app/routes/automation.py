"""
自动化任务管理路由。

作者: yandc
创建时间: 2026-01-20
"""
import secrets

from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.automation import (
    AutomationTask,
    AutomationTaskCase,
    TaskExecution,
    generate_task_no,
)
from app.models.env_variable import Environment
from app.utils.permission import check_project_permission, require_permission
from app.services.scheduler_service import SchedulerService
from app.services.automation_executor import AutomationExecutor, DuplicateExecutionError
from app.schemas.common import MessageResponseSchema

automation_blp = Blueprint(
    "automation",
    __name__,
    url_prefix="/api/projects/<int:project_id>/automations",
    description="自动化任务管理",
)

automation_exec_blp = Blueprint(
    "automation_exec",
    __name__,
    url_prefix="/api/automations",
    description="自动化任务执行",
)

# 向后兼容
automation_bp = automation_blp

scheduler = SchedulerService()


@automation_blp.route("")
class AutomationsView(MethodView):
    """自动化任务列表与创建"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目自动化任务列表（分页，按创建时间倒序）。"""
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        query = AutomationTask.query.filter_by(
            project_id=project_id, is_deleted=0
        ).order_by(AutomationTask.created_at.desc())

        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            "code": 0,
            "data": [t.to_dict() for t in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
        })

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        500, schema=MessageResponseSchema, description="创建失败"
    )
    @require_permission("automation:create")
    @check_project_permission('create')
    def post(self, project_id):
        """创建自动化任务。"""
        data = request.get_json()

        name = data.get("name")
        if not name:
            return jsonify({
                "code": 1,
                "message": "任务名称不能为空"
            }), 400

        # 校验名称唯一性
        existing = AutomationTask.query.filter_by(
            project_id=project_id, name=name, is_deleted=0
        ).first()
        if existing:
            return jsonify({
                "code": 1,
                "message": "任务名称已存在"
            }), 400

        # 校验环境存在性
        environment_id = data.get("environment_id")
        if environment_id is not None:
            env = Environment.query.get(environment_id)
            if not env:
                return jsonify({
                    "code": 1,
                    "message": "环境不存在"
                }), 404

        trigger_type = data.get("trigger_type", "manual")

        # Cron 表达式校验
        cron_expression = data.get("cron_expression")
        if trigger_type == "cron":
            if not cron_expression:
                return jsonify({
                    "code": 1,
                    "message": "Cron 表达式不能为空"
                }), 400
            if not SchedulerService.validate_cron(cron_expression):
                return jsonify({
                    "code": 1,
                    "message": "Cron 表达式格式无效"
                }), 400

        # Webhook 令牌生成
        webhook_token = None
        if trigger_type == "webhook":
            webhook_token = secrets.token_urlsafe(32)

        try:
            task = AutomationTask(
                task_no=generate_task_no(project_id),
                name=name,
                description=data.get("description"),
                project_id=project_id,
                trigger_type=trigger_type,
                cron_expression=cron_expression,
                webhook_token=webhook_token,
                environment_id=environment_id,
                status=data.get("status", 1),
            )
            db.session.add(task)
            db.session.commit()

            # 注册 cron 调度
            if trigger_type == "cron" and cron_expression:
                scheduler.add_cron_job(task.id, cron_expression)

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": task.to_dict(),
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}"
            }), 500


@automation_blp.route("/<int:task_id>")
class AutomationDetailView(MethodView):
    """自动化任务详情、更新与删除"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    @check_project_permission('read')
    def get(self, project_id, task_id):
        """获取任务详情（含关联用例）。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        task_dict = task.to_dict()
        # 附带关联用例信息
        task_cases = AutomationTaskCase.query.filter_by(
            task_id=task.id
        ).order_by(AutomationTaskCase.sort_order.asc()).all()
        task_dict["cases"] = [tc.to_dict() for tc in task_cases]

        return jsonify({"code": 0, "data": task_dict})

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        500, schema=MessageResponseSchema, description="更新失败"
    )
    @require_permission("automation:update")
    @check_project_permission('update')
    def put(self, project_id, task_id):
        """更新自动化任务。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        data = request.get_json()

        # 名称唯一性校验（如果更新了名称）
        new_name = data.get("name")
        if new_name and new_name != task.name:
            dup = AutomationTask.query.filter_by(
                project_id=project_id, name=new_name, is_deleted=0
            ).first()
            if dup:
                return jsonify({
                    "code": 1,
                    "message": "任务名称已存在"
                }), 400

        # 校验环境存在性
        environment_id = data.get("environment_id")
        if environment_id is not None:
            env = Environment.query.get(environment_id)
            if not env:
                return jsonify({
                    "code": 1,
                    "message": "环境不存在"
                }), 404

        new_trigger = data.get("trigger_type")
        new_cron = data.get("cron_expression")

        # Cron 表达式校验
        effective_trigger = new_trigger or task.trigger_type
        if effective_trigger == "cron":
            effective_cron = (
                new_cron if new_cron is not None
                else task.cron_expression
            )
            if effective_cron and not SchedulerService.validate_cron(
                effective_cron
            ):
                return jsonify({
                    "code": 1,
                    "message": "Cron 表达式格式无效"
                }), 400

        try:
            old_trigger = task.trigger_type

            # 更新简单字段
            for field in [
                "name", "description", "trigger_type",
                "cron_expression", "environment_id", "status",
            ]:
                if field in data:
                    setattr(task, field, data[field])

            # Webhook 令牌：切换到 webhook 时生成
            if (
                new_trigger == "webhook"
                and old_trigger != "webhook"
            ):
                task.webhook_token = secrets.token_urlsafe(32)

            # 处理 trigger_type 变更的调度器同步
            effective_trigger = task.trigger_type
            if effective_trigger == "cron" and task.cron_expression:
                scheduler.add_cron_job(
                    task.id, task.cron_expression
                )
            elif old_trigger == "cron" and effective_trigger != "cron":
                scheduler.remove_job(task.id)

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": task.to_dict(),
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}"
            }), 500

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        500, schema=MessageResponseSchema, description="删除失败"
    )
    @require_permission("automation:delete")
    @check_project_permission('delete')
    def delete(self, project_id, task_id):
        """软删除任务及关联执行历史。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        try:
            task.is_deleted = 1

            # 标记关联的 TaskExecution 为已删除
            TaskExecution.query.filter_by(
                task_id=task.id
            ).update({"status": "deleted"})

            # 如果是 cron 类型，移除调度
            if task.trigger_type == "cron":
                scheduler.remove_job(task.id)

            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "删除成功"
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}"
            }), 500


# ---- 执行相关路由 (automation_exec_blp) ----

executor = AutomationExecutor()


@automation_exec_blp.route("/<int:task_id>/execute")
class AutomationExecuteView(MethodView):
    """手动触发自动化任务执行"""

    @automation_exec_blp.response(200, MessageResponseSchema)
    @require_permission("automation:execute")
    def post(self, task_id):
        """手动触发执行自动化任务。"""
        task = AutomationTask.query.filter_by(
            id=task_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        data = request.get_json(silent=True) or {}
        environment_id = data.get("environment_id")

        try:
            execution = executor.execute_task(
                task_id, environment_id=environment_id
            )
            return jsonify({
                "code": 0,
                "message": "执行已触发",
                "data": execution.to_dict(),
            })
        except DuplicateExecutionError:
            return jsonify({
                "code": 1,
                "message": "任务正在执行中，请勿重复触发"
            }), 409


@automation_exec_blp.route("/<int:task_id>/cancel")
class AutomationCancelView(MethodView):
    """取消自动化任务执行"""

    @automation_exec_blp.response(200, MessageResponseSchema)
    @require_permission("automation:execute")
    def post(self, task_id):
        """取消正在执行的自动化任务。"""
        task = AutomationTask.query.filter_by(
            id=task_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        running_execution = TaskExecution.query.filter_by(
            task_id=task_id, status="running"
        ).first()
        if not running_execution:
            return jsonify({
                "code": 1,
                "message": "没有正在执行的任务"
            }), 404

        try:
            running_execution.status = "cancelled"
            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "执行已取消",
                "data": running_execution.to_dict(),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"取消失败: {str(e)}"
            }), 500
