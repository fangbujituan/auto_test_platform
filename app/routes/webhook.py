"""
Webhook 触发自动化任务执行路由。

作者: yandc
创建时间: 2026-01-20
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.automation import AutomationTask
from app.services.automation_executor import (
    AutomationExecutor,
    DuplicateExecutionError,
)
from app.schemas.common import MessageResponseSchema

webhook_blp = Blueprint(
    "webhook",
    __name__,
    url_prefix="/api/webhooks",
    description="Webhook 触发自动化任务执行",
)

executor = AutomationExecutor()


@webhook_blp.route("/<string:token>")
class WebhookTriggerView(MethodView):
    """Webhook 触发自动化任务执行（公开端点，通过 token 验证）"""

    @webhook_blp.response(200, MessageResponseSchema)
    @webhook_blp.alt_response(
        401, schema=MessageResponseSchema, description="无效Token"
    )
    @webhook_blp.alt_response(
        409, schema=MessageResponseSchema, description="重复执行"
    )
    def post(self, token):
        """通过 Webhook Token 触发自动化任务执行。"""
        task = AutomationTask.query.filter_by(
            webhook_token=token, is_deleted=0, status=1
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "无效的 Webhook Token"
            }), 401

        try:
            execution = executor.execute_task(
                task.id, trigger_source="webhook"
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
