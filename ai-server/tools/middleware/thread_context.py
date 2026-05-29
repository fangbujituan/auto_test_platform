"""
Thread Context 中间件

从 LangGraph 运行时配置中提取 thread_id，
注入到 ContextVar 中，供 TokenCounter 自动关联统计数据。

核心方案：使用 langgraph.config.get_config() 获取当前 RunnableConfig，
从中提取 configurable.thread_id。

注入时机：before_model（每次模型调用前）
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState

from tools.debug.readlog import logs
from tools.utils.token_counter import (
    set_current_thread_id,
    set_current_agent,
    get_current_thread_id,
)


class ThreadContextMiddleware(AgentMiddleware):
    """
    Thread Context 中间件
    
    使用 langgraph.config.get_config() 从 LangGraph 运行时获取 thread_id，
    注入到 ContextVar，供 TokenCallbackHandler 自动关联统计数据。
    """

    def __init__(self, agent_name: str = "unknown"):
        self.agent_name = agent_name
        self._logged_first = False

    @property
    def name(self) -> str:
        return "thread_context"

    def _get_thread_id_from_langgraph(self) -> str | None:
        """通过 langgraph.config.get_config() 获取 thread_id"""
        try:
            from langgraph.config import get_config
            config = get_config()
            if config and isinstance(config, dict):
                configurable = config.get("configurable", {})
                thread_id = configurable.get("thread_id")
                if not self._logged_first:
                    logs.info(f"[ThreadContext] 🔍 get_config() configurable keys={list(configurable.keys())}")
                return thread_id
        except Exception as e:
            if not self._logged_first:
                logs.warning(f"[ThreadContext] get_config() 调用失败: {e}")
        return None

    def _extract_thread_id(self, state: AgentState, runtime: Any) -> str | None:
        """从多个来源提取 thread_id（按优先级）"""
        
        # 方式 1（推荐）: langgraph.config.get_config()
        thread_id = self._get_thread_id_from_langgraph()
        if thread_id:
            return thread_id
        
        # 方式 2: runtime.config["configurable"]["thread_id"]
        if runtime is not None:
            config = getattr(runtime, "config", None)
            if config and isinstance(config, dict):
                configurable = config.get("configurable", {})
                thread_id = configurable.get("thread_id")
                if thread_id:
                    return thread_id
            
            # 方式 3: runtime.context
            ctx = getattr(runtime, "context", None)
            if ctx and isinstance(ctx, dict):
                configurable = ctx.get("configurable", {})
                if isinstance(configurable, dict):
                    thread_id = configurable.get("thread_id")
                    if thread_id:
                        return thread_id
            
            # 方式 4: runtime 直接属性
            thread_id = getattr(runtime, "thread_id", None)
            if thread_id:
                return thread_id
        
        # 方式 5: state 中的 thread_id
        if isinstance(state, dict):
            thread_id = state.get("thread_id")
            if thread_id:
                return thread_id
        
        return None

    def before_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        """同步版本：模型调用前注入 thread_id"""
        self._inject(state, runtime)
        return None

    async def abefore_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        """异步版本：模型调用前注入 thread_id"""
        self._inject(state, runtime)
        return None

    def _inject(self, state: AgentState, runtime: Any):
        """注入 thread_id 和 agent_name 到 ContextVar"""
        # 设置 agent_name
        set_current_agent(self.agent_name)
        
        # 提取 thread_id
        thread_id = self._extract_thread_id(state, runtime)
        
        if thread_id:
            current = get_current_thread_id()
            if current != thread_id:
                set_current_thread_id(thread_id)
                logs.info(f"[ThreadContext] ✅ 注入 thread_id={thread_id}, agent={self.agent_name}")
            self._logged_first = True
        elif not self._logged_first:
            logs.warning(f"[ThreadContext] ⚠️ 未能提取 thread_id | agent={self.agent_name}")
