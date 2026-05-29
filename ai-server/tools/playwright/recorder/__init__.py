"""
Playwright Codegen 录制模块

集成 Playwright 官方 Codegen 录制功能，生成高质量的语义化选择器代码。

核心组件：
- recorder-server.js: Node.js 录制服务（使用内部 API _enableRecorder）
- recorder_client.py: Python 客户端
- codegen_tools.py: LangChain 工具（供 Agent 调用）

使用方式：
    # 方式一：直接使用客户端
    from tools.playwright.recorder import CodegenRecorder
    
    async with CodegenRecorder() as recorder:
        await recorder.start(url="https://example.com")
        await recorder.click("button")
        code = await recorder.get_codegen_code()
    
    # 方式二：通过 Agent 工具
    # Agent 可以调用 codegen_start, codegen_click 等工具

技术说明：
- Python Playwright 没有暴露 _enableRecorder 内部 API
- 需要通过 Node.js 调用 TypeScript 内部 API
- 录制服务通过 WebSocket 通信
"""

from tools.playwright.recorder.recorder_client import (
    CodegenRecorder,
    CodegenRecorderSync
)

from tools.playwright.recorder.codegen_tools import (
    CODEGEN_TOOLS,
    codegen_start,
    codegen_click,
    codegen_fill,
    codegen_navigate,
    codegen_get_code,
    codegen_save_script,
    codegen_stop,
    codegen_screenshot,
)

__all__ = [
    # 客户端
    "CodegenRecorder",
    "CodegenRecorderSync",
    
    # 工具
    "CODEGEN_TOOLS",
    "codegen_start",
    "codegen_click",
    "codegen_fill",
    "codegen_navigate",
    "codegen_get_code",
    "codegen_save_script",
    "codegen_stop",
    "codegen_screenshot",
]
