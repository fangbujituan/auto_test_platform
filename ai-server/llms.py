"""
LLM 模型配置

支持多种模型：
- AIOP Gateway: 公司统一 AI 网关（OpenAI/Azure/Gemini）
- Kiro Gateway: 本地 Kiro 网关（Claude/DeepSeek）
- AIClient2API: 本地 AIClient-2-API 网关（Claude/Gemini/Qwen/Grok）
"""

import os
import json
import time
import base64
from typing import Literal, Any
from dotenv import load_dotenv

# 加载 .env 文件（override=True 确保总是使用文件中的值）
load_dotenv(override=True)

from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# ============================================================================
# AIOP Gateway 配置（公司统一 AI 网关）
# ============================================================================
AIOP_BASE_URL = os.getenv("AIOP_BASE_URL", "https://aiop-gateway.item.com/openai/v1")
AIOP_API_KEY = os.getenv("AIOP_API_KEY", "")
AIOP_APP_CODE = os.getenv("AIOP_APP_CODE", "")
AIOP_TENANT_ID = os.getenv("AIOP_TENANT_ID", "")
AIOP_AGENT_CODE = os.getenv("AIOP_AGENT_CODE", "")
AIOP_AGENT_NAME = os.getenv("AIOP_AGENT_NAME", "")
AIOP_USER_ID = os.getenv("AIOP_USER_ID", "")
AIOP_USER_NAME = os.getenv("AIOP_USER_NAME", "")

# ============================================================================
# Kiro Gateway 配置（本地 Claude 网关 - 旧版）
# ============================================================================
KIRO_BASE_URL = os.getenv("KIRO_BASE_URL", "http://localhost:9000/v1")
KIRO_API_KEY = os.getenv("KIRO_API_KEY", "")

# ============================================================================
# AIClient2API Gateway 配置（本地多模型网关）
# ============================================================================
AICLIENT_BASE_URL = os.getenv("AICLIENT_BASE_URL", "http://localhost:9000")
AICLIENT_API_KEY = os.getenv("AICLIENT_API_KEY", "sk-test")

# ============================================================================
# Local Gateway 配置（局域网部署的本地大模型）
# ============================================================================
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://192.168.1.7:4000/v1")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "sk-your-super-secret-key-2026")

# ============================================================================
# 默认模型配置
# ============================================================================
# 格式: "gateway/provider/model" 或 "gateway/model"
# - aiop/azure/gpt-5.4: AIOP Gateway Azure GPT-5.4
# - aiop/openai/gpt-4: AIOP Gateway OpenAI GPT-4
# - kiro/claude-sonnet-4.5: Kiro Gateway Claude Sonnet
# - aiclient/claude-kiro-oauth/claude-sonnet-4-6: AIClient2API Claude via Kiro
# - aiclient/claude-sonnet-4-6: AIClient2API Claude（简写）
# - local/llama3.2-1b: 局域网本地大模型（推荐）
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "local/llama3.2-1b")


def _log(message: str):
    """延迟导入日志模块，避免循环依赖"""
    try:
        from tools.debug.readlog import logs
        logs.info(message)
    except ImportError:
        print(message)


def _b64_encode(text: str) -> str:
    """Base64 编码（用于 X-Agent-Name 和 X-User-Name）"""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


class LLMLogger(BaseCallbackHandler):
    """LLM 调用日志记录器
    
    记录所有 LLM 请求和响应。
    """
    
    def __init__(self, provider: str = "unknown"):
        self._start_time = None
        self._provider = provider
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 调用开始时记录请求"""
        self._start_time = time.time()
        model = kwargs.get("invocation_params", {}).get("model", "unknown")
        
        _log(f"[{self._provider}] ========== 请求开始 ==========")
        _log(f"[{self._provider}] 模型: {model}")
        _log(f"[{self._provider}] 请求数量: {len(prompts)}")
        
        # 记录请求内容（截断过长的 prompt）
        for i, prompt in enumerate(prompts):
            if len(prompt) > 500:
                prompt_display = prompt[:500] + "...(截断)"
            else:
                prompt_display = prompt
            _log(f"[{self._provider}] 请求 [{i+1}]: {prompt_display}")
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        """LLM 调用结束时记录响应"""
        elapsed = time.time() - self._start_time if self._start_time else 0
        
        _log(f"[{self._provider}] ========== 响应结束 ==========")
        _log(f"[{self._provider}] 耗时: {elapsed:.2f}秒")
        
        # 记录 token 使用情况
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            _log(f"[{self._provider}] Token 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
        
        # 记录响应内容（截断过长的响应）
        for i, generation in enumerate(response.generations):
            if generation:
                text = generation[0].text if generation[0] else ""
                if len(text) > 500:
                    text_display = text[:500] + "...(截断)"
                else:
                    text_display = text
                _log(f"[{self._provider}] 响应 [{i+1}]: {text_display}")
    
    def on_llm_error(self, error, **kwargs):
        """LLM 调用出错时记录错误"""
        _log(f"[{self._provider}] ========== 请求错误 ==========")
        _log(f"[{self._provider}] 错误类型: {type(error).__name__}")
        _log(f"[{self._provider}] 错误信息: {str(error)}")


# 启动时打印模型配置
_log(f"[LLM] 模型配置加载完成:")
_log(f"  - 默认模型: {DEFAULT_MODEL}")
_log(f"  - AIOP Gateway: {AIOP_BASE_URL} ({'已配置' if AIOP_API_KEY else '未配置'})")
_log(f"  - Kiro Gateway: {KIRO_BASE_URL} ({'已配置' if KIRO_API_KEY else '未配置'})")
_log(f"  - AIClient2API: {AICLIENT_BASE_URL} ({'已配置' if AICLIENT_API_KEY else '未配置'})")
_log(f"  - Local Gateway: {LOCAL_BASE_URL} ({'已配置' if LOCAL_API_KEY else '未配置'})")


def get_default_model(agent_name: str | None = None):
    """获取默认模型。"""
    from tools.utils.token_counter import get_token_callback
    callbacks = [get_token_callback(agent_name=agent_name)]
    
    return get_model(model=DEFAULT_MODEL, callbacks=callbacks)


def get_aiop_model(model: str = "azure/gpt-5.4", callbacks: list | None = None):
    """获取 AIOP Gateway 模型。
    
    Args:
        model: 模型名称，格式为 "厂商/模型名"：
            - azure/gpt-5.4: Azure OpenAI GPT-5.4
            - azure/gpt-4: Azure OpenAI GPT-4
            - openai/gpt-4: OpenAI GPT-4
            - openai/gpt-3.5-turbo: OpenAI GPT-3.5 Turbo
            - gemini/gemini-2.5-flash: Google Gemini
        callbacks: 回调处理器列表
    """
    if not AIOP_API_KEY:
        raise ValueError("AIOP_API_KEY 未配置，请在 .env 文件中设置")
    
    # 检查是否使用 JWT Token（以 "eyJ" 开头）
    is_jwt_token = AIOP_API_KEY.startswith("eyJ")
    
    # 如果不是 JWT Token，需要检查 AIOP_APP_CODE
    if not is_jwt_token and not AIOP_APP_CODE:
        raise ValueError("AIOP_APP_CODE 未配置，请在 .env 文件中设置")
    
    # 构建额外的请求头（仅非 JWT Token 方式需要）
    default_headers = {}
    if not is_jwt_token:
        default_headers["X-App-Code"] = AIOP_APP_CODE
        
        if AIOP_TENANT_ID:
            default_headers["X-Tenant-Id"] = AIOP_TENANT_ID
        if AIOP_AGENT_CODE:
            default_headers["X-Agent-Code"] = AIOP_AGENT_CODE
        if AIOP_AGENT_NAME:
            default_headers["X-Agent-Name"] = _b64_encode(AIOP_AGENT_NAME)
        if AIOP_USER_ID:
            default_headers["X-User-Id"] = AIOP_USER_ID
        if AIOP_USER_NAME:
            default_headers["X-User-Name"] = _b64_encode(AIOP_USER_NAME)
    
    # 添加日志记录器
    if callbacks is None:
        callbacks = []
    callbacks.append(LLMLogger("AIOP"))
    
    auth_method = "JWT Token" if is_jwt_token else "API Key + Headers"
    _log(f"[LLM] 创建 AIOP 模型: {model} (认证方式: {auth_method})")
    
    llm = ChatOpenAI(
        model=model,
        api_key=AIOP_API_KEY,
        base_url=AIOP_BASE_URL,
        callbacks=callbacks,
        default_headers=default_headers,
    )
    return llm


def get_kiro_model(model: str = "claude-sonnet-4.5", callbacks: list | None = None):
    """获取 Kiro 模型（通过本地 kiro-gateway）。
    
    Args:
        model: 模型名称：
            - claude-sonnet-4.5: Claude Sonnet 4.5（推荐）
            - claude-sonnet-4-6: Claude Sonnet 4-6
            - claude-haiku-4.5: Claude Haiku 4.5（快速）
            - claude-opus-4.5: Claude Opus 4.5（最强）
            - deepseek-3.2: DeepSeek 3.2
            - qwen3-coder-next: Qwen3 Coder Next
        callbacks: 回调处理器列表
    """
    if not KIRO_API_KEY:
        raise ValueError("KIRO_API_KEY 未配置，请在 .env 文件中设置")
    
    if not KIRO_BASE_URL:
        raise ValueError("KIRO_BASE_URL 未配置，请在 .env 文件中设置")
    
    # 添加日志记录器
    if callbacks is None:
        callbacks = []
    callbacks.append(LLMLogger("Kiro"))
    
    llm = ChatOpenAI(
        model=model,
        api_key=KIRO_API_KEY,
        base_url=KIRO_BASE_URL,
        callbacks=callbacks,
    )
    _log(f"[LLM] 创建 Kiro 模型: {model}")
    return llm


def get_aiclient_model(model: str = "claude-sonnet-4-6", callbacks: list | None = None):
    """获取 AIClient2API 模型（通过本地 AIClient-2-API 网关）。
    
    支持多种模型提供商，通过路径前缀区分：
    - claude-kiro-oauth: Claude via Kiro OAuth
    - gemini-cli-oauth: Gemini via CLI OAuth
    - gemini-antigravity: Gemini via Antigravity
    - qwen-code-oauth: Qwen Code via OAuth
    - grok-custom: Grok via Cookie/SSO
    
    Args:
        model: 模型名称，格式为 "provider/model" 或直接模型名：
            - claude-kiro-oauth/claude-sonnet-4-6: Claude Sonnet 4-6 via Kiro
            - claude-kiro-oauth/claude-opus-4.5: Claude Opus 4.5 via Kiro
            - gemini-cli-oauth/gemini-2.5-flash: Gemini via CLI
            - qwen-code-oauth/qwen3-coder-plus: Qwen Coder
        callbacks: 回调处理器列表
    """
    if not AICLIENT_BASE_URL:
        raise ValueError("AICLIENT_BASE_URL 未配置，请在 .env 文件中设置")
    
    # 解析模型名称
    parts = model.split("/")
    if len(parts) == 2:
        # 格式: provider/model
        provider, specific_model = parts
        base_url = f"{AICLIENT_BASE_URL}/{provider}/v1"
        actual_model = specific_model
    else:
        # 直接模型名，使用 claude-kiro-oauth 作为默认提供商
        base_url = f"{AICLIENT_BASE_URL}/claude-kiro-oauth/v1"
        actual_model = model
    
    # 添加日志记录器
    if callbacks is None:
        callbacks = []
    callbacks.append(LLMLogger("AIClient"))
    
    llm = ChatOpenAI(
        model=actual_model,
        api_key=AICLIENT_API_KEY,
        base_url=base_url,
        callbacks=callbacks,
    )
    _log(f"[LLM] 创建 AIClient2API 模型: {actual_model} (提供商: {provider if len(parts) == 2 else 'claude-kiro-oauth'})")
    return llm


def get_local_model(model: str = "llama3.2-1b", callbacks: list | None = None):
    """获取 Local 模型（通过局域网部署的本地大模型网关）。
    
    Args:
        model: 模型名称：
            - llama3.2-1b: Llama 3.2 1B（默认）
            - 其他本地部署的模型
        callbacks: 回调处理器列表
    """
    if not LOCAL_API_KEY:
        raise ValueError("LOCAL_API_KEY 未配置，请在 .env 文件中设置")
    
    if not LOCAL_BASE_URL:
        raise ValueError("LOCAL_BASE_URL 未配置，请在 .env 文件中设置")
    
    # 添加日志记录器
    if callbacks is None:
        callbacks = []
    callbacks.append(LLMLogger("Local"))
    
    llm = ChatOpenAI(
        model=model,
        api_key=LOCAL_API_KEY,
        base_url=LOCAL_BASE_URL,
        callbacks=callbacks,
    )
    _log(f"[LLM] 创建 Local 模型: {model}")
    return llm


def get_model(
    model: str | None = None,
    callbacks: list | None = None,
    agent_name: str | None = None,
):
    """获取模型。
    
    Args:
        model: 模型名称，格式为 "gateway/provider/model" 或 "gateway/model"
            - "aiop/azure/gpt-5.4": AIOP Gateway Azure GPT-5.4
            - "aiop/openai/gpt-4": AIOP Gateway OpenAI GPT-4
            - "kiro/claude-sonnet-4.5": Kiro Gateway Claude Sonnet
            - "aiclient/claude-sonnet-4-6": AIClient2API Claude（默认 claude-kiro-oauth）
            - "aiclient/claude-kiro-oauth/claude-sonnet-4-6": AIClient2API Claude via Kiro
            - "aiclient/gemini-cli-oauth/gemini-2.5-flash": AIClient2API Gemini
        callbacks: 回调处理器列表
        agent_name: Agent 名称，用于 Token 统计标识
    
    Returns:
        聊天模型实例
    """
    # 如果没有提供回调，使用默认的 Token 回调
    if callbacks is None:
        from tools.utils.token_counter import get_token_callback
        callbacks = [get_token_callback(agent_name=agent_name)]
    
    model_name = model or DEFAULT_MODEL
    _log(f"[LLM] get_model() | model={model_name} | agent={agent_name} | callbacks={[type(c).__name__ for c in callbacks]}")
    
    # 解析格式
    parts = model_name.split("/")
    
    if len(parts) == 4:
        # 格式: gateway/provider/subprovider/model (如 aiclient/claude-kiro-oauth/claude-sonnet-4-6)
        gateway, provider, subprovider, specific_model = parts
        full_model = f"{provider}/{subprovider}/{specific_model}"
    elif len(parts) == 3:
        # 格式: gateway/provider/model 或 gateway/subprovider/model
        gateway, second, third = parts
        if gateway == "aiclient":
            # aiclient/claude-kiro-oauth/claude-sonnet-4-6
            full_model = f"{second}/{third}"
        elif gateway == "aiop":
            # aiop/azure/gpt-5.4
            full_model = f"{second}/{third}"
        else:
            # 其他情况
            full_model = f"{second}/{third}"
    elif len(parts) == 2:
        # 格式: provider/model 或 gateway/model
        first, second = parts
        if first in ("aiop", "kiro", "aiclient", "local"):
            # gateway/model 格式
            gateway = first
            if gateway == "aiop":
                full_model = f"azure/{second}"
            elif gateway == "aiclient":
                full_model = second  # 直接使用模型名，默认 claude-kiro-oauth
            else:
                full_model = second
        else:
            # provider/model 格式，默认使用 AIOP
            gateway = "aiop"
            full_model = model_name
    else:
        # 只有模型名，默认使用 Kiro
        gateway = "kiro"
        full_model = model_name
    
    if gateway == "aiop":
        return get_aiop_model(model=full_model, callbacks=callbacks)
    elif gateway == "kiro":
        return get_kiro_model(model=full_model, callbacks=callbacks)
    elif gateway == "aiclient":
        return get_aiclient_model(model=full_model, callbacks=callbacks)
    elif gateway == "local":
        return get_local_model(model=full_model, callbacks=callbacks)
    else:
        raise ValueError(f"未知的网关: {gateway}。支持的网关: aiop, kiro, aiclient, local")