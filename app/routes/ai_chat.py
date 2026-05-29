"""
AI 对话 API 路由。

作者: yandc
创建时间: 2026-02-10
"""
import json

from flask import jsonify, Response
from flask.views import MethodView
from flask_smorest import Blueprint
from app.utils.permission import login_required
from app.services.ai_service import AIService
from app.schemas.ai import AIChatRequestSchema
from app.schemas.common import MessageResponseSchema

ai_chat_blp = Blueprint(
    "ai_chat", __name__,
    url_prefix="/api/ai/chat",
    description="AI 对话接口"
)

ai_service = AIService()


def _validate_messages(messages):
    """校验消息列表非空且至少一条消息内容非空。"""
    if not messages:
        return False
    return any(
        msg.get("content", "").strip()
        for msg in messages
    )


@ai_chat_blp.route("")
class AIChatView(MethodView):
    """同步对话接口"""

    @ai_chat_blp.arguments(AIChatRequestSchema)
    @ai_chat_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """发送对话请求，返回 AI 回复。"""
        messages = json_data.get("messages", [])
        if not _validate_messages(messages):
            return jsonify({
                "code": 400,
                "message": "消息内容不能为空",
            }), 400

        result = ai_service.chat(
            messages=messages,
            provider_id=json_data.get("provider_id"),
            temperature=json_data.get("temperature", 0.7),
            max_tokens=json_data.get("max_tokens", 2048),
        )

        if "error_code" in result:
            return jsonify({
                "code": 1,
                "message": result["error_message"],
            }), 502

        return jsonify({
            "code": 0,
            "data": result,
        })


@ai_chat_blp.route("/stream")
class AIChatStreamView(MethodView):
    """流式对话接口（SSE）"""

    @login_required
    def post(self):
        """发送对话请求，SSE 流式返回。"""
        from flask import request as flask_request
        json_data = flask_request.get_json(silent=True) or {}

        messages = json_data.get("messages", [])
        if not _validate_messages(messages):
            return jsonify({
                "code": 400,
                "message": "消息内容不能为空",
            }), 400

        def generate():
            for chunk in ai_service.chat_stream(
                messages=messages,
                provider_id=json_data.get("provider_id"),
                temperature=json_data.get("temperature", 0.7),
                max_tokens=json_data.get("max_tokens", 2048),
            ):
                if isinstance(chunk, dict):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
