"""
LLM 多网关支持模块。

整合自 ai-server/llms.py，支持以下网关：
- AIOP Gateway: 公司统一 AI 网关（OpenAI/Azure/Gemini）
- Kiro Gateway: 本地 Kiro 网关（Claude/DeepSeek）
- AIClient2API Gateway: 本地多模型网关（Claude/Gemini/Qwen/Grok）

集成了 LangChain 和 Token 统计能力。

作者: yandc
创建时间: 2026-05-30
"""
import os
import base64
from typing import Optional, List, Any
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler

from app.utils.debug.readlog import logs
from app.utils.token_counter import get_token_callback, set_current_agent

# 加载环境变量
load_dotenv(override=True)

# ========================================
# AIOP Gateway 配置
# ========================================
AIOP_BASE_URL = os.getenv("AIOP_BASE_URL", "https://aiop-gateway.item.com/openai/v1")
AIOP_API_KEY = os.getenv("AIOP_API_KEY", "")
AIOP_APP_CODE = os.getenv("AIOP_APP_CODE", "")
AIOP_TENANT_ID = os.getenv("AIOP_TENANT_ID", "")
AIOP_AGENT_CODE = os.getenv("AIOP_AGENT_CODE", "")
AIOP_AGENT_NAME = os.getenv("AIOP_AGENT_NAME", "")
AIOP_USER_ID = os.getenv("AIOP_USER_ID", "")
AIOP_USER_NAME = os.getenv("AIOP_USER_NAME", "")

# ========================================
# Kiro Gateway 配置
# ========================================
KIRO_BASE_URL = os.getenv("KIRO_BASE_URL", "http://localhost:9000/v1")
KIRO_API_KEY = os.getenv("KIRO_API_KEY", "")

# ========================================
# AIClient2API Gateway 配置
# ========================================
AICLIENT_BASE_URL = os.getenv("AICLIENT_BASE_URL", "http://localhost:9000")
AICLIENT_API_KEY = os.getenv("AICLIENT_API_KEY", "sk-test")

# ========================================
# Local Gateway 配置（局域网部署的本地大模型）
# ========================================
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://192.168.1.7:4000/v1")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "sk-your-super-secret-key-2026")

# ========================================
# 默认模型配置
# ========================================
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "local/llama3.2-1b")


class LLMLogger(BaseCallbackHandler):
    """LLM 调用日志记录器。
    
    记录所有 LLM 请求和响应，用于调试和监控。
    """
    
    def __init__(self, provider: str = "unknown"):
        self._start_time = None
        self._provider = provider
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 调用开始时记录请求。"""
        import time
        self._start_time = time.time()
        model = kwargs.get("invocation_params", {}).get("model", "unknown")
        
        logs.info(f"[{self._provider}] ========== 请求开始 ==========")
        logs.info(f"[{self._provider}] 模型: {model}")
        logs.info(f"[{self._provider}] 请求数量: {len(prompts)}")
        
        for i, prompt in enumerate(prompts):
            if len(prompt) > 500:
                prompt_display = prompt[:500] + "...(截断)"
            else:
                prompt_display = prompt
            logs.info(f"[{self._provider}] 请求 [{i+1}]: {prompt_display}")
    
    def on_llm_end(self, response, **kwargs):
        """LLM 调用结束时记录响应。"""
        import time
        elapsed = time.time() - self._start_time if self._start_time else 0
        
        logs.info(f"[{self._provider}] ========== 响应结束 ==========")
        logs.info(f"[{self._provider}] 耗时: {elapsed:.2f}秒")
        
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            logs.info(f"[{self._provider}] Token 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
        
        for i, generation in enumerate(response.generations):
            if generation:
                text = generation[0].text if generation[0] else ""
                if len(text) > 500:
                    text_display = text[:500] + "...(截断)"
                else:
                    text_display = text
                logs.info(f"[{self._provider}] 响应 [{i+1}]: {text_display}")
    
    def on_llm_error(self, error, **kwargs):
        """LLM 调用出错时记录错误。"""
        logs.error(f"[{self._provider}] ========== 请求错误 ==========")
        logs.error(f"[{self._provider}] 错误类型: {type(error).__name__}")
        logs.error(f"[{self._provider}] 错误信息: {str(error)}")


# 启动时打印模型配置
logs.info(f"[LLM] 模型配置加载完成:")
logs.info(f"  - 默认模型: {DEFAULT_MODEL}")
logs.info(f"  - AIOP Gateway: {AIOP_BASE_URL} ({'已配置' if AIOP_API_KEY else '未配置'})")
logs.info(f"  - Kiro Gateway: {KIRO_BASE_URL} ({'已配置' if KIRO_API_KEY else '未配置'})")
logs.info(f"  - AIClient2API: {AICLIENT_BASE_URL} ({'已配置' if AICLIENT_API_KEY else '未配置'})")
logs.info(f"  - Local Gateway: {LOCAL_BASE_URL} ({'已配置' if LOCAL_API_KEY else '未配置'})")


def _b64_encode(text: str) -> str:
    """Base64 编码（用于 X-Agent-Name 和 X-User-Name）。"""
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def get_aiop_model(
    model: str = "azure/gpt-5.4",
    callbacks: Optional[List[BaseCallbackHandler]] = None
):
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
        raise ValueError("AIOP_API_KEY 未配置，请在环境变量中设置")
    
    # 检查是否使用 JWT Token（以 "eyJ" 开头）
    is_jwt_token = AIOP_API_KEY.startswith("eyJ")
    
    # 如果不是 JWT Token，需要检查 AIOP_APP_CODE
    if not is_jwt_token and not AIOP_APP_CODE:
        raise ValueError("AIOP_APP_CODE 未配置，请在环境变量中设置")
    
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
    logs.info(f"[LLM] 创建 AIOP 模型: {model} (认证方式: {auth_method})")
    
    llm = ChatOpenAI(
        model=model,
        api_key=AIOP_API_KEY,
        base_url=AIOP_BASE_URL,
        callbacks=callbacks,
        default_headers=default_headers,
    )
    return llm


def get_kiro_model(
    model: str = "claude-sonnet-4.5",
    callbacks: Optional[List[BaseCallbackHandler]] = None
):
    """获取 Kiro Gateway 模型（通过本地 kiro-gateway）。
    
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
        raise ValueError("KIRO_API_KEY 未配置，请在环境变量中设置")
    
    if not KIRO_BASE_URL:
        raise ValueError("KIRO_BASE_URL 未配置，请在环境变量中设置")
    
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
    logs.info(f"[LLM] 创建 Kiro 模型: {model}")
    return llm


def get_aiclient_model(
    model: str = "claude-sonnet-4-6",
    callbacks: Optional[List[BaseCallbackHandler]] = None
):
    """获取 AIClient2API 模型（通过本地 AIClient-2-API 网关）。
    
    支持多种模型提供商，通过路径前缀区分：
    - claude-kiro-oauth: Claude via Kiro OAuth
    - gemini-cli-oauth: Gemini via CLI OAuth
    - gemini-antigravity: Gemini via Antigravity
    - qwen-code-oauth: Qwen Code via OAuth
    - grok-custom: Grok via Cookie/SSO
    
    Args:
        model: 模型名称，格式为 "提供商/模型名" 或直接模型名：
            - claude-kiro-oauth/claude-sonnet-4-6: Claude Sonnet 4-6 via Kiro
            - claude-kiro-oauth/claude-opus-4.5: Claude Opus 4.5 via Kiro
            - gemini-cli-oauth/gemini-2.5-flash: Gemini via CLI
            - qwen-code-oauth/qwen3-coder-plus: Qwen Coder
        callbacks: 回调处理器列表
    """
    if not AICLIENT_BASE_URL:
        raise ValueError("AICLIENT_BASE_URL 未配置，请在环境变量中设置")
    
    # 解析模型名称
    parts = model.split("/")
    if len(parts) == 2:
        # 格式: 提供商/模型
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
    logs.info(f"[LLM] 创建 AIClient2API 模型: {actual_model} (提供商: {provider if len(parts) == 2 else 'claude-kiro-oauth'})")
    return llm


def get_local_model(
    model: str = "llama3.2-1b",
    callbacks: Optional[List[BaseCallbackHandler]] = None
):
    """获取 Local 模型（通过局域网部署的本地大模型网关）。
    
    Args:
        model: 模型名称：
            - llama3.2-1b: Llama 3.2 1B（默认）
            - 其他本地部署的模型
        callbacks: 回调处理器列表
    """
    if not LOCAL_API_KEY:
        raise ValueError("LOCAL_API_KEY 未配置，请在环境变量中设置")
    
    if not LOCAL_BASE_URL:
        raise ValueError("LOCAL_BASE_URL 未配置，请在环境变量中设置")
    
    # 添加日志记录器
    if callbacks is None:
        callbacks = []
    callbacks.append(LLMLogger("Local"))
    
    # 局域网内的本地 LLM 必须绕开系统/环境代理，否则会被 macOS 系统代理拦截导致超时
    # （httpx 默认 trust_env=True 会读取 macOS Network → Proxies 配置）
    import httpx as _httpx
    sync_client = _httpx.Client(trust_env=False, timeout=120.0)
    async_client = _httpx.AsyncClient(trust_env=False, timeout=120.0)
    
    llm = ChatOpenAI(
        model=model,
        api_key=LOCAL_API_KEY,
        base_url=LOCAL_BASE_URL,
        callbacks=callbacks,
        http_client=sync_client,
        http_async_client=async_client,
    )
    logs.info(f"[LLM] 创建 Local 模型: {model}（已禁用系统代理）")
    return llm


def get_model(
    model: Optional[str] = None,
    callbacks: Optional[List[BaseCallbackHandler]] = None,
    agent_name: Optional[str] = None,
):
    """获取模型。
    
    Args:
        model: 模型名称，格式为 "网关/提供商/模型" 或 "网关/模型"：
            - "aiop/azure/gpt-5.4": AIOP Gateway Azure GPT-5.4
            - "aiop/openai/gpt-4": AIOP Gateway OpenAI GPT-4
            - "kiro/claude-sonnet-4.5": Kiro Gateway Claude Sonnet
            - "aiclient/claude-sonnet-4-6": AIClient2API Claude（默认 claude-kiro-oauth）
            - "aiclient/claude-kiro-oauth/claude-sonnet-4-6": AIClient2API Claude via Kiro
            - "aiclient/gemini-cli-oauth/gemini-2.5-flash": AIClient2API Gemini
            - "local/llama3.2-1b": 局域网本地大模型
        callbacks: 回调处理器列表
        agent_name: Agent 名称（用于 Token 统计标识）
    
    Returns:
        ChatOpenAI 实例
    """
    model_name = model or DEFAULT_MODEL
    logs.info(f"[LLM] get_model() | model={model_name} | agent={agent_name}")
    
    # 设置 Agent 上下文
    if agent_name:
        set_current_agent(agent_name)
    
    # 初始化回调列表
    if callbacks is None:
        callbacks = []
    
    # 添加 Token 统计回调
    token_cb = get_token_callback(agent_name=agent_name)
    if token_cb not in callbacks:
        callbacks.append(token_cb)
    
    # 解析格式
    parts = model_name.split("/")
    
    if len(parts) >= 3 and parts[0] == "aiclient":
        # aiclient/claude-kiro-oauth/claude-sonnet-4-6
        gateway = parts[0]
        full_model = "/".join(parts[1:])
    elif len(parts) >= 2:
        gateway = parts[0]
        if gateway in ("aiop", "kiro", "aiclient", "local"):
            full_model = "/".join(parts[1:])
        else:
            # provider/model 格式，默认使用 AIOP
            gateway = "aiop"
            full_model = model_name
    else:
        # 只有模型名，默认使用 Local
        gateway = "local"
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


def get_default_model(agent_name: Optional[str] = None, callbacks: Optional[List[BaseCallbackHandler]] = None):
    """获取默认模型。
    
    Args:
        agent_name: Agent 名称
        callbacks: 回调处理器列表
    """
    return get_model(model=DEFAULT_MODEL, callbacks=callbacks, agent_name=agent_name)
