"""
Before Agent 中间件模块
在发送给大模型之前记录所有信息到日志
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState

from tools.debug.readlog import logs


class BeforeAgentMiddleware(AgentMiddleware):
    """
    Before Agent 中间件，在模型调用之前记录所有相关信息到日志。
    
    记录的信息包括：
    - 当前时间戳
    - 用户输入内容
    - 系统提示词
    - 历史消息数量
    - 可用工具列表
    """

    @property
    def name(self) -> str:
        """中间件名称"""
        return "before_agent"

    def _format_message(self, message: Any) -> str:
        """格式化消息对象为字符串"""
        if hasattr(message, 'content'):
            content = message.content
            msg_type = type(message).__name__
            return f"[{msg_type}] {content}"
        return str(message)

    def _extract_messages_info(self, messages: list) -> dict:
        """提取消息列表的关键信息"""
        info = {
            "total_count": len(messages),
            "user_messages": [],
            "assistant_messages": [],
            "tool_messages": [],
            "system_messages": [],
        }
        
        for msg in messages:
            msg_type = type(msg).__name__
            content_preview = ""
            
            if hasattr(msg, 'content'):
                content = msg.content
                # 截取前 200 字符作为预览
                if isinstance(content, str):
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                else:
                    content_preview = str(content)[:200]
            
            if msg_type == "HumanMessage":
                info["user_messages"].append(content_preview)
            elif msg_type == "AIMessage":
                info["assistant_messages"].append(content_preview)
            elif msg_type == "ToolMessage":
                info["tool_messages"].append(content_preview)
            elif msg_type == "SystemMessage":
                info["system_messages"].append(content_preview)
        
        return info

    def _log_messages(self, state: AgentState, runtime: Any) -> None:
        """
        记录消息到日志（内部方法）
        
        Args:
            state: 当前 Agent 状态，包含 messages 等
            runtime: 运行时上下文
        """
        # 记录分隔线
        logs.info("=" * 80)
        logs.info("[BeforeAgentMiddleware] 模型调用前日志记录")
        logs.info("=" * 80)
        
        # 获取消息列表
        messages = state.get("messages", [])
        messages_info = self._extract_messages_info(messages)
        
        # 记录消息统计
        logs.info(f"消息总数: {messages_info['total_count']}")
        logs.info(f"用户消息数: {len(messages_info['user_messages'])}")
        logs.info(f"助手消息数: {len(messages_info['assistant_messages'])}")
        logs.info(f"工具消息数: {len(messages_info['tool_messages'])}")
        logs.info(f"系统消息数: {len(messages_info['system_messages'])}")
        
        # 记录最新的用户输入
        if messages_info['user_messages']:
            logs.info("-" * 40)
            logs.info("最新用户输入:")
            for i, msg in enumerate(messages_info['user_messages'][-3:], 1):  # 最近 3 条
                logs.info(f"  [{i}] {msg}")
        
        # 记录最近的助手回复
        if messages_info['assistant_messages']:
            logs.info("-" * 40)
            logs.info("最近助手回复:")
            for i, msg in enumerate(messages_info['assistant_messages'][-2:], 1):  # 最近 2 条
                logs.info(f"  [{i}] {msg}")
        
        # 记录工具调用结果
        if messages_info['tool_messages']:
            logs.info("-" * 40)
            logs.info("工具调用结果:")
            for i, msg in enumerate(messages_info['tool_messages'][-3:], 1):  # 最近 3 条
                logs.info(f"  [{i}] {msg}")
        
        # 记录完整消息详情（调试级别）
        logs.info("-" * 40)
        logs.info("完整消息列表:")
        for i, msg in enumerate(messages):
            logs.info(f"  [{i}] {self._format_message(msg)}")
        
        logs.info("=" * 80)

    def before_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        """
        同步版本：在模型调用之前运行，记录所有信息到日志。
        
        Args:
            state: 当前 Agent 状态，包含 messages 等
            runtime: 运行时上下文
            
        Returns:
            None（不修改状态，仅记录日志）
        """
        self._log_messages(state, runtime)
        return None

    async def abefore_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        """
        异步版本：在模型调用之前运行，记录所有信息到日志。
        
        LangGraph 使用异步执行（astream/ainvoke），所以需要实现此方法。
        
        Args:
            state: 当前 Agent 状态，包含 messages 等
            runtime: 运行时上下文
            
        Returns:
            None（不修改状态，仅记录日志）
        """
        self._log_messages(state, runtime)
        return None
