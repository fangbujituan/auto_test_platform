"""
LangChain 兼容的 ChatModel 适配器。

核心思路
--------
- 不重新实现"调 OpenAI / 通义 / Ollama / AIOP"的逻辑。
- 不持有 API Key，也不在代码里硬编码任何 provider 信息。
- 运行时把 LangChain 的 ``BaseMessage`` 列表转换成 ``ai_service.AIService``
  使用的 ``[{"role": ..., "content": ...}]`` 格式，调用后再把结果包回
  ``ChatResult``。

约束
----
- 必须在 Flask app context 内调用：``AIService`` 要查数据库取 provider 配置。
- ``provider_id=None`` 时使用数据库里 ``is_default=True`` 的提供商。
- 暂不实现 streaming / tool-calling 的原生支持（首版骨架够用，后续按需扩展）。

作者: yandc
"""
from __future__ import annotations

from typing import Any, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field


def _to_ai_service_messages(messages: List[BaseMessage]) -> List[dict]:
    """把 LangChain 消息列表转成 ``AIService`` 接受的格式。"""
    role_map = {
        "system": "system",
        "human": "user",
        "ai": "assistant",
    }
    out: List[dict] = []
    for msg in messages:
        # BaseMessage.type: 'system' | 'human' | 'ai' | 'tool' | ...
        role = role_map.get(msg.type)
        if role is None:
            # 未知类型（如 tool）暂时透传为 user 文本，避免拒绝消息
            role = "user"
        # AIService 目前只支持纯文本 content，复杂类型先 str() 兜底
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        out.append({"role": role, "content": content})
    return out


class DBChatModel(BaseChatModel):
    """
    使用数据库里 AI 提供商配置的 ChatModel。

    Examples
    --------
    >>> from app.flask_app import create_app
    >>> from app.agents.llm import DBChatModel
    >>> app = create_app()
    >>> with app.app_context():
    ...     llm = DBChatModel()  # 用默认提供商
    ...     resp = llm.invoke("用一句话介绍 LangGraph")
    ...     print(resp.content)
    """

    provider_id: Optional[int] = Field(
        default=None,
        description="ai_provider_configs.id；为 None 时使用 is_default=True 的提供商",
    )
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=2048)

    @property
    def _llm_type(self) -> str:
        return "db-provider-chat-model"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    # ------------------------------------------------------------------
    # LangChain 必须实现的方法
    # ------------------------------------------------------------------
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 延迟导入，避免在导入期就强依赖 Flask / DB 环境
        from app.services.ai_service import AIService

        payload = _to_ai_service_messages(messages)
        result = AIService().chat(
            payload,
            provider_id=self.provider_id,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        if "error_code" in result:
            raise RuntimeError(
                f"LLM 调用失败: {result['error_code']} - "
                f"{result.get('error_message')}"
            )

        content = result.get("content", "")
        usage = result.get("usage") or {}
        message = AIMessage(
            content=content,
            response_metadata={"usage": usage},
            usage_metadata=_to_usage_metadata(usage),
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        from app.services.ai_service import AIService

        payload = _to_ai_service_messages(messages)
        for chunk in AIService().chat_stream(
            payload,
            provider_id=self.provider_id,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        ):
            # AIService.chat_stream 在错误时 yield 一个 JSON 字符串；
            # 这里保持简单：把每段都按文本处理，错误 JSON 也会作为文本透传。
            text = chunk if isinstance(chunk, str) else str(chunk)
            if not text:
                continue
            yield ChatGenerationChunk(message=AIMessageChunk(content=text))


def _to_usage_metadata(usage: dict) -> Optional[dict]:
    """把 AIService 返回的 usage 字段尽量映射到 LangChain 的 usage_metadata。"""
    if not usage:
        return None
    # 兼容多种字段命名
    in_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    out_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    total = usage.get("total_tokens") or (in_tokens + out_tokens)
    return {
        "input_tokens": int(in_tokens),
        "output_tokens": int(out_tokens),
        "total_tokens": int(total),
    }
