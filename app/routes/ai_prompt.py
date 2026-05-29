"""
AI 提示词模板 API 路由。

作者: yandc
创建时间: 2026-02-10
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.ai_prompt import AIPromptTemplate
from app.utils.permission import login_required
from app.schemas.ai import (
    AIPromptCreateSchema,
    AIPromptUpdateSchema,
)
from app.schemas.common import MessageResponseSchema

ai_prompt_blp = Blueprint(
    "ai_prompt", __name__,
    url_prefix="/api/ai/prompts",
    description="AI 提示词模板管理"
)


def _prompt_to_response(prompt):
    """将提示词模板转换为响应字典。"""
    return {
        "id": prompt.id,
        "name": prompt.name,
        "scene": prompt.scene,
        "system_prompt": prompt.system_prompt,
        "user_prompt_template": prompt.user_prompt_template,
        "description": prompt.description,
        "is_builtin": prompt.is_builtin,
        "created_at": prompt.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": prompt.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


@ai_prompt_blp.route("")
class AIPromptsView(MethodView):
    """提示词模板列表与创建"""

    @ai_prompt_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取所有提示词模板列表。"""
        prompts = AIPromptTemplate.query.all()
        return jsonify({
            "code": 0,
            "data": [_prompt_to_response(p) for p in prompts],
        })

    @ai_prompt_blp.arguments(AIPromptCreateSchema)
    @ai_prompt_blp.response(200, MessageResponseSchema)
    @ai_prompt_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    def post(self, json_data):
        """创建提示词模板。"""
        try:
            prompt = AIPromptTemplate(
                name=json_data["name"],
                scene=json_data["scene"],
                system_prompt=json_data["system_prompt"],
                user_prompt_template=json_data["user_prompt_template"],
                description=json_data.get("description"),
            )

            db.session.add(prompt)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": _prompt_to_response(prompt),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}",
            }), 500


@ai_prompt_blp.route("/<int:prompt_id>")
class AIPromptDetailView(MethodView):
    """提示词模板详情、更新与删除"""

    @ai_prompt_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self, prompt_id):
        """获取单个提示词模板详情。"""
        prompt = AIPromptTemplate.query.get(prompt_id)
        if not prompt:
            return jsonify({"code": 1, "message": "提示词模板不存在"}), 404

        return jsonify({
            "code": 0,
            "data": _prompt_to_response(prompt),
        })

    @ai_prompt_blp.arguments(AIPromptUpdateSchema)
    @ai_prompt_blp.response(200, MessageResponseSchema)
    @ai_prompt_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    def put(self, json_data, prompt_id):
        """更新提示词模板。"""
        prompt = AIPromptTemplate.query.get(prompt_id)
        if not prompt:
            return jsonify({"code": 1, "message": "提示词模板不存在"}), 404

        try:
            if "name" in json_data:
                prompt.name = json_data["name"]
            if "scene" in json_data:
                prompt.scene = json_data["scene"]
            if "system_prompt" in json_data:
                prompt.system_prompt = json_data["system_prompt"]
            if "user_prompt_template" in json_data:
                prompt.user_prompt_template = json_data["user_prompt_template"]
            if "description" in json_data:
                prompt.description = json_data["description"]

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": _prompt_to_response(prompt),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}",
            }), 500

    @ai_prompt_blp.response(200, MessageResponseSchema)
    @ai_prompt_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    def delete(self, prompt_id):
        """删除提示词模板。"""
        prompt = AIPromptTemplate.query.get(prompt_id)
        if not prompt:
            return jsonify({"code": 1, "message": "提示词模板不存在"}), 404

        try:
            db.session.delete(prompt)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}",
            }), 500
