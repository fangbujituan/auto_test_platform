"""
MCP 客户端工具模块
提供各种 MCP 工具的客户端连接和工具获取功能
"""

import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


def get_zhipu_search_mcp_tools():
    """获取智谱搜索 MCP 工具"""
    client = MultiServerMCPClient(
        {
            "search": {
                "url": "https://open.bigmodel.cn/api/mcp/web_search/sse?Authorization=615ff211360f41f59a4b99787132badf.8Yn84taE1Vzv0izs",
                "transport": "sse",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_tavily_search_tools():
    """获取 Tavily 搜索 MCP 工具"""
    client = MultiServerMCPClient(
        {
            "search": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "streamable_http",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_playwright_mcp_tools():
    """获取 Playwright MCP 工具（无登录态）"""
    client = MultiServerMCPClient(
        {
            "playwright_mcp": {
                "command": "npx",
                "args": [
                    "@playwright/mcp@latest",
                    "--viewport-size", "1920x1080",  # 默认浏览器窗口大小
                ],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_playwright_mcp_tools_with_auth(storage_state_path: str = "playwright_scripts/auth_state/bnp_auth.json"):
    """
    获取带登录态的 Playwright MCP 工具
    
    Args:
        storage_state_path: 登录态文件路径（使用 context.storageState() 保存的 JSON 文件）
                           默认: playwright_scripts/auth_state/bnp_auth.json
    
    Returns:
        Playwright MCP 工具列表（浏览器会自动加载登录态）
    
    使用场景:
        - 已有登录态文件，需要录制登录后的操作
        - 避免每次录制都重新登录
    
    注意:
        - 登录态文件需要提前通过 Playwright 脚本保存
        - 如果文件不存在，MCP 会正常启动但不会加载登录态
        - --storage-state 需要配合 --isolated 参数才能生效
    """
    import os
    from pathlib import Path
    
    # 转换为绝对路径（MCP 需要绝对路径）
    if not os.path.isabs(storage_state_path):
        # 相对于项目根目录
        project_root = Path(__file__).parent.parent.parent
        abs_path = project_root / storage_state_path
    else:
        abs_path = Path(storage_state_path)
    
    # Windows 路径转换为正斜杠格式（跨平台兼容）
    abs_path_str = str(abs_path).replace("\\", "/")
    
    # 检查文件是否存在
    if not abs_path.exists():
        print(f"⚠️  登录态文件不存在: {abs_path_str}")
        print(f"   将启动无登录态的浏览器会话")
        # 文件不存在时不加载登录态
        args = [
            "@playwright/mcp@latest",
            "--viewport-size", "1920x1080",  # 默认浏览器窗口大小
        ]
    else:
        print(f"🔐 加载登录态: {abs_path_str}")
        # 必须添加 --isolated 参数，否则 --storage-state 不生效
        args = [
            "@playwright/mcp@latest",
            "--viewport-size", "1920x1080",  # 默认浏览器窗口大小
            "--isolated",
            f"--storage-state={abs_path_str}"
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
    tools = asyncio.run(client.get_tools())
    return tools


def get_chrome_devtools_mcp_tools():
    """获取 Chrome DevTools MCP 工具"""
    client = MultiServerMCPClient(
        {
            "chrome_devtools_mcp": {
                "command": "npx",
                "args": ["chrome-devtools-mcp@latest", "--headless=false", "--isolated=true"],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


# def get_chrome_mcp_tools():
#     """获取 Chrome MCP 工具（已弃用）"""
#     try:
#         client = MultiServerMCPClient(
#             {
#                 "chrome_mcp": {
#                     "url": "http://127.0.0.1:12306/mcp",
#                     "transport": "streamable_http",
#                 }
#             }
#         )
#         tools = asyncio.run(client.get_tools())
#         return tools
#     except Exception as e:
#         print(f"Warning: Failed to load Chrome MCP tools: {e}")
#         return []


def get_mcp_server_chart_tools():
    """获取 MCP Chart Server 工具"""
    client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools
