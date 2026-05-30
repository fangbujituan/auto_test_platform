"""
UI 引擎（UI-engine）。

负责 Web UI 自动化测试的执行（如基于 Selenium/Playwright 的浏览器测试）。

整合了Playwright自动化能力：
1. 脚本执行（executor.py）
2. 录制回放功能（recorder.py）
3. 报告解析（report.py）
4. 脚本生成（script_generator.py）

作者: yandc
创建时间: 2026-05-30
"""

from app.engine.ui_engine.config import UIAutomationConfig, DEFAULT_CONFIG
from app.engine.ui_engine.playwright.executor import create_playwright_executor_tool
from app.engine.ui_engine.playwright.recorder import create_recorder_tool
from app.engine.ui_engine.playwright.report import create_result_parser_tool
from app.engine.ui_engine.playwright.script_generator import create_script_save_tool, create_script_generator_tool
from app.engine.ui_engine.playwright.script_index import get_index_manager


def get_ui_engine_tools(config: UIAutomationConfig | None = None):
    """
    获取UI引擎的所有工具。
    
    Args:
        config: UI自动化配置
        
    Returns:
        工具列表
    """
    cfg = config or DEFAULT_CONFIG
    
    # 创建所有工具
    executor_tool = create_playwright_executor_tool(cfg)
    recorder_tools = create_recorder_tool(cfg)
    parser_tool = create_result_parser_tool(cfg)
    save_tool = create_script_save_tool(cfg)
    generator_tool = create_script_generator_tool(cfg)
    
    # 返回所有工具
    return [executor_tool, *recorder_tools, parser_tool, save_tool, generator_tool]


def get_ui_engine_info():
    """
    获取UI引擎信息。
    
    Returns:
        引擎信息字典
    """
    return {
        "name": "UI Engine",
        "version": "1.0.0",
        "description": "Web UI自动化测试引擎，基于Playwright",
        "capabilities": [
            "Playwright脚本执行",
            "Codegen录制回放",
            "测试结果解析",
            "脚本生成与保存",
            "脚本索引管理"
        ],
        "config": {
            "default_browser": DEFAULT_CONFIG.default_browser,
            "default_headless": DEFAULT_CONFIG.default_headless,
            "default_timeout": DEFAULT_CONFIG.default_timeout,
            "workspace_root": DEFAULT_CONFIG.workspace_root
        }
    }


# 导出主要功能
__all__ = [
    "UIAutomationConfig",
    "DEFAULT_CONFIG",
    "get_ui_engine_tools",
    "get_ui_engine_info",
    "get_index_manager",
    "create_playwright_executor_tool",
    "create_recorder_tool",
    "create_result_parser_tool",
    "create_script_save_tool",
    "create_script_generator_tool"
]