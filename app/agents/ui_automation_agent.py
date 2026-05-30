"""
UI 自动化 Agent 工厂。

迁移自 ai-server/tools/core/agent_factory.py。

基于 deepagents 的 SubAgent 架构，装配三层中间件 + Playwright/Chart MCP 工具，
对外暴露 `make_agent` 异步上下文管理器（保持 MCP session 存活直到 agent 结束）。

使用方式：
    from app.agents.ui_automation_agent import make_agent

    async with make_agent() as agent:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": "..."}]})

也可作为 LangGraph API 的 graph 入口：
    from app.agents.ui_automation_agent import agent
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import anyio
from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.pregel import Pregel

from app.agents.prompts import SYSTEM_PROMPT
from app.services.llm_gateway import get_model
from app.utils.debug.readlog import logs
from app.utils.middleware import (
    BeforeAgentMiddleware,
    DOMCleanerMiddleware,
    ThreadContextMiddleware,
    TokenControlMiddleware,
)


# ============================================================================
# Token 控制阈值（可通过环境变量调整）
# ============================================================================

# 触发摘要的 token 阈值，默认 120K（DeepSeek 128K 上下文的 ~93%）
_TRIGGER_TOKENS = int(os.getenv("UI_AGENT_TRIGGER_TOKENS", "120000"))
# 摘要后保留的最近消息条数
_KEEP_MESSAGES = int(os.getenv("UI_AGENT_KEEP_MESSAGES", "50"))
# Agent 名称（用于 Token 统计）
_AGENT_NAME = os.getenv("UI_AGENT_NAME", "agent")


@asynccontextmanager
async def make_agent() -> AsyncIterator[Pregel]:
    """创建 UI 自动化 Agent。

    保持 MCP session 在 agent 生命周期内存活，退出时自动清理资源。

    集成三层能力：
    1. DOM 清理中间件 — 自动清理 Playwright 工具返回的 DOM，降低噪音
    2. Token 控制中间件 — 超阈值时自动摘要历史，避免上下文溢出
    3. Thread Context 中间件 — 注入 thread_id 用于跨调用追踪

    工具来源：Playwright MCP + Chart MCP（@antv/mcp-server-chart）
    """
    # Playwright MCP（浏览器自动化）
    playwright_client = MultiServerMCPClient(
        {
            "playwright": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest"],
            }
        }
    )

    # Chart MCP（图表生成）
    chart_client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )

    # 主 agent 中间件链
    # 顺序很重要：ThreadContext → 日志 → DOM清理 → Token控制
    dom_middleware = DOMCleanerMiddleware()
    logs.info(f"[ui_agent] 创建 DOMCleanerMiddleware 实例: {id(dom_middleware)}")

    middleware = [
        # 注入 thread_id 到 ContextVar，供其他中间件/工具使用
        ThreadContextMiddleware(agent_name=_AGENT_NAME),
        # 调用日志
        BeforeAgentMiddleware(),
        # 在主 agent 层面拦截工具输出，清理 DOM
        dom_middleware,
        # Token 超限时自动摘要历史，保留最近 N 条
        TokenControlMiddleware(
            model=get_model(agent_name=_AGENT_NAME),
            trigger_tokens=_TRIGGER_TOKENS,
            keep_messages=_KEEP_MESSAGES,
        ),
    ]

    try:
        async with playwright_client.session("playwright") as playwright_session, \
                chart_client.session("mcp_chart_server") as chart_session:

            # 加载并合并两组工具
            playwright_tools = await load_mcp_tools(playwright_session)
            chart_tools = await load_mcp_tools(chart_session)
            all_tools = playwright_tools + chart_tools

            model = get_model(agent_name=_AGENT_NAME)

            logs.info(
                f"[ui_agent] 装配完成 | tools={len(all_tools)} "
                f"| middleware={[type(m).__name__ for m in middleware]}"
            )

            agent_graph = create_deep_agent(
                tools=all_tools,
                system_prompt=SYSTEM_PROMPT,
                model=model,
                middleware=middleware,
                # 主 agent 已配置完整中间件，不再单独定义 subagents
            )
            logs.info("[ui_agent] create_deep_agent 完成")

            yield agent_graph

    except (anyio.BrokenResourceError, BaseExceptionGroup) as e:
        # MCP 会话在服务关闭时可能抛出这些异常，属于正常关闭流程
        if isinstance(e, BaseExceptionGroup):
            broken = [exc for exc in e.exceptions if isinstance(exc, anyio.BrokenResourceError)]
            if len(broken) == len(e.exceptions):
                logs.info("[ui_agent] MCP 会话已正常关闭")
            else:
                logs.warning(f"[ui_agent] MCP 会话关闭时出现异常: {e}")
        else:
            logs.info("[ui_agent] MCP 会话资源已释放")
    except Exception as e:
        logs.error(f"[ui_agent] Agent 运行异常: {e}")
        raise


# 别名，便于作为 LangGraph API 的 graph 入口
agent = make_agent


__all__ = ["make_agent", "agent"]
