"""
Token 控制中间件模块
替代 SummarizationMiddleware，使用 Overwrite 直接替换 messages，避免发送 remove 消息

问题背景：
- SummarizationMiddleware 触发时会发送 type: "remove" 的消息
- LangGraph Studio UI 不支持 remove 消息类型，导致前端报错
- 解决方案：使用 Overwrite 直接替换 messages 列表，并生成摘要保留历史信息

功能特点：
1. 滑动窗口：保留最近 N 条完整消息
2. 智能摘要：对旧消息生成摘要，保留关键信息
3. 前端兼容：不发送 remove 消息
4. 可配置：支持自定义模型、阈值、保留数量

参考文档：
- https://reference.langchain.com/python/langgraph/types/Overwrite
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import Overwrite

from tools.debug.readlog import logs
from tools.utils.token_counter import TokenCounter, get_current_thread_id


# 摘要提示词
SUMMARY_PROMPT = """请对以下对话历史进行简洁的摘要，保留关键信息：
1. 用户的意图和目标
2. 已完成的操作和结果
3. 重要的上下文信息（如 URL、页面状态、错误信息等）
4. 未完成的任务

要求：
- 摘要长度控制在 {max_length} 字以内
- 使用中文
- 突出关键操作和结果
- 忽略无关细节

对话历史：
{conversation}
"""


class TokenControlMiddleware(AgentMiddleware):
    """
    Token 控制中间件 - 替代 SummarizationMiddleware
    
    功能：
    1. 滑动窗口：保留最近 N 条完整消息
    2. 智能摘要：对旧消息生成摘要，保留关键信息
    3. 前端兼容：使用 Overwrite 直接替换，不发送 remove 消息
    
    使用方式：
        from langchain.chat_models import init_chat_model
        
        middleware = [
            # ...其他中间件...
            TokenControlMiddleware(
                model=init_chat_model("deepseek:deepseek-chat"),
                trigger_tokens=100000,
                keep_messages=50,
            ),
        ]
    """

    @property
    def name(self) -> str:
        """中间件名称"""
        return "token_control"

    def __init__(
        self,
        model: BaseChatModel = None,
        trigger_tokens: int = 100000,
        keep_messages: int = 50,
        summarize_threshold: int = 10,
        max_summary_length: int = 8000,
    ):
        """
        初始化 Token 控制中间件
        
        Args:
            model: LLM 模型，用于生成摘要（可选，不提供则直接裁剪）
            trigger_tokens: 触发阈值（token 数量），默认 100000（DeepSeek 128K 的 90%）
            keep_messages: 保留的完整消息数，默认 50 条
            summarize_threshold: 触发总结的最小消息数，默认 10 条（太少不值得总结）
            max_summary_length: 摘要最大字数，默认 5000
        """
        super().__init__()
        self.model = model
        self.trigger_tokens = trigger_tokens
        self.keep_messages = keep_messages
        self.summarize_threshold = summarize_threshold
        self.max_summary_length = max_summary_length
        
        logs.info(f"[TokenControlMiddleware] 初始化完成")
        logs.info(f"  - 触发阈值: {trigger_tokens} tokens")
        logs.info(f"  - 保留消息数: {keep_messages}")
        logs.info(f"  - 摘要最大长度: {self.max_summary_length} 字")
        logs.info(f"  - 总结功能: {'启用' if model else '禁用'}")

    def _count_tokens(self, messages: list) -> int:
        """
        估算 token 数量（近似计算）
        
        使用字符数估算：
        - 英文：约 4 字符 = 1 token
        - 中文：约 1.5 字符 = 1 token
        - 综合估算：约 3 字符 = 1 token（保守估计）
        
        Args:
            messages: 消息列表
            
        Returns:
            估算的 token 数量
        """
        total_chars = 0
        for msg in messages:
            if hasattr(msg, 'content'):
                content = msg.content
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    # 处理多模态内容
                    for item in content:
                        if isinstance(item, dict):
                            if 'text' in item:
                                total_chars += len(item['text'])
                            elif 'base64' in item:
                                # Base64 图片估算为固定 token 数
                                total_chars += 1000
                        elif isinstance(item, str):
                            total_chars += len(item)
        
        # 综合估算：约 3 字符 = 1 token
        return total_chars // 3

    def _format_messages_for_summary(self, messages: list) -> str:
        """
        将消息列表格式化为用于总结的文本
        
        Args:
            messages: 消息列表
            
        Returns:
            格式化后的文本
        """
        lines = []
        for msg in messages:
            msg_type = type(msg).__name__
            
            # 获取消息内容
            content = ""
            if hasattr(msg, 'content'):
                raw_content = msg.content
                if isinstance(raw_content, str):
                    content = raw_content[:500]  # 截断过长的消息
                    if len(raw_content) > 500:
                        content += "...[截断]"
                elif isinstance(raw_content, list):
                    # 处理多模态内容
                    text_parts = []
                    for item in raw_content:
                        if isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'][:200])
                        elif isinstance(item, str):
                            text_parts.append(item[:200])
                    content = " | ".join(text_parts)[:500]
            
            # 格式化消息类型
            if isinstance(msg, HumanMessage):
                prefix = "[用户]"
            elif isinstance(msg, AIMessage):
                prefix = "[AI]"
            elif isinstance(msg, ToolMessage):
                prefix = "[工具结果]"
            elif isinstance(msg, SystemMessage):
                prefix = "[系统]"
            else:
                prefix = f"[{msg_type}]"
            
            lines.append(f"{prefix} {content}")
        
        return "\n".join(lines)

    def _summarize_messages(self, messages: list) -> str:
        """
        使用 LLM 生成消息摘要
        
        Args:
            messages: 需要总结的消息列表
            
        Returns:
            摘要文本
        """
        if not self.model:
            logs.warning("[TokenControlMiddleware] 未配置模型，无法生成摘要")
            return None
        
        if len(messages) < self.summarize_threshold:
            logs.info(f"[TokenControlMiddleware] 消息数 {len(messages)} < {self.summarize_threshold}，跳过总结")
            return None
        
        try:
            # 格式化消息
            conversation = self._format_messages_for_summary(messages)
            
            logs.info(f"[TokenControlMiddleware] 开始生成摘要，输入长度: {len(conversation)} 字符")
            
            # 调用 LLM 生成摘要
            prompt = SUMMARY_PROMPT.format(conversation=conversation, max_length=self.max_summary_length)
            response = self.model.invoke(prompt)
            
            summary = response.content if hasattr(response, 'content') else str(response)
            
            # 确保摘要不超过最大长度
            if len(summary) > self.max_summary_length:
                logs.info(f"[TokenControlMiddleware] 摘要超长 ({len(summary)} > {self.max_summary_length})，进行截断")
                summary = summary[:self.max_summary_length] + "...[已截断]"
            
            logs.info(f"[TokenControlMiddleware] 摘要生成完成，长度: {len(summary)} 字符")
            
            return summary
            
        except Exception as e:
            logs.error(f"[TokenControlMiddleware] 摘要生成失败: {e}")
            return None

    def _get_pending_tool_calls(self, messages: list) -> set:
        """
        获取消息序列中未完成的 tool_call_id 集合
        
        规则：
        - AIMessage 可能有 tool_calls 属性（包含多个 tool_call）
        - 每个 tool_call 有 id 属性
        - ToolMessage 有 tool_call_id 属性，表示响应对应的 tool_call
        
        Args:
            messages: 消息列表
            
        Returns:
            未完成的 tool_call_id 集合
        """
        pending_tool_calls = set()
        
        for msg in messages:
            # 收集 AIMessage 中的 tool_calls
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if isinstance(tool_call, dict) and 'id' in tool_call:
                        pending_tool_calls.add(tool_call['id'])
                    elif hasattr(tool_call, 'id'):
                        pending_tool_calls.add(tool_call.id)
            
            # 移除已响应的 ToolMessage
            if isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
                pending_tool_calls.discard(msg.tool_call_id)
        
        return pending_tool_calls
    
    def _ensure_tool_call_completeness(self, recent_messages: list, old_messages: list) -> list:
        """
        确保消息序列完整性：如果保留的消息包含未完成的 tool_calls，
        从旧消息中找到对应的 ToolMessage 并包含进来。
        
        Args:
            recent_messages: 保留的最近消息
            old_messages: 被裁剪的旧消息
            
        Returns:
            完整的消息列表
        """
        # 检查是否有未完成的 tool_calls
        pending_tool_calls = self._get_pending_tool_calls(recent_messages)
        
        if not pending_tool_calls:
            # 没有未完成的 tool_calls，直接返回
            return recent_messages
        
        logs.warning(f"[TokenControlMiddleware] ⚠️ 发现未完成的 tool_calls: {pending_tool_calls}")
        logs.info("[TokenControlMiddleware] 正在从旧消息中查找对应的 ToolMessage...")
        
        # 从旧消息中查找对应的 ToolMessage（从后向前搜索）
        tool_messages_to_add = []
        remaining_pending = pending_tool_calls.copy()
        
        for msg in reversed(old_messages):
            if isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
                if msg.tool_call_id in remaining_pending:
                    tool_messages_to_add.append(msg)
                    remaining_pending.discard(msg.tool_call_id)
                    logs.info(f"  - 找到 ToolMessage: tool_call_id={msg.tool_call_id}")
                    
                    if not remaining_pending:
                        break
        
        if tool_messages_to_add:
            # 将 ToolMessage 按原始顺序排列（从早到晚）
            tool_messages_to_add.reverse()
            
            # 插入到最近消息的开头
            new_messages = tool_messages_to_add + recent_messages
            
            logs.info(f"[TokenControlMiddleware] ✅ 已补全 {len(tool_messages_to_add)} 个 ToolMessage")
            
            # 再次验证完整性
            still_pending = self._get_pending_tool_calls(new_messages)
            if still_pending:
                logs.error(f"[TokenControlMiddleware] ❌ 仍有未完成的 tool_calls: {still_pending}")
                # 尝试移除包含这些 tool_calls 的 AIMessage
                new_messages = self._remove_incomplete_tool_calls(new_messages, still_pending)
            
            return new_messages
        
        # 没有找到对应的 ToolMessage，需要移除包含这些 tool_calls 的 AIMessage
        logs.warning("[TokenControlMiddleware] ⚠️ 未找到对应的 ToolMessage，移除包含未完成 tool_calls 的 AIMessage")
        return self._remove_incomplete_tool_calls(recent_messages, pending_tool_calls)
    
    def _remove_incomplete_tool_calls(self, messages: list, pending_tool_calls: set) -> list:
        """
        移除包含未完成 tool_calls 的 AIMessage
        
        Args:
            messages: 消息列表
            pending_tool_calls: 未完成的 tool_call_id 集合
            
        Returns:
            清理后的消息列表
        """
        cleaned_messages = []
        
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                # 检查这条 AIMessage 的 tool_calls 是否在 pending 中
                msg_tool_call_ids = set()
                for tool_call in msg.tool_calls:
                    if isinstance(tool_call, dict) and 'id' in tool_call:
                        msg_tool_call_ids.add(tool_call['id'])
                    elif hasattr(tool_call, 'id'):
                        msg_tool_call_ids.add(tool_call.id)
                
                # 如果有未完成的 tool_call，移除这条消息
                if msg_tool_call_ids & pending_tool_calls:
                    logs.warning(f"[TokenControlMiddleware] 移除包含未完成 tool_calls 的 AIMessage: {msg_tool_call_ids}")
                    continue
            
            cleaned_messages.append(msg)
        
        return cleaned_messages
    
    def _validate_message_sequence(self, messages: list) -> bool:
        """
        验证消息序列完整性
        
        Args:
            messages: 消息列表
            
        Returns:
            是否完整
        """
        pending_tool_calls = self._get_pending_tool_calls(messages)
        
        if pending_tool_calls:
            logs.error(f"[TokenControlMiddleware] ❌ 消息序列不完整，未完成的 tool_calls: {pending_tool_calls}")
            return False
        
        return True

    def before_model(self, state, runtime) -> dict[str, Any] | None:
        """
        同步版本：模型调用前检查 token 数量
        
        如果 token 数量超过阈值：
        1. 保留最近 N 条完整消息
        2. 对旧消息生成摘要（如果配置了模型）
        3. 将摘要作为 SystemMessage 插入开头
        4. 使用 Overwrite 替换整个消息列表
        
        Args:
            state: 当前 Agent 状态
            runtime: 运行时上下文
            
        Returns:
            状态更新字典，或 None（不更新）
        """
        # 🔧 强化：检查消息序列完整性
        messages = state.get("messages", [])
        if messages:
            self._log_message_sequence_status(messages)
        
        return self._process_token_control(state, runtime)

    async def abefore_model(self, state, runtime) -> dict[str, Any] | None:
        """
        异步版本：模型调用前检查 token 数量
        
        LangGraph 使用异步执行（astream/ainvoke），所以需要实现此方法。
        
        Args:
            state: 当前 Agent 状态
            runtime: 运行时上下文
            
        Returns:
            状态更新字典，或 None（不更新）
        """
        # 🔧 强化：检查消息序列完整性
        messages = state.get("messages", [])
        if messages:
            self._log_message_sequence_status(messages)
        
        return self._process_token_control(state, runtime)
    
    def _log_message_sequence_status(self, messages: list):
        """
        记录消息序列状态（用于调试）
        
        Args:
            messages: 消息列表
        """
        pending = self._get_pending_tool_calls(messages)
        
        if pending:
            logs.warning(f"[TokenControlMiddleware] ⚠️ 检测到未完成的 tool_calls: {pending}")
            # 打印详细的消息序列信息
            for i, msg in enumerate(messages[-10:]):  # 只打印最近 10 条
                msg_type = type(msg).__name__
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    tool_call_ids = [tc.get('id', tc.id) if isinstance(tc, dict) else tc.id for tc in msg.tool_calls]
                    logs.warning(f"  [{i}] {msg_type}: tool_calls={tool_call_ids}")
                elif isinstance(msg, ToolMessage):
                    logs.warning(f"  [{i}] {msg_type}: tool_call_id={msg.tool_call_id}")
                else:
                    logs.debug(f"  [{i}] {msg_type}")

    def _process_token_control(self, state, runtime) -> dict[str, Any] | None:
        """
        处理 Token 控制的核心逻辑（同步和异步共用）
        
        如果 token 数量超过阈值：
        1. 保留最近 N 条完整消息
        2. 对旧消息生成摘要（如果配置了模型）
        3. 将摘要作为 SystemMessage 插入开头
        4. 确保消息序列完整性（tool_calls 和 ToolMessage 配对）
        5. 使用 Overwrite 替换整个消息列表
        
        Args:
            state: 当前 Agent 状态
            runtime: 运行时上下文
            
        Returns:
            状态更新字典，或 None（不更新）
        """
        messages = state.get("messages", [])
        
        if not messages:
            return None
        
        # 优先使用模型返回的真实 input_tokens（包含 system_prompt + tool schema）
        # 字符估算只能看到 messages 内容，看不到隐藏的 ~30K tool schema 开销
        token_count = None
        thread_id = get_current_thread_id()
        if thread_id:
            try:
                counter = TokenCounter()
                real_tokens = counter.get_last_input_tokens(thread_id)
                if real_tokens and real_tokens > 0:
                    token_count = real_tokens
                    logs.info(f"[TokenControlMiddleware] 使用真实 input_tokens: {token_count} (thread={thread_id})")
            except Exception as e:
                logs.warning(f"[TokenControlMiddleware] 获取真实 token 失败: {e}")
        
        if token_count is None:
            token_count = self._count_tokens(messages)
            logs.info(f"[TokenControlMiddleware] 使用字符估算: {token_count}")
        
        message_count = len(messages)
        
        logs.info(f"[TokenControlMiddleware] 当前状态:")
        logs.info(f"  - 消息数量: {message_count}")
        logs.info(f"  - Token 估算: {token_count}")
        logs.info(f"  - 触发阈值: {self.trigger_tokens}")
        
        if token_count > self.trigger_tokens:
            logs.info(f"[TokenControlMiddleware] ⚠️ 触发 Token 控制!")
            
            # 保留最近 N 条消息
            recent_messages = messages[-self.keep_messages:]
            
            # 需要处理的消息（被裁剪的）
            old_messages = messages[:-self.keep_messages]
            
            new_messages = []
            
            # 如果有模型，尝试生成摘要
            if self.model and len(old_messages) >= self.summarize_threshold:
                summary = self._summarize_messages(old_messages)
                
                if summary:
                    # 创建摘要消息
                    summary_message = SystemMessage(
                        content=f"[历史对话摘要]\n{summary}"
                    )
                    new_messages.append(summary_message)
                    logs.info(f"  - 已添加历史摘要")
                else:
                    logs.info(f"  - 摘要生成失败，直接裁剪")
            else:
                logs.info(f"  - 跳过摘要生成（{'未配置模型' if not self.model else '消息数不足'}）")
            
            # 🔧 关键修复：确保消息序列完整性
            # 如果保留的消息包含未完成的 tool_calls，需要补全对应的 ToolMessage
            recent_messages = self._ensure_tool_call_completeness(recent_messages, old_messages)
            
            # 添加最近的消息
            new_messages.extend(recent_messages)
            
            # 🔧 二次验证：确保最终消息序列完整
            if not self._validate_message_sequence(new_messages):
                logs.error("[TokenControlMiddleware] ❌ 消息序列验证失败，尝试紧急修复...")
                # 紧急修复：移除所有包含 tool_calls 的 AIMessage
                pending = self._get_pending_tool_calls(new_messages)
                new_messages = self._remove_incomplete_tool_calls(new_messages, pending)
                
                # 再次验证
                if not self._validate_message_sequence(new_messages):
                    logs.error("[TokenControlMiddleware] ❌ 紧急修复失败，放弃本次裁剪")
                    return None
            
            # 计算新的 token 数量
            new_token_count = self._count_tokens(new_messages)
            reduction = (token_count - new_token_count) / token_count * 100 if token_count > 0 else 0
            
            logs.info(f"  - 原始消息: {message_count} 条")
            logs.info(f"  - 保留消息: {len(recent_messages)} 条")
            logs.info(f"  - 新消息列表: {len(new_messages)} 条")
            logs.info(f"  - Token 变化: {token_count} -> {new_token_count} (减少 {reduction:.1f}%)")
            
            # 关键：使用 Overwrite 直接替换，不发送 remove 消息
            return {"messages": Overwrite(value=new_messages)}
        
        return None