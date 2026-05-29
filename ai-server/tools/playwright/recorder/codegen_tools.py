"""
Codegen 录制工具

提供 LangChain 工具，让 Agent 可以：
1. 启动 Codegen 录制会话
2. 执行操作（自动被 Codegen 录制）
3. 获取生成的代码
4. 保存到脚本库

集成到 recording_agent 中使用。
"""

import json
from typing import Optional, Dict, Any
from langchain_core.tools import tool

from tools.debug.readlog import logs


# 全局录制器实例
_recorder_instance = None
_codegen_output_file = None


def get_recorder():
    """获取全局录制器实例"""
    global _recorder_instance
    if _recorder_instance is None:
        from tools.playwright.recorder.recorder_client import CodegenRecorder
        _recorder_instance = CodegenRecorder(auto_start_server=True)
    return _recorder_instance


async def ensure_recorder_connected():
    """确保录制器已连接"""
    recorder = get_recorder()
    if recorder.ws is None:
        await recorder._connect()
    return recorder


@tool
async def codegen_start(
    url: str,
    headless: bool = False,
    storage_state: str = "",
    output_file: str = ""
) -> str:
    """
    启动 Codegen 录制会话。
    
    启动一个带录制功能的浏览器，后续所有操作都会被自动录制并生成代码。
    Codegen 会分析 DOM 结构，生成高质量的语义化选择器。
    
    Args:
        url: 初始 URL
        headless: 是否无头模式（默认 False，显示浏览器）
        storage_state: 登录态文件路径（可选）
        output_file: 代码输出文件路径（可选）
    
    Returns:
        启动结果
    """
    global _codegen_output_file
    
    try:
        recorder = await ensure_recorder_connected()
        
        params = {
            "url": url,
            "headless": headless
        }
        
        if storage_state:
            params["storage_state"] = storage_state
        
        if output_file:
            params["output_file"] = output_file
            _codegen_output_file = output_file
        else:
            # 默认输出到临时文件
            import tempfile
            _codegen_output_file = tempfile.mktemp(suffix=".spec.ts")
            params["output_file"] = _codegen_output_file
        
        result = await recorder.start(**params)
        
        if result.get("success"):
            return json.dumps({
                "success": True,
                "message": f"Codegen 录制会话已启动，浏览器已打开",
                "url": url,
                "hint": "后续操作将被自动录制。完成后使用 codegen_get_code 获取生成的代码。"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_start] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_click(selector: str = "", x: int = 0, y: int = 0) -> str:
    """
    在 Codegen 会话中点击元素。
    
    操作会被 Codegen 自动录制，生成高质量选择器的代码。
    
    Args:
        selector: 元素选择器（推荐使用）
        x: 点击坐标 X（备用方案）
        y: 点击坐标 Y（备用方案）
    
    Returns:
        点击结果
    """
    try:
        recorder = await ensure_recorder_connected()
        
        params = {}
        if selector:
            params["selector"] = selector
        elif x and y:
            params["coordinates"] = {"x": x, "y": y}
        else:
            return json.dumps({
                "success": False,
                "error": "请提供 selector 或坐标 (x, y)"
            }, ensure_ascii=False)
        
        result = await recorder.click(**params)
        
        if result.get("success"):
            return json.dumps({
                "success": True,
                "message": f"已点击: {selector or f'({x}, {y})'}",
                "hint": "Codegen 正在录制此操作"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_click] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_fill(selector: str, value: str) -> str:
    """
    在 Codegen 会话中填充输入框。
    
    操作会被 Codegen 自动录制。
    
    Args:
        selector: 输入框选择器
        value: 要填充的值
    
    Returns:
        填充结果
    """
    try:
        recorder = await ensure_recorder_connected()
        result = await recorder.fill(selector, value)
        
        if result.get("success"):
            return json.dumps({
                "success": True,
                "message": f"已填充: {selector}",
                "hint": "Codegen 正在录制此操作"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_fill] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_navigate(url: str) -> str:
    """
    在 Codegen 会话中导航到 URL。
    
    Args:
        url: 目标 URL
    
    Returns:
        导航结果
    """
    try:
        recorder = await ensure_recorder_connected()
        result = await recorder.navigate(url)
        
        if result.get("success"):
            return json.dumps({
                "success": True,
                "message": f"已导航到: {url}"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_navigate] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_get_code() -> str:
    """
    获取 Codegen 生成的代码。
    
    返回 Codegen 分析 DOM 后生成的高质量 TypeScript 代码。
    代码使用语义化选择器（getByRole, getByText 等）。
    
    Returns:
        生成的代码
    """
    global _codegen_output_file
    
    try:
        recorder = await ensure_recorder_connected()
        code = await recorder.get_codegen_code()
        
        return json.dumps({
            "success": True,
            "code": code,
            "output_file": _codegen_output_file,
            "hint": "可以使用 codegen_save_script 保存到脚本库"
        }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_get_code] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_save_script(name: str, description: str = "") -> str:
    """
    保存 Codegen 生成的脚本到脚本库。
    
    Args:
        name: 脚本名称
        description: 脚本描述
    
    Returns:
        保存结果
    """
    global _codegen_output_file
    
    try:
        # 获取生成的代码
        recorder = await ensure_recorder_connected()
        code = await recorder.get_codegen_code()
        
        if not code:
            return json.dumps({
                "success": False,
                "error": "没有录制的代码"
            }, ensure_ascii=False)
        
        # 保存到脚本库
        from tools.playwright.script_manager import get_manager
        from tools.playwright.config import DEFAULT_CONFIG
        from tools.playwright.script_generator import create_script_save_tool
        
        manager = get_manager()
        save_tool = create_script_save_tool(DEFAULT_CONFIG)
        
        result = save_tool.invoke({
            "script_content": code,
            "script_name": name,
            "language": "typescript"
        })
        
        # 保存元数据
        manager.save_metadata(
            name=name,
            description=description or f"Codegen 录制的脚本: {name}",
            url_patterns=[],
            keywords=["codegen"],
            variables=[]
        )
        
        return json.dumps({
            "success": True,
            "message": f"脚本已保存: {name}",
            "file_path": result,
            "hint": "可以使用 run_playwright_script 执行此脚本"
        }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_save_script] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_stop() -> str:
    """
    停止 Codegen 录制会话。
    
    关闭浏览器，返回最终生成的代码。
    
    Returns:
        停止结果和最终代码
    """
    try:
        recorder = await ensure_recorder_connected()
        result = await recorder.stop()
        
        if result.get("success"):
            code = result.get("code", "")
            actions_count = result.get("actionsCount", 0)
            
            return json.dumps({
                "success": True,
                "message": "Codegen 录制会话已停止",
                "actions_count": actions_count,
                "code": code,
                "hint": "可以使用 codegen_save_script 保存代码"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_stop] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
async def codegen_screenshot() -> str:
    """
    在 Codegen 会话中截图。
    
    Returns:
        截图结果（包含 base64 数据）
    """
    try:
        recorder = await ensure_recorder_connected()
        result = await recorder.screenshot()
        
        if result.get("success"):
            return json.dumps({
                "success": True,
                "message": "截图成功",
                "base64_length": len(result.get("base64", ""))
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, ensure_ascii=False)
            
    except Exception as e:
        logs.error(f"[codegen_screenshot] Error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# 导出所有工具
CODEGEN_TOOLS = [
    codegen_start,
    codegen_click,
    codegen_fill,
    codegen_navigate,
    codegen_get_code,
    codegen_save_script,
    codegen_stop,
    codegen_screenshot,
]
