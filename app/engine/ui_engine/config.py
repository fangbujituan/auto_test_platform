"""
UI引擎配置模块

定义UI自动化测试的配置参数，包括Playwright相关设置。

作者: yandc
创建时间: 2026-05-30
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class UIAutomationConfig:
    """UI自动化配置."""
    
    # 工作区根目录
    workspace_root: str = str(Path(__file__).parent.parent.parent.parent)
    
    # Playwright 相关配置
    playwright_binary: str = "npx"  # 在 Windows 上会自动调整为 npx.cmd
    playwright_args: list[str] = None  # Playwright 默认参数
    
    # 默认浏览器和模式
    default_browser: str = "chromium"
    default_headless: bool = True
    default_timeout: int = 30000  # 30秒
    
    # 目录配置
    results_dir: str = "/playwright_results"  # 测试结果目录（虚拟路径）
    reports_dir: str = "/playwright_reports"  # HTML报告目录（虚拟路径）
    base64_images_dir: str = "/base64_images"  # base64图片保存目录（虚拟路径）
    
    # MCP 相关配置
    chrome_mcp_url: str = "http://127.0.0.1:12306/mcp"
    chrome_mcp_transport: str = "http"
    
    # 图表 MCP 配置
    chart_mcp_command: str = "uvx"
    chart_mcp_args: list[str] = None
    
    # 模型配置
    model_name: str = "gpt-4o-mini"
    
    def __post_init__(self):
        """初始化默认值."""
        if self.playwright_args is None:
            self.playwright_args = ["playwright", "test"]
        
        if self.chart_mcp_args is None:
            self.chart_mcp_args = ["mcp-server-chart"]


# 默认配置实例
DEFAULT_CONFIG = UIAutomationConfig()