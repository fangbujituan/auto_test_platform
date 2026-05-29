"""
Tools 模块
导出所有工具和功能
"""

# 核心架构
from tools.core import make_agent, agent

# MCP 客户端工具
from tools.mcp import (
    get_zhipu_search_mcp_tools,
    get_tavily_search_tools,
    get_playwright_mcp_tools,
    get_playwright_mcp_tools_with_auth,
    get_chrome_devtools_mcp_tools,
    get_mcp_server_chart_tools,
)

# 中间件
from tools.middleware import (
    DOMCleanerMiddleware,
    BeforeAgentMiddleware,
    CodeCollectorMiddleware,
    get_collector,
    reset_collector,
)

# 工具函数
from tools.utils import clean_dom_html, clean_playwright_snapshot

# 示例工具
from tools.examples import get_weather

# 调试工具
from tools.debug import logs

# Playwright 自动化
from tools.playwright import (
    UIAutomationConfig,
    DEFAULT_CONFIG,
    SYSTEM_PROMPT,
    MAIN_AGENT_PROMPT,
    create_ui_automation_agent,
    create_playwright_executor_tool,
    create_result_parser_tool,
    create_script_save_tool,
    # 录制回放
    ScriptManager,
    get_manager,
    make_recording_agent,
    recording_agent,
    # BNP 专用认证工具
    create_bnp_login_tool,
    create_bnp_check_auth_tool,
    create_bnp_list_auth_states_tool,
    bnp_login_and_save,
    bnp_check_auth,
    bnp_list_auth_states,
)

__all__ = [
    # 核心架构
    "make_agent",
    "agent",
    
    # MCP 客户端工具
    "get_zhipu_search_mcp_tools",
    "get_tavily_search_tools",
    "get_playwright_mcp_tools",
    "get_playwright_mcp_tools_with_auth",
    "get_chrome_devtools_mcp_tools",
    "get_mcp_server_chart_tools",
    
    # 中间件
    "DOMCleanerMiddleware",
    "BeforeAgentMiddleware",
    "CodeCollectorMiddleware",
    "get_collector",
    "reset_collector",
    
    # 工具函数
    "clean_dom_html",
    "clean_playwright_snapshot",
    
    # 示例工具
    "get_weather",
    
    # 调试工具
    "logs",
    
    # Playwright 自动化
    "UIAutomationConfig",
    "DEFAULT_CONFIG",
    "SYSTEM_PROMPT",
    "MAIN_AGENT_PROMPT",
    "create_ui_automation_agent",
    "create_playwright_executor_tool",
    "create_result_parser_tool",
    "create_script_save_tool",
    # 录制回放
    "ScriptManager",
    "get_manager",
    "make_recording_agent",
    "recording_agent",
    # BNP 专用认证工具
    "create_bnp_login_tool",
    "create_bnp_check_auth_tool",
    "create_bnp_list_auth_states_tool",
    "bnp_login_and_save",
    "bnp_check_auth",
    "bnp_list_auth_states",
]
