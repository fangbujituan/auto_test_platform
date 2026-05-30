"""
LangChain LLM 工厂服务。

提供创建 LangChain 兼容的 ChatOpenAI 实例的功能，
用于 Agent 系统。

作者: yandc
创建时间: 2026-05-30
"""
import os
import base64
import time
import logging
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.models.ai_provider import AIProviderConfig
from app.models.base import db
from app.utils.crypto import CryptoUtil

load_dotenv()

logger = logging.getLogger(__name__)


class LLMLogger(BaseCallbackHandler):
    """LLM 调用日志记录器"""

    def __init__(self, provider: str = "unknown"):
        self._start_time = None
        self._provider = provider

    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 调用开始时记录请求"""
        self._start_time = time.time()
        model = kwargs.get("invocation_params", {}).get("model", "unknown")

        logger.info(f"[{self._provider}] ========== 请求开始 ==========")
        logger.info(f"[{self._provider}] 模型: {model}")
        logger.info(f"[{self._provider}] 请求数量: {len(prompts)}")

        # 记录请求内容（截断过长的 prompt）
        for i, prompt in enumerate(prompts):
            if len(prompt) > 500:
                prompt_display = prompt[:500] + "...(截断)"
            else:
                prompt_display = prompt
            logger.info(f"[{self._provider}] 请求 [{i+1}]: {prompt_display}")

    def on_llm_end(self, response: LLMResult, **kwargs):
        """LLM 调用结束时记录响应"""
        elapsed = time.time() - self._start_time if self._start_time else 0

        logger.info(f"[{self._provider}] ========== 响应结束 ==========")
        logger.info(f"[{self._provider}] 耗时: {elapsed:.2f}秒")

        # 记录 token 使用情况
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            logger.info(
                f"[{self._provider}] Token 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
            )

        # 记录响应内容（截断过长的响应）
        for i, generation in enumerate(response.generations):
            if generation:
                text = generation[0].text if generation[0] else ""
                if len(text) > 500:
                    text_display = text[:500] + "...(截断)"
                else:
                    text_display = text
                logger.info(f"[{self._provider}] 响应 [{i+1}]: {text_display}")

    def on_llm_error(self, error, **kwargs):
        """LLM 调用出错时记录错误"""
        logger.error(f"[{self._provider}] ========== 请求错误 ==========")
        logger.error(f"[{self._provider}] 错误类型: {type(error).__name__}")
        logger.error(f"[{self._provider}] 错误信息: {str(error)}")


def _b64_encode(text: str) -> str:
    """Base64 编码（用于 X-Agent-Name 和 X-User-Name）"""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


class LLMFactory:
    """LangChain LLM 工厂类"""

    @staticmethod
    def _get_env_config() -> dict:
        """从环境变量获取默认配置"""
        return {
            "aiop_base_url": os.getenv("AIOP_BASE_URL", "https://aiop-gateway.item.com/openai/v1"),
            "aiop_api_key": os.getenv("AIOP_API_KEY", ""),
            "aiop_app_code": os.getenv("AIOP_APP_CODE", ""),
            "aiop_tenant_id": os.getenv("AIOP_TENANT_ID", ""),
            "aiop_agent_code": os.getenv("AIOP_AGENT_CODE", ""),
            "aiop_agent_name": os.getenv("AIOP_AGENT_NAME", ""),
            "aiop_user_id": os.getenv("AIOP_USER_ID", ""),
            "aiop_user_name": os.getenv("AIOP_USER_NAME", ""),
            "kiro_base_url": os.getenv("KIRO_BASE_URL", "http://localhost:9000/v1"),
            "kiro_api_key": os.getenv("KIRO_API_KEY", ""),
            "aiclient_base_url": os.getenv("AICLIENT_BASE_URL", "http://localhost:9000"),
            "aiclient_api_key": os.getenv("AICLIENT_API_KEY", "sk-test"),
            "local_base_url": os.getenv("LOCAL_BASE_URL", "http://192.168.1.7:4000/v1"),
            "local_api_key": os.getenv("LOCAL_API_KEY", "sk-your-super-secret-key-2026"),
            "default_model": os.getenv("DEFAULT_MODEL", "local/llama3.2-1b"),
        }

    @staticmethod
    def create_llm(
        provider_config: Optional[AIProviderConfig] = None,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        agent_name: Optional[str] = None,
    ) -> ChatOpenAI:
        """
        创建 LangChain ChatOpenAI 实例。

        Args:
            provider_config: AIProviderConfig 实例，如果为 None 则使用默认配置
            callbacks: 回调处理器列表
            agent_name: Agent 名称，用于日志和 Token 统计

        Returns:
            ChatOpenAI 实例
        """
        env_config = LLMFactory._get_env_config()

        # 如果没有提供配置，尝试获取默认配置
        if provider_config is None:
            provider_config = AIProviderConfig.query.filter_by(
                is_default=True, is_enabled=True
            ).first()

        # 如果仍然没有配置，使用默认模型配置
        if provider_config is None:
            return LLMFactory._create_from_model_str(
                env_config["default_model"],
                env_config,
                callbacks,
                agent_name,
            )

        return LLMFactory._create_from_config(
            provider_config, env_config, callbacks, agent_name
        )

    @staticmethod
    def create_llm_from_model_str(
        model_str: str,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        agent_name: Optional[str] = None,
    ) -> ChatOpenAI:
        """
        从模型字符串创建 ChatOpenAI 实例。

        模型字符串格式: "gateway/provider/model" 或 "gateway/model"
        例如:
            - "aiop/azure/gpt-5.4"
            - "kiro/claude-sonnet-4.5"
            - "aiclient/claude-kiro-oauth/claude-sonnet-4-6"
            - "local/llama3.2-1b"

        Args:
            model_str: 模型字符串
            callbacks: 回调处理器列表
            agent_name: Agent 名称

        Returns:
            ChatOpenAI 实例
        """
        env_config = LLMFactory._get_env_config()
        return LLMFactory._create_from_model_str(
            model_str, env_config, callbacks, agent_name
        )

    @staticmethod
    def _create_from_config(
        provider_config: AIProviderConfig,
        env_config: dict,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        agent_name: Optional[str] = None,
    ) -> ChatOpenAI:
        """从 AIProviderConfig 配置创建"""
        # 解密 API Key
        api_key = ""
        if provider_config.api_key_encrypted:
            api_key = CryptoUtil.decrypt(provider_config.api_key_encrypted)

        provider_type = provider_config.provider_type
        base_url = provider_config.base_url
        model_name = provider_config.model_name

        # 准备回调
        if callbacks is None:
            callbacks = []
        callbacks.append(LLMLogger(provider_type))

        default_headers = {}

        if provider_type == "aiop":
            # AIOP 网关特殊处理
            is_jwt_token = api_key and api_key.startswith("eyJ")
            if not is_jwt_token:
                if provider_config.aiop_app_code:
                    default_headers["X-App-Code"] = provider_config.aiop_app_code
                if provider_config.aiop_tenant_id:
                    default_headers["X-Tenant-Id"] = provider_config.aiop_tenant_id
                if provider_config.aiop_agent_code:
                    default_headers["X-Agent-Code"] = provider_config.aiop_agent_code
                if provider_config.aiop_agent_name:
                    default_headers["X-Agent-Name"] = _b64_encode(
                        provider_config.aiop_agent_name
                    )
                if provider_config.aiop_user_id:
                    default_headers["X-User-Id"] = provider_config.aiop_user_id
                if provider_config.aiop_user_name:
                    default_headers["X-User-Name"] = _b64_encode(
                        provider_config.aiop_user_name
                    )

        elif provider_type == "aiclient":
            # AIClient 网关特殊处理：解析模型名称
            parts = model_name.split("/")
            if len(parts) == 2:
                provider, actual_model = parts
                base_url = f"{base_url}/{provider}/v1"
                model_name = actual_model
            else:
                base_url = f"{base_url}/claude-kiro-oauth/v1"

        logger.info(
            f"[LLMFactory] 创建 {provider_type} 模型: {model_name}, base_url={base_url}"
        )

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            callbacks=callbacks,
            default_headers=default_headers if default_headers else None,
        )

    @staticmethod
    def _create_from_model_str(
        model_str: str,
        env_config: dict,
        callbacks: Optional[list[BaseCallbackHandler]] = None,
        agent_name: Optional[str] = None,
    ) -> ChatOpenAI:
        """从模型字符串创建"""
        # 解析模型字符串
        parts = model_str.split("/")

        if len(parts) >= 1:
            gateway = parts[0]
        else:
            gateway = "local"

        # 准备回调
        if callbacks is None:
            callbacks = []
        callbacks.append(LLMLogger(gateway))

        default_headers = {}

        if gateway == "aiop":
            # AIOP 网关
            api_key = env_config["aiop_api_key"]
            base_url = env_config["aiop_base_url"]

            if len(parts) >= 3:
                model = "/".join(parts[1:])
            elif len(parts) == 2:
                model = f"azure/{parts[1]}"
            else:
                model = "azure/gpt-5.4"

            # AIOP 特殊请求头
            is_jwt_token = api_key and api_key.startswith("eyJ")
            if not is_jwt_token:
                if env_config["aiop_app_code"]:
                    default_headers["X-App-Code"] = env_config["aiop_app_code"]
                if env_config["aiop_tenant_id"]:
                    default_headers["X-Tenant-Id"] = env_config["aiop_tenant_id"]
                if env_config["aiop_agent_code"]:
                    default_headers["X-Agent-Code"] = env_config["aiop_agent_code"]
                if env_config["aiop_agent_name"]:
                    default_headers["X-Agent-Name"] = _b64_encode(
                        env_config["aiop_agent_name"]
                    )
                if env_config["aiop_user_id"]:
                    default_headers["X-User-Id"] = env_config["aiop_user_id"]
                if env_config["aiop_user_name"]:
                    default_headers["X-User-Name"] = _b64_encode(
                        env_config["aiop_user_name"]
                    )

        elif gateway == "kiro":
            # Kiro 网关
            api_key = env_config["kiro_api_key"]
            base_url = env_config["kiro_base_url"]
            if len(parts) >= 2:
                model = "/".join(parts[1:])
            else:
                model = "claude-sonnet-4.5"

        elif gateway == "aiclient":
            # AIClient 网关
            api_key = env_config["aiclient_api_key"]
            base_url = env_config["aiclient_base_url"]

            if len(parts) >= 3:
                provider = parts[1]
                model = parts[2]
                base_url = f"{base_url}/{provider}/v1"
            elif len(parts) == 2:
                model = parts[1]
                base_url = f"{base_url}/claude-kiro-oauth/v1"
            else:
                model = "claude-sonnet-4-6"
                base_url = f"{base_url}/claude-kiro-oauth/v1"

        elif gateway == "local":
            # Local 网关
            api_key = env_config["local_api_key"]
            base_url = env_config["local_base_url"]
            if len(parts) >= 2:
                model = "/".join(parts[1:])
            else:
                model = "llama3.2-1b"

        else:
            # 默认使用 local
            api_key = env_config["local_api_key"]
            base_url = env_config["local_base_url"]
            model = model_str

        logger.info(
            f"[LLMFactory] 创建 {gateway} 模型: {model}, base_url={base_url}"
        )

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            callbacks=callbacks,
            default_headers=default_headers if default_headers else None,
        )
