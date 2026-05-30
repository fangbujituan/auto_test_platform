"""
UI 引擎（UI-engine）。

负责 Web UI 自动化测试的执行（如基于 Playwright 的浏览器测试）。

整合 Playwright 自动化能力：
1. 脚本执行（``executor.py``）
2. 报告解析（``report.py``）
3. 脚本生成（``script_generator.py``）
4. 脚本索引（``script_index.py``）

录制能力请使用 ``app.agents.recording_agent.make_recording_agent``——它通过
Playwright MCP + 中间件实时收集动作并生成代码，是更现代的方案，已经替代
原 ai-server 中基于 Node 录制服务的 ``CodegenRecorder``。

作者: yandc
创建时间: 2026-05-30
"""

from app.engine.ui_engine.config import DEFAULT_CONFIG, UIAutomationConfig
from app.engine.ui_engine.playwright.executor import create_playwright_executor_tool
from app.engine.ui_engine.playwright.report import create_result_parser_tool
from app.engine.ui_engine.playwright.script_generator import (
    create_script_generator_tool,
    create_script_save_tool,
)
from app.engine.ui_engine.playwright.script_index import get_index_manager


def get_ui_engine_tools(config: UIAutomationConfig | None = None):
    """获取 UI 引擎的所有工具。

    Args:
        config: UI 自动化配置（可选，默认使用 ``DEFAULT_CONFIG``）

    Returns:
        工具列表（脚本执行 / 报告解析 / 脚本保存 / 脚本生成）
    """
    cfg = config or DEFAULT_CONFIG
    return [
        create_playwright_executor_tool(cfg),
        create_result_parser_tool(cfg),
        create_script_save_tool(cfg),
        create_script_generator_tool(cfg),
    ]


def get_ui_engine_info() -> dict:
    """获取 UI 引擎信息（用于前端展示与健康检查）。"""
    return {
        "name": "UI Engine",
        "version": "1.1.0",
        "description": "Web UI 自动化测试引擎，基于 Playwright + LangChain Agent",
        "capabilities": [
            "Playwright 脚本执行",
            "测试结果解析",
            "脚本生成与保存",
            "脚本索引管理",
            "Agent 实时录制（见 app.agents.recording_agent）",
        ],
        "config": {
            "default_browser": DEFAULT_CONFIG.default_browser,
            "default_headless": DEFAULT_CONFIG.default_headless,
            "default_timeout": DEFAULT_CONFIG.default_timeout,
            "workspace_root": DEFAULT_CONFIG.workspace_root,
        },
    }


__all__ = [
    "UIAutomationConfig",
    "DEFAULT_CONFIG",
    "get_ui_engine_tools",
    "get_ui_engine_info",
    "get_index_manager",
    "create_playwright_executor_tool",
    "create_result_parser_tool",
    "create_script_save_tool",
    "create_script_generator_tool",
]
