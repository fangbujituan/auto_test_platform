"""
统一 AI 调用服务层。

封装提供商配置解析、API Key 解密、适配器调用等逻辑，
为业务层提供统一的 AI 调用接口。

作者: yandc
创建时间: 2026-02-10
"""
import logging

from app.models.base import db
from app.models.ai_provider import AIProviderConfig
from app.models.ai_prompt import AIPromptTemplate
from app.services.ai_adapters import get_adapter
from app.utils.crypto import CryptoUtil

logger = logging.getLogger(__name__)


class AIService:
    """统一 AI 调用服务层。"""

    def chat(self, messages: list, provider_id: int = None,
             temperature: float = 0.7, max_tokens: int = 2048) -> dict:
        """
        同步对话调用。

        Args:
            messages: 消息列表，格式为
                [{"role": "system"|"user"|"assistant", "content": "..."}]
            provider_id: 提供商配置 ID，为 None 时使用默认提供商
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            {"content": "AI回复文本", "usage": {...}}
            或 {"error_code": str, "error_message": str}
        """
        config = self._get_provider_config(provider_id)
        if isinstance(config, dict):
            return config

        api_key = None
        try:
            api_key = self._decrypt_api_key(config)
            adapter = self._get_adapter(config, api_key)
            return adapter.chat(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        except Exception as e:
            logger.exception("AI 调用异常")
            return {
                "error_code": "SERVICE_ERROR",
                "error_message": f"AI 服务错误: {e}",
            }
        finally:
            api_key = None  # noqa: F841 — 不缓存明文

    def chat_stream(self, messages: list, provider_id: int = None,
                    temperature: float = 0.7, max_tokens: int = 2048):
        """
        流式对话调用，返回 generator。

        yield 每个 token 片段（str）。
        """
        config = self._get_provider_config(provider_id)
        if isinstance(config, dict):
            import json
            yield json.dumps(config)
            return

        api_key = None
        try:
            api_key = self._decrypt_api_key(config)
            adapter = self._get_adapter(config, api_key)
            yield from adapter.chat_stream(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        except Exception as e:
            import json
            logger.exception("AI 流式调用异常")
            yield json.dumps({
                "error_code": "SERVICE_ERROR",
                "error_message": f"AI 服务错误: {e}",
            })
        finally:
            api_key = None  # noqa: F841

    def chat_with_template(self, scene: str, variables: dict,
                           provider_id: int = None) -> dict:
        """
        使用提示词模板进行对话。

        Args:
            scene: 场景标识（如 'test_case_generation'）
            variables: 模板变量字典
            provider_id: 提供商配置 ID

        Returns:
            同 chat() 返回格式
        """
        template = AIPromptTemplate.query.filter_by(
            scene=scene
        ).first()
        if not template:
            return {
                "error_code": "TEMPLATE_NOT_FOUND",
                "error_message": f"未找到场景 '{scene}' 的提示词模板",
            }

        # 使用 format_map 替换占位符
        try:
            user_content = template.user_prompt_template.format_map(
                variables
            )
        except KeyError as e:
            return {
                "error_code": "TEMPLATE_VARIABLE_MISSING",
                "error_message": f"模板变量缺失: {e}",
            }

        messages = [
            {"role": "system", "content": template.system_prompt},
            {"role": "user", "content": user_content},
        ]
        return self.chat(
            messages, provider_id=provider_id
        )

    def test_connection(self, provider_type: str, api_key: str,
                        base_url: str, model_name: str) -> dict:
        """
        测试提供商连接（使用明文参数，用于未保存的配置测试）。

        Returns:
            {"success": bool, "message": str, "latency_ms": int}
        """
        try:
            adapter = get_adapter(
                provider_type, api_key, base_url, model_name
            )
            return adapter.test_connection()
        except ValueError as e:
            return {"success": False, "message": str(e), "latency_ms": 0}
        except Exception as e:
            logger.exception("连接测试异常")
            return {"success": False, "message": str(e), "latency_ms": 0}

    def set_default(self, provider_id: int) -> dict:
        """
        设置默认提供商。

        将指定 ID 的配置设为默认，其余全部取消默认。

        Returns:
            {"success": True} 或 {"error_code": str, "error_message": str}
        """
        target = AIProviderConfig.query.get(provider_id)
        if not target:
            return {
                "error_code": "PROVIDER_NOT_FOUND",
                "error_message": "提供商配置不存在",
            }

        # 取消所有默认
        AIProviderConfig.query.filter(
            AIProviderConfig.id != provider_id
        ).update({"is_default": False})
        # 设置目标为默认
        target.is_default = True
        db.session.commit()
        return {"success": True}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_provider_config(self, provider_id: int = None):
        """
        获取提供商配置。

        未指定 provider_id 时使用默认提供商。

        Returns:
            AIProviderConfig 实例的 dict 表示，
            或 {"error_code": str, "error_message": str}
        """
        if provider_id is not None:
            config = AIProviderConfig.query.get(provider_id)
            if not config:
                return {
                    "error_code": "PROVIDER_NOT_FOUND",
                    "error_message": "提供商配置不存在",
                }
            return config

        config = AIProviderConfig.query.filter_by(
            is_default=True
        ).first()
        if not config:
            return {
                "error_code": "NO_DEFAULT_PROVIDER",
                "error_message": "未配置默认 AI 提供商",
            }
        return config

    def _get_adapter(self, provider_config, api_key: str):
        """根据配置获取对应的适配器实例。"""
        kwargs = {}
        if provider_config.provider_type == "aiop":
            kwargs = {
                "aiop_app_code": provider_config.aiop_app_code,
                "aiop_tenant_id": provider_config.aiop_tenant_id,
                "aiop_agent_code": provider_config.aiop_agent_code,
                "aiop_agent_name": provider_config.aiop_agent_name,
                "aiop_user_id": provider_config.aiop_user_id,
                "aiop_user_name": provider_config.aiop_user_name,
            }
        
        return get_adapter(
            provider_type=provider_config.provider_type,
            api_key=api_key,
            base_url=provider_config.base_url,
            model_name=provider_config.model_name,
            **kwargs
        )

    @staticmethod
    def _decrypt_api_key(provider_config) -> str:
        """在内存中解密 API Key。Ollama 等无需 Key 的返回空串。"""
        if not provider_config.api_key_encrypted:
            return ""
        return CryptoUtil.decrypt(provider_config.api_key_encrypted)
