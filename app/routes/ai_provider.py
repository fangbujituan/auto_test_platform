"""
AI 提供商配置 API 路由。

作者: yandc
创建时间: 2026-02-10
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.ai_provider import AIProviderConfig
from app.utils.permission import login_required
from app.utils.crypto import CryptoUtil
from app.services.ai_service import AIService
from app.schemas.ai import (
    AIProviderCreateSchema,
    AIProviderUpdateSchema,
    AIProviderTestSchema,
)
from app.schemas.common import MessageResponseSchema

ai_provider_blp = Blueprint(
    "ai_provider", __name__,
    url_prefix="/api/ai/providers",
    description="AI 提供商配置管理"
)

ai_service = AIService()


def _provider_to_response(provider):
    """将提供商配置转换为响应字典，API Key 脱敏。"""
    masked_key = ""
    if provider.api_key_encrypted:
        try:
            raw_key = CryptoUtil.decrypt(provider.api_key_encrypted)
            masked_key = CryptoUtil.mask_key(raw_key)
        except Exception:
            masked_key = "****"
    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "api_key_masked": masked_key,
        "base_url": provider.base_url,
        "model_name": provider.model_name,
        "is_default": provider.is_default,
        "is_enabled": provider.is_enabled,
        "created_at": provider.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": provider.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


@ai_provider_blp.route("")
class AIProvidersView(MethodView):
    """提供商配置列表与创建"""

    @ai_provider_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取所有提供商配置列表（API Key 脱敏）。"""
        providers = AIProviderConfig.query.all()
        return jsonify({
            "code": 0,
            "data": [_provider_to_response(p) for p in providers],
        })

    @ai_provider_blp.arguments(AIProviderCreateSchema)
    @ai_provider_blp.response(200, MessageResponseSchema)
    @ai_provider_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    def post(self, json_data):
        """创建提供商配置。"""
        try:
            encrypted_key = None
            if json_data.get("api_key"):
                encrypted_key = CryptoUtil.encrypt(json_data["api_key"])

            provider = AIProviderConfig(
                name=json_data["name"],
                provider_type=json_data["provider_type"],
                api_key_encrypted=encrypted_key,
                base_url=json_data["base_url"],
                model_name=json_data["model_name"],
                is_default=json_data.get("is_default", False),
                is_enabled=json_data.get("is_enabled", True),
            )

            # 如果设为默认，取消其他默认
            if provider.is_default:
                AIProviderConfig.query.update({"is_default": False})

            db.session.add(provider)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": _provider_to_response(provider),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}",
            }), 500


@ai_provider_blp.route("/<int:provider_id>")
class AIProviderDetailView(MethodView):
    """提供商配置详情、更新与删除"""

    @ai_provider_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self, provider_id):
        """获取单个提供商配置详情（API Key 脱敏）。"""
        provider = AIProviderConfig.query.get(provider_id)
        if not provider:
            return jsonify({"code": 1, "message": "提供商配置不存在"}), 404

        return jsonify({
            "code": 0,
            "data": _provider_to_response(provider),
        })

    @ai_provider_blp.arguments(AIProviderUpdateSchema)
    @ai_provider_blp.response(200, MessageResponseSchema)
    @ai_provider_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    def put(self, json_data, provider_id):
        """更新提供商配置。"""
        provider = AIProviderConfig.query.get(provider_id)
        if not provider:
            return jsonify({"code": 1, "message": "提供商配置不存在"}), 404

        try:
            if "name" in json_data:
                provider.name = json_data["name"]
            if "provider_type" in json_data:
                provider.provider_type = json_data["provider_type"]
            if "api_key" in json_data:
                if json_data["api_key"]:
                    provider.api_key_encrypted = CryptoUtil.encrypt(json_data["api_key"])
                else:
                    provider.api_key_encrypted = None
            if "base_url" in json_data:
                provider.base_url = json_data["base_url"]
            if "model_name" in json_data:
                provider.model_name = json_data["model_name"]
            if "is_default" in json_data:
                if json_data["is_default"]:
                    AIProviderConfig.query.filter(
                        AIProviderConfig.id != provider_id
                    ).update({"is_default": False})
                provider.is_default = json_data["is_default"]
            if "is_enabled" in json_data:
                provider.is_enabled = json_data["is_enabled"]

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": _provider_to_response(provider),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}",
            }), 500

    @ai_provider_blp.response(200, MessageResponseSchema)
    @ai_provider_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    def delete(self, provider_id):
        """删除提供商配置。"""
        provider = AIProviderConfig.query.get(provider_id)
        if not provider:
            return jsonify({"code": 1, "message": "提供商配置不存在"}), 404

        try:
            db.session.delete(provider)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}",
            }), 500


@ai_provider_blp.route("/<int:provider_id>/test")
class AIProviderTestView(MethodView):
    """测试已保存的提供商连接"""

    @ai_provider_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, provider_id):
        """测试已保存的提供商配置连接。"""
        provider = AIProviderConfig.query.get(provider_id)
        if not provider:
            return jsonify({"code": 1, "message": "提供商配置不存在"}), 404

        api_key = ""
        if provider.api_key_encrypted:
            try:
                api_key = CryptoUtil.decrypt(provider.api_key_encrypted)
            except Exception:
                return jsonify({
                    "code": 1,
                    "message": "API Key 解密失败",
                }), 500

        result = ai_service.test_connection(
            provider_type=provider.provider_type,
            api_key=api_key,
            base_url=provider.base_url,
            model_name=provider.model_name,
        )
        return jsonify({"code": 0, "data": result})


@ai_provider_blp.route("/test")
class AIProviderTestUnsavedView(MethodView):
    """测试未保存的提供商连接"""

    @ai_provider_blp.arguments(AIProviderTestSchema)
    @ai_provider_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """使用表单参数测试连接（未保存时）。"""
        result = ai_service.test_connection(
            provider_type=json_data["provider_type"],
            api_key=json_data.get("api_key") or "",
            base_url=json_data["base_url"],
            model_name=json_data["model_name"],
        )
        return jsonify({"code": 0, "data": result})


@ai_provider_blp.route("/<int:provider_id>/default")
class AIProviderDefaultView(MethodView):
    """设置默认提供商"""

    @ai_provider_blp.response(200, MessageResponseSchema)
    @ai_provider_blp.alt_response(500, schema=MessageResponseSchema, description="设置失败")
    @login_required
    def put(self, provider_id):
        """将指定提供商设为默认。"""
        result = ai_service.set_default(provider_id)
        if "error_code" in result:
            return jsonify({
                "code": 1,
                "message": result["error_message"],
            }), 404

        provider = AIProviderConfig.query.get(provider_id)
        return jsonify({
            "code": 0,
            "message": "设置默认成功",
            "data": _provider_to_response(provider),
        })
