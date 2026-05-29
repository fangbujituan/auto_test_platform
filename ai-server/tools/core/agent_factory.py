"""
Agent 工厂模块
提供创建 LangGraph Agent 的工厂函数

架构说明：
- deepagents 使用 SubAgent 架构，工具调用发生在子 agent 层面
- 需要通过 subagents 参数配置子 agent 的中间件
- 自定义的 general-purpose SubAgent 会覆盖默认配置
"""

import anyio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal

from tools.debug.readlog import logs
from tools.middleware.token_control import TokenControlMiddleware
from llms import get_model
from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.pregel import Pregel

from tools.middleware.dom_cleaner import DOMCleanerMiddleware
from tools.middleware.logging import BeforeAgentMiddleware
from tools.middleware.thread_context import ThreadContextMiddleware


# ============================================================================
# 常量定义
# ============================================================================

# General-purpose SubAgent 的系统提示词
GENERAL_PURPOSE_SYSTEM_PROMPT = """In order to complete the objective that the user asks of you, you have access to a number of standard tools.

【重要提示】Playwright 选择器语法：
- ✅ 使用文本选择器：text="Username" 或 get_text("Username")
- ✅ 使用 Playwright 文本定位：label:has-text("Username")
- ✅ 使用标准 CSS 选择器：label[for="inputUserName"]
- ✅ 使用属性选择器：[data-testid="username"]
- ❌ 不要使用 jQuery 语法（如 :contains("Username")），Playwright 不支持
- ❌ 不要使用 jQuery 的伪类选择器

【DOM 已优化】
你看到的 HTML 已经过优化处理，移除了 CSS、样式、脚本等冗余信息，只保留了页面元素、关键属性和文本内容，这有助于你更准确地定位元素。
"""

# General-purpose SubAgent 的描述
GENERAL_PURPOSE_DESCRIPTION = "General-purpose agent for researching complex questions, searching for files and content, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. This agent has access to all tools as the main agent."


# ============================================================================
# Agent 工厂函数
# ============================================================================

@asynccontextmanager
async def make_agent() -> AsyncIterator[Pregel]:
    """
    创建 agent 的工厂函数，使用 asynccontextmanager 保持 MCP session 存活。

    这是 LangGraph API 推荐的方式：
    - session 在 agent 生命周期内保持活跃
    - 退出时自动清理资源
    - 同时支持 Playwright 和 Chart MCP 服务
    - 包含两层对话长度控制机制：
      1. DOM 清理（第 1 层）：自动清理 Playwright 返回的 DOM
      2. 对话历史总结（第 2 层）：当 token 超过 64K 时总结历史

    架构说明：
    - deepagents 使用 SubAgent 架构
    - 工具调用发生在子 agent (general-purpose) 层面
    - 通过自定义 subagents 配置，在子 agent 中添加 DOMCleanerMiddleware
    """
    # 创建 Playwright MCP client
    playwright_client = MultiServerMCPClient(
        {
            "playwright": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest"],
            }
        }
    )

    # 创建 Chart MCP client
    chart_client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )

    # 模型配置已由 llms.py 的 get_model() 函数统一管理（通过 kiro-gateway）

    # 定义系统提示词（已优化，包含选择器语法指南）
    SYSTEM_PROMPT = """你是一个专业的Web自动化测试助手和数据可视化专家，可以使用Playwright来控制浏览器完成各种任务，也可以生成各种图表。

    你可以：
    - 使用 Playwright 控制浏览器：打开网页、点击元素、填写表单、截图、等待元素加载、执行JavaScript代码
    - 使用 Chart 工具生成图表：柱状图、折线图、饼图、散点图等，支持数据可视化

    请根据用户的指令，使用提供的工具来完成浏览器自动化任务和数据可视化任务。
    """

    # 主 agent 的中间件配置
    # 重要：工具调用可能在主 agent 层面发生（不经过 subagent）
    # 所以需要在主 agent 的 middleware 中也添加 DOMCleanerMiddleware
    dom_middleware = DOMCleanerMiddleware()
    logs.info(f"[agent_factory] 创建 DOMCleanerMiddleware 实例: {id(dom_middleware)}")
    
    middleware = [
        # Thread Context 中间件（最先执行，注入 thread_id 到 ContextVar）
        ThreadContextMiddleware(agent_name="agent"),
        
        # 日志记录中间件
        BeforeAgentMiddleware(),
        
        # DOM 清理中间件 - 在主 agent 层面拦截工具输出
        dom_middleware,

        # Token 控制中间件（替代 SummarizationMiddleware）
        # 使用 Overwrite 直接替换 messages，避免发送 remove 消息
        # 支持历史摘要：保留关键信息，避免丢失上下文
        # 触发阈值：5000 tokens（测试用）
        # 保留消息：最近 50 条
        TokenControlMiddleware(
            model=get_model(agent_name="agent"),
            trigger_tokens=120000,  # 正常值：DeepSeek 128K 的 93%
            keep_messages=50,
        ),
    ]

    # 同时使用两个 session
    # 使用 try-except 包裹整个 async with 块，捕获会话关闭时的 BrokenResourceError
    try:
        async with playwright_client.session("playwright") as playwright_session, \
                  chart_client.session("mcp_chart_server") as chart_session:

            # 分别加载工具
            playwright_tools = await load_mcp_tools(playwright_session)
            chart_tools = await load_mcp_tools(chart_session)

            # 合并工具列表
            all_tools = playwright_tools + chart_tools

            model = get_model(agent_name="agent")

            logs.info(f"[agent_factory] 配置完成，准备调用 create_deep_agent")
            logs.info(f"[agent_factory] 主 agent middleware 数量: {len(middleware)}")
            logs.info(f"[agent_factory] 主 agent middleware 类型: {[type(m).__name__ for m in middleware]}")

            # 创建 agent (注意: tools 和 instructions 是位置参数)
            logs.info(f"[agent_factory] 调用 create_deep_agent...")
            agent = create_deep_agent(
                tools=all_tools,
                system_prompt=SYSTEM_PROMPT,
                model=model,
                middleware=middleware,
                # 不需要单独配置 subagents，因为主 agent 的 middleware 已经包含 DOMCleanerMiddleware
            )
            logs.info(f"[agent_factory] create_deep_agent 完成")

            # yield agent，session 会保持存活直到请求处理完成
            yield agent
            
    except (anyio.BrokenResourceError, BaseExceptionGroup) as e:
        # MCP 会话在服务器关闭时可能抛出这些异常
        # 这是正常关闭流程，不需要打印错误日志
        if isinstance(e, BaseExceptionGroup):
            broken_errors = [exc for exc in e.exceptions if isinstance(exc, anyio.BrokenResourceError)]
            if len(broken_errors) == len(e.exceptions):
                logs.info("[agent_factory] MCP 会话已正常关闭")
            else:
                logs.warning(f"[agent_factory] MCP 会话关闭时出现异常: {e}")
        else:
            logs.info("[agent_factory] MCP 会话资源已释放")
    except Exception as e:
        logs.error(f"[agent_factory] Agent 运行异常: {e}")
        raise


# 导出 make_agent 供 LangGraph API 使用
agent = make_agent
