"""UI自动化测试智能体配置."""



import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    """获取环境变量."""
    return os.environ.get(key, default)

# pragma: no cover  MC80OmFIVnBZMlhscm9IbGhiVGxqWTQ2TkdWMWJBPT06YmFhYTQwYWU=

def _env_int(key: str, default: int = 0) -> int:
    """获取整数环境变量."""
    return int(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    """获取布尔环境变量."""
    val = os.environ.get(key, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default
# type: ignore  MS80OmFIVnBZMlhscm9IbGhiVGxqWTQ2TkdWMWJBPT06YmFhYTQwYWU=


@dataclass
class UIAutomationConfig:
    """UI自动化测试智能体配置."""

    # 工作空间根目录（FilesystemBackend 的根目录）
    # 所有虚拟路径都相对于此目录，如 /playwright_scripts/test.spec.ts 映射到 {workspace_root}/playwright_scripts/test.spec.ts
    workspace_root: str = field(default_factory=lambda: _env("UI_WORKSPACE_ROOT", "."))

    # MCP 服务配置
    # mcp-chrome 服务器配置
    chrome_mcp_url: str = field(default_factory=lambda: _env("CHROME_MCP_URL", "http://127.0.0.1:12306/mcp"))
    chrome_mcp_transport: str = field(default_factory=lambda: _env("CHROME_MCP_TRANSPORT", "streamable_http"))
# fmt: off  Mi80OmFIVnBZMlhscm9IbGhiVGxqWTQ2TkdWMWJBPT06YmFhYTQwYWU=
    
    # mcp-chart-server 配置
    chart_mcp_command: str = field(default_factory=lambda: _env("CHART_MCP_COMMAND", "npx"))
    chart_mcp_args: list[str] = field(default_factory=lambda: ["-y", "@antv/mcp-server-chart"])

    # Playwright 执行配置
    playwright_binary: str = field(default_factory=lambda: _env("PLAYWRIGHT_BINARY", "npx"))
    playwright_args: list[str] = field(default_factory=lambda: ["playwright", "test"])
    
    # 虚拟路径（以 / 开头）
    scripts_dir: str = field(default_factory=lambda: _env("PLAYWRIGHT_SCRIPTS_DIR", "/playwright_scripts/tests"))
    results_dir: str = field(default_factory=lambda: _env("PLAYWRIGHT_RESULTS_DIR", "/playwright_results"))
    reports_dir: str = field(default_factory=lambda: _env("PLAYWRIGHT_REPORTS_DIR", "/playwright_reports"))
    base64_images_dir: str = field(default_factory=lambda: _env("BASE64_IMAGES_DIR", "/base64_images"))

    # Playwright 默认配置
    default_browser: str = field(default_factory=lambda: _env("PLAYWRIGHT_DEFAULT_BROWSER", "chromium"))
    default_headless: bool = field(default_factory=lambda: _env_bool("PLAYWRIGHT_DEFAULT_HEADLESS", True))
    default_timeout: int = field(default_factory=lambda: _env_int("PLAYWRIGHT_DEFAULT_TIMEOUT", 60000))
    navigation_timeout: int = field(default_factory=lambda: _env_int("PLAYWRIGHT_NAVIGATION_TIMEOUT", 120000))
    
    # 测试报告配置
    report_format: str = field(default_factory=lambda: _env("REPORT_FORMAT", "html"))  # html, json, markdown
    include_screenshots: bool = field(default_factory=lambda: _env_bool("REPORT_INCLUDE_SCREENSHOTS", True))
    include_videos: bool = field(default_factory=lambda: _env_bool("REPORT_INCLUDE_VIDEOS", False))

    # 语言模型配置（通过 kiro-gateway）
    model_provider: str = field(default_factory=lambda: _env("UI_MODEL_PROVIDER", "openai"))  # openai 兼容 API
    model_name: str = field(default_factory=lambda: _env("UI_MODEL_NAME", "claude-sonnet-4.5"))  # 默认使用 Claude Sonnet
    api_key: str = field(default_factory=lambda: _env("KIRO_API_KEY", ""))  # Kiro Gateway API Key
# noqa  My80OmFIVnBZMlhscm9IbGhiVGxqWTQ2TkdWMWJBPT06YmFhYTQwYWU=


# 默认配置实例
DEFAULT_CONFIG = UIAutomationConfig()
