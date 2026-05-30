"""
UI引擎配置模块

定义UI自动化测试的配置参数，包括Playwright相关设置。
所有配置都从环境变量读取，支持企业级部署。

作者: yandc
创建时间: 2026-05-30
更新: 2026-05-30 - 重构为从环境变量读取配置
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class UIAutomationConfig:
    """UI自动化配置."""
    
    # 工作区根目录
    workspace_root: str = str(Path(__file__).parent.parent.parent.parent)
    
    # Playwright 相关配置
    playwright_binary: str = os.getenv("UI_ENGINE_PLAYWRIGHT_BINARY", "npx")  # 在 Windows 上会自动调整为 npx.cmd
    playwright_args: list[str] = None  # Playwright 默认参数
    
    # 默认浏览器和模式
    default_browser: str = os.getenv("UI_ENGINE_DEFAULT_BROWSER", "chromium")
    default_headless: bool = os.getenv("UI_ENGINE_HEADLESS", "true").lower() == "true"
    default_timeout: int = int(os.getenv("UI_ENGINE_DEFAULT_TIMEOUT", "30000"))  # 30秒
    
    # 目录配置
    scripts_dir: str = os.getenv("UI_ENGINE_SCRIPTS_DIR", "/playwright_scripts/tests")  # 测试脚本目录（虚拟路径）
    results_dir: str = os.getenv("UI_ENGINE_RESULTS_DIR", "/playwright_results")  # 测试结果目录（虚拟路径）
    reports_dir: str = os.getenv("UI_ENGINE_REPORTS_DIR", "/playwright_reports")  # HTML报告目录（虚拟路径）
    base64_images_dir: str = os.getenv("UI_ENGINE_BASE64_IMAGES_DIR", "/base64_images")  # base64图片保存目录（虚拟路径）

    # 导航超时（毫秒）
    navigation_timeout: int = int(os.getenv("UI_ENGINE_NAVIGATION_TIMEOUT", "120000"))
    
    # MCP 相关配置
    chrome_mcp_url: str = os.getenv("UI_ENGINE_CHROME_MCP_URL", "http://127.0.0.1:12306/mcp")
    chrome_mcp_transport: str = os.getenv("UI_ENGINE_CHROME_MCP_TRANSPORT", "http")
    
    # 图表 MCP 配置
    chart_mcp_command: str = os.getenv("UI_ENGINE_CHART_MCP_COMMAND", "uvx")
    chart_mcp_args: list[str] = None
    
    # 模型配置
    model_name: str = os.getenv("UI_ENGINE_MODEL_NAME", "gpt-4o-mini")
    
    def __post_init__(self):
        """初始化默认值."""
        if self.playwright_args is None:
            self.playwright_args = ["playwright", "test"]
        
        if self.chart_mcp_args is None:
            self.chart_mcp_args = ["mcp-server-chart"]


# 默认配置实例
DEFAULT_CONFIG = UIAutomationConfig()