"""Playwright 自动化测试模块."""

from tools.playwright.config import UIAutomationConfig, DEFAULT_CONFIG
from tools.playwright.prompts import SYSTEM_PROMPT, MAIN_AGENT_PROMPT
from tools.playwright.agent import create_ui_automation_agent, agent
from tools.playwright.executor import create_playwright_executor_tool
from tools.playwright.report import create_result_parser_tool
from tools.playwright.script_generator import create_script_save_tool
from tools.playwright.script_manager import ScriptManager, get_manager
from tools.playwright.recording_agent import make_recording_agent, recording_agent
from tools.playwright.bnp_auth_tool import (
    create_bnp_login_tool,
    create_bnp_check_auth_tool,
    create_bnp_list_auth_states_tool,
    bnp_login_and_save,
    bnp_check_auth,
    bnp_list_auth_states,
)

__all__ = [
    # 配置
    "UIAutomationConfig",
    "DEFAULT_CONFIG",
    # 提示词
    "SYSTEM_PROMPT",
    "MAIN_AGENT_PROMPT",
    # Agent
    "create_ui_automation_agent",
    "agent",
    # 录制回放 Agent
    "make_recording_agent",
    "recording_agent",
    # 工具
    "create_playwright_executor_tool",
    "create_result_parser_tool",
    "create_script_save_tool",
    # BNP 专用认证工具
    "create_bnp_login_tool",
    "create_bnp_check_auth_tool",
    "create_bnp_list_auth_states_tool",
    "bnp_login_and_save",
    "bnp_check_auth",
    "bnp_list_auth_states",
    # 脚本管理
    "ScriptManager",
    "get_manager",
]
