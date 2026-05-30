"""
MCP 客户端工具模块。

迁移自 ai-server/tools/mcp/clients.py。

提供各种 MCP（Model Context Protocol）服务的客户端连接和工具加载：
- Playwright（带/不带登录态）
- Chrome DevTools
- MCP Chart Server（图表）
- 智谱搜索、Tavily 搜索

所有需要 API Key / URL 的 MCP 服务都从环境变量读取，避免硬编码敏感信息。
"""

import asyncio
import os
from pathlib import Path
from typing import List, Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.utils.debug.readlog import logs


# ============================================================================
# 搜索类 MCP（HTTP/SSE 接入）
# ============================================================================

def get_zhipu_search_mcp_tools() -> List[Any]:
    """获取智谱搜索 MCP 工具。

    需要环境变量：
        ZHIPU_SEARCH_MCP_URL: SSE 接入地址（默认 https://open.bigmodel.cn/api/mcp/web_search/sse）
        ZHIPU_SEARCH_API_KEY: 智谱开放平台 API Key

    Returns:
        加载到的 LangChain 工具列表
    """
    base_url = os.getenv(
        "ZHIPU_SEARCH_MCP_URL",
        "https://open.bigmodel.cn/api/mcp/web_search/sse",
    )
    api_key = os.getenv("ZHIPU_SEARCH_API_KEY", "")
    if not api_key:
        raise ValueError("ZHIPU_SEARCH_API_KEY 未配置，请在 .env 中设置")

    url = f"{base_url}?Authorization={api_key}"
    client = MultiServerMCPClient(
        {
            "search": {
                "url": url,
                "transport": "sse",
            }
        }
    )
    return asyncio.run(client.get_tools())


def get_tavily_search_tools() -> List[Any]:
    """获取 Tavily 搜索 MCP 工具。

    需要环境变量：
        TAVILY_MCP_URL: HTTP 接入地址（默认 https://mcp.tavily.com/mcp/）
        TAVILY_API_KEY: Tavily API Key

    Returns:
        加载到的 LangChain 工具列表
    """
    base_url = os.getenv("TAVILY_MCP_URL", "https://mcp.tavily.com/mcp/")
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 未配置，请在 .env 中设置")

    url = f"{base_url}?tavilyApiKey={api_key}"
    client = MultiServerMCPClient(
        {
            "search": {
                "url": url,
                "transport": "streamable_http",
            }
        }
    )
    return asyncio.run(client.get_tools())


# ============================================================================
# Playwright MCP（stdio 接入）
# ============================================================================

def get_playwright_mcp_tools(viewport: str = "1920x1080") -> List[Any]:
    """获取 Playwright MCP 工具（无登录态）。

    Args:
        viewport: 默认浏览器窗口大小

    Returns:
        加载到的 LangChain 工具列表
    """
    client = MultiServerMCPClient(
        {
            "playwright_mcp": {
                "command": "npx",
                "args": [
                    "@playwright/mcp@latest",
                    "--viewport-size", viewport,
                ],
                "transport": "stdio",
            }
        }
    )
    return asyncio.run(client.get_tools())


def get_playwright_mcp_tools_with_auth(
    storage_state_path: str = "playwright_scripts/auth_state/bnp_auth.json",
    viewport: str = "1920x1080",
) -> List[Any]:
    """获取带登录态的 Playwright MCP 工具。

    Args:
        storage_state_path: 登录态文件路径（context.storageState() 输出的 JSON）。
            支持相对路径（相对于项目根目录）或绝对路径。
        viewport: 默认浏览器窗口大小

    Returns:
        加载到的 LangChain 工具列表（浏览器会自动加载登录态）

    使用场景：
        已有登录态文件，需要录制登录后的操作，避免每次重新登录。

    注意：
        - 登录态文件需要提前通过 Playwright 脚本保存
        - 如果文件不存在，MCP 会正常启动但不会加载登录态
        - --storage-state 必须配合 --isolated 才能生效
    """
    # 转换为绝对路径（MCP 需要绝对路径）
    if os.path.isabs(storage_state_path):
        abs_path = Path(storage_state_path)
    else:
        # 相对于项目根目录（app 的上两级）
        project_root = Path(__file__).parent.parent.parent
        abs_path = project_root / storage_state_path

    # Windows 路径转换为正斜杠格式（跨平台兼容）
    abs_path_str = str(abs_path).replace("\\", "/")

    if not abs_path.exists():
        logs.warning(f"⚠️  登录态文件不存在: {abs_path_str}，将启动无登录态的浏览器")
        args = [
            "@playwright/mcp@latest",
            "--viewport-size", viewport,
        ]
    else:
        logs.info(f"🔐 加载登录态: {abs_path_str}")
        args = [
            "@playwright/mcp@latest",
            "--viewport-size", viewport,
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


# ============================================================================
# Chrome DevTools MCP（stdio 接入）
# ============================================================================

def get_chrome_devtools_mcp_tools() -> List[Any]:
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


# ============================================================================
# 图表 MCP（stdio 接入）
# ============================================================================

def get_mcp_server_chart_tools() -> List[Any]:
    """获取 MCP Chart Server 工具（@antv/mcp-server-chart）。"""
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


__all__ = [
    "get_zhipu_search_mcp_tools",
    "get_tavily_search_tools",
    "get_playwright_mcp_tools",
    "get_playwright_mcp_tools_with_auth",
    "get_chrome_devtools_mcp_tools",
    "get_mcp_server_chart_tools",
]
