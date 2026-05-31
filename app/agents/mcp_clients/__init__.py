"""
MCP 客户端集合（agent 这一侧消费的外部 MCP server）。

> 注意区分：``app/mcp_server/`` 是"我们对外暴露的 MCP server"；
> 这里是"我们作为 client 去连别家的 MCP server"。两者方向相反，
> 不要放同一个目录。

每个工厂函数返回一组 LangChain ``Tool``，可直接挂到 agent 上。
"""

from app.agents.mcp_clients.clients import (
    get_chrome_devtools_mcp_tools,
    get_mcp_server_chart_tools,
    get_playwright_mcp_tools,
    get_playwright_mcp_tools_with_auth,
    get_tavily_search_tools,
    get_zhipu_search_mcp_tools,
)

__all__ = [
    "get_zhipu_search_mcp_tools",
    "get_tavily_search_tools",
    "get_playwright_mcp_tools",
    "get_playwright_mcp_tools_with_auth",
    "get_chrome_devtools_mcp_tools",
    "get_mcp_server_chart_tools",
]
