"""
MCP 客户端工厂函数集合。

提供各类外部 MCP server 的连接封装，返回 LangChain 兼容的工具列表，
可直接传入 ``create_react_agent`` 等 LangGraph 入口。

迁移自 ``ai-server/tools/mcp/clients.py``，对外接口保持一致。

注意
----
- ``asyncio.run`` 只能在没有运行中的事件循环时调用。如果在 Flask 异步上下文
  或已有 event loop 的进程里调用，需要改用 ``await client.get_tools()``。
- 默认存放登录态文件的相对路径基准是 **本仓库根目录**，因此 ``__file__``
  从 ``app/agents/mcp_clients/clients.py`` 向上回退三级到 ``auto_test_platform/``。

作者: yandc（迁移自 ai-server）
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


# ---------------------------------------------------------------------------
# 远端搜索类 MCP
# ---------------------------------------------------------------------------
def get_zhipu_search_mcp_tools():
    """获取智谱搜索 MCP 工具。"""
    client = MultiServerMCPClient(
        {
            "search": {
                "url": "https://open.bigmodel.cn/api/mcp/web_search/sse?Authorization=615ff211360f41f59a4b99787132badf.8Yn84taE1Vzv0izs",
                "transport": "sse",
            }
        }
    )
    return asyncio.run(client.get_tools())


def get_tavily_search_tools():
    """获取 Tavily 搜索 MCP 工具。"""
    client = MultiServerMCPClient(
        {
            "search": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "streamable_http",
            }
        }
    )
    return asyncio.run(client.get_tools())


# ---------------------------------------------------------------------------
# 浏览器自动化类 MCP
# ---------------------------------------------------------------------------
def get_playwright_mcp_tools():
    """获取 Playwright MCP 工具（无登录态）。"""
    client = MultiServerMCPClient(
        {
            "playwright_mcp": {
                "command": "npx",
                "args": [
                    "@playwright/mcp@latest",
                    "--viewport-size", "1920x1080",
                ],
                "transport": "stdio",
            }
        }
    )
    return asyncio.run(client.get_tools())


def get_playwright_mcp_tools_with_auth(
    storage_state_path: str = "playwright_scripts/auth_state/bnp_auth.json",
):
    """
    获取带登录态的 Playwright MCP 工具。

    Args:
        storage_state_path: 登录态文件路径（``context.storageState()`` 保存的 JSON）

    Returns:
        Playwright MCP 工具列表（浏览器会自动加载登录态）。

    注意：
        - 必须配合 ``--isolated`` 才能让 ``--storage-state`` 生效。
        - 登录态文件不存在时会回退到无登录态启动，并打印告警。
    """
    if not os.path.isabs(storage_state_path):
        # 仓库根目录 = 当前文件向上三级（mcp_clients → agents → app → repo_root）
        project_root = Path(__file__).resolve().parents[3]
        abs_path = project_root / storage_state_path
    else:
        abs_path = Path(storage_state_path)

    abs_path_str = str(abs_path).replace("\\", "/")

    if not abs_path.exists():
        print(f"⚠️  登录态文件不存在: {abs_path_str}")
        print("   将启动无登录态的浏览器会话")
        args = [
            "@playwright/mcp@latest",
            "--viewport-size", "1920x1080",
        ]
    else:
        print(f"🔐 加载登录态: {abs_path_str}")
        args = [
            "@playwright/mcp@latest",
            "--viewport-size", "1920x1080",
            "--isolated",
            f"--storage-state={abs_path_str}",
        ]

    client = MultiServerMCPClient(
        {
            "playwright_mcp": {
                "command": "npx",
                "args": args,
                "transport": "stdio",
            }
        }
    )
    return asyncio.run(client.get_tools())


def get_chrome_devtools_mcp_tools():
    """获取 Chrome DevTools MCP 工具。"""
    client = MultiServerMCPClient(
        {
            "chrome_devtools_mcp": {
                "command": "npx",
                "args": [
                    "chrome-devtools-mcp@latest",
                    "--headless=false",
                    "--isolated=true",
                ],
                "transport": "stdio",
            }
        }
    )
    return asyncio.run(client.get_tools())


# ---------------------------------------------------------------------------
# 其它 MCP
# ---------------------------------------------------------------------------
def get_mcp_server_chart_tools():
    """获取 AntV MCP Chart Server 工具。"""
    client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )
    return asyncio.run(client.get_tools())
