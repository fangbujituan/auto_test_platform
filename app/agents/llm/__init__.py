"""
Agent LLM 适配层。

把项目数据库里管理的 AI 提供商配置（``ai_provider_configs``）封装成
LangChain ``BaseChatModel`` 接口，让 LangGraph / LangChain 生态的工具链
（chains、tool calling、structured output 等）能直接消费。

所有"用哪个提供商、用什么模型、API Key 是多少"都仍然来自数据库：
agent 这一层只做"形状转换"，不持有任何凭证或路由逻辑。

作者: yandc
"""

from app.agents.llm.bridge import MockLLM, call_real_llm, mock_llm
from app.agents.llm.chat_model import DBChatModel

__all__ = [
    "DBChatModel",
    # 旧版桥接（保留为兼容入口；新代码推荐用 DBChatModel）
    "MockLLM",
    "mock_llm",
    "call_real_llm",
]
