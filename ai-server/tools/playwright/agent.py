"""UI自动化测试智能体 - 轻量级实现.

本模块实现了简洁的UI自动化测试解决方案，集成了：
1. midscene-web: UI自动化测试工具
2. mcp-chart-server: 图表生成工具
3. 本地工具：save_playwright_script, run_playwright_script, parse_test_results

特点：
- 无子智能体架构，所有工具直接由主智能体调用
- 简洁的系统提示词，减少 token 消耗
- 所有工具调用信息在界面上可见

使用方式:
    agent = create_ui_automation_agent()
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "..."}]})
"""

import asyncio
import base64
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware import before_model
from llms import get_model
from langchain_core.messages import ToolMessage

from tools.debug.readlog import logs
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from tools.playwright.config import DEFAULT_CONFIG, UIAutomationConfig
from tools.playwright.prompts import SYSTEM_PROMPT
from tools.playwright.executor import create_playwright_executor_tool
from tools.playwright.report import create_result_parser_tool
from tools.playwright.script_generator import create_script_save_tool


# Base64 数据的正则匹配模式
# 匹配 "base64Data" 或 \"base64Data\" 后跟任意长度的 base64 字符串
# 最小长度设为 50 字符，避免误匹配短字符串
BASE64_PATTERN = re.compile(r'\\?"base64Data\\?"\s*:\s*\\?"([A-Za-z0-9+/=]{50,}.*?)\\?"')


def _save_base64_image(base64_data: str, message_id: str, config: UIAutomationConfig) -> str:
    """保存 base64 图片到本地并返回文件路径.

    Args:
        base64_data: base64 编码的图片数据
        message_id: 消息 ID，用于生成文件名
        config: 配置对象

    Returns:
        保存的图片文件的绝对路径
    """
    # 创建保存目录（虚拟路径转实际路径）
    images_dir = Path(config.workspace_root) / config.base64_images_dir.lstrip("/")
    images_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名：消息ID_时间戳.png
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{message_id}_{timestamp}.png"
    filepath = images_dir / filename

    try:
        # 解码并保存图片
        image_bytes = base64.b64decode(base64_data)
        filepath.write_bytes(image_bytes)
        return str(filepath.absolute())
    except Exception as e:
        # 如果解码失败，返回错误信息
        return f"[ERROR: Failed to save image - {e}]"


def _contains_base64(content: Any) -> bool:
    """检查内容是否包含 base64 数据."""
    if content is None:
        return False

    if isinstance(content, str):
        return bool(BASE64_PATTERN.search(content))

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if isinstance(text, str) and BASE64_PATTERN.search(text):
                    return True
            elif isinstance(item, str) and BASE64_PATTERN.search(item):
                return True

    return False


def _replace_base64_in_content(content: Any, message_id: str, config: UIAutomationConfig) -> Any:
    """将内容中的 base64 数据保存到本地并替换为文件路径.

    Args:
        content: 消息内容
        message_id: 消息 ID
        config: 配置对象

    Returns:
        替换后的内容
    """
    def replace_match(match: re.Match) -> str:
        """替换匹配到的 base64 数据."""
        base64_data = match.group(1)  # 提取 base64 数据
        saved_path = _save_base64_image(base64_data, message_id, config)
        return f'"base64Data": "[BASE64_IMAGE_SAVED: {saved_path}]"'

    if isinstance(content, str):
        return BASE64_PATTERN.sub(replace_match, content)

    if isinstance(content, list):
        new_content = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                new_item = item.copy()
                if isinstance(item["text"], str):
                    new_item["text"] = BASE64_PATTERN.sub(replace_match, item["text"])
                new_content.append(new_item)
            else:
                new_content.append(item)
        return new_content

    return content


def create_ui_automation_agent(
    chrome_mcp_url: str | None = None,
    enable_chart_tools: bool = True,
    debug: bool = False,
):
    """创建UI自动化测试智能体.

    Args:
        chrome_mcp_url: Chrome MCP 服务器地址，默认使用配置文件中的地址
        enable_chart_tools: 是否启用图表工具，默认启用
        debug: 是否启用调试模式

    Returns:
        配置好的智能体实例
    """
    config = DEFAULT_CONFIG

    # API Key 已由 llms.py 统一管理（通过 kiro-gateway）

    # 初始化语言模型（使用配置中的模型名称）
    model = get_model(model=config.model_name)

    # 收集所有工具
    all_tools = []

    # 1. 加载 Chrome MCP 工具
    chrome_url = chrome_mcp_url or config.chrome_mcp_url
    chrome_client = MultiServerMCPClient({
        "midscene-web": {
            "transport": config.chrome_mcp_transport,
            "url": chrome_url,
        }
    })
    chrome_tools = asyncio.run(chrome_client.get_tools())
    all_tools.extend(chrome_tools)

    # 2. 加载图表 MCP 工具（可选）
    if enable_chart_tools:
        try:
            chart_client = MultiServerMCPClient({
                "mcp-server-chart": {
                    "transport": "stdio",
                    "command": config.chart_mcp_command,
                    "args": config.chart_mcp_args,
                }
            })
            chart_tools = asyncio.run(chart_client.get_tools())
            all_tools.extend(chart_tools)
        except Exception as e:
            logs.warning(f"无法加载图表工具: {e}")

    # 3. 创建本地工具
    script_save_tool = create_script_save_tool(config)
    executor_tool = create_playwright_executor_tool(config)
    parser_tool = create_result_parser_tool(config)
    all_tools.extend([script_save_tool, executor_tool, parser_tool])

    @before_model
    def filter_base64_content(state: AgentState, _runtime: Runtime) -> dict[str, Any] | None:
        """过滤消息中的 base64 图片数据以减少 token 消耗.

        处理逻辑：
        1. 遍历所有 ToolMessage，检查是否包含 base64 数据
        2. 如果包含，将 base64 数据保存到本地并替换为文件路径
        3. 使用 Overwrite 确保完全替换消息列表
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        modified = False
        new_messages = []

        for msg in messages:
            # 只处理 ToolMessage
            if msg.type == "tool":
                content = msg.content
                if _contains_base64(content):
                    # 保存 base64 数据到本地并替换为文件路径
                    # 使用 tool_call_id 作为文件名的一部分
                    message_id = msg.tool_call_id or msg.id or "unknown"
                    new_content = _replace_base64_in_content(content, message_id, config)
                    # 创建新的 ToolMessage
                    new_msg = ToolMessage(
                        content=new_content,
                        tool_call_id=msg.tool_call_id,
                        name=getattr(msg, 'name', None),
                        id=msg.id,
                    )
                    new_messages.append(new_msg)
                    modified = True
                else:
                    new_messages.append(msg)
            else:
                new_messages.append(msg)

        if modified:
            return {"messages": Overwrite(new_messages)}
        return None

    # 配置文件系统后端
    # 使用 FilesystemBackend 并启用 virtual_mode
    # 这样 agent 使用虚拟路径 (如 /playwright_scripts/test.spec.ts) 映射到实际文件系统
    workspace_root = Path(config.workspace_root).resolve()
    backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)

    # 创建智能体（不使用子智能体）
    agent = create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[filter_base64_content],
        backend=backend,  # 关键：映射虚拟路径到物理文件系统
        debug=debug,
    )

    return agent


# 保持向后兼容
# 注意：需要 Chrome MCP 服务运行在 http://127.0.0.1:12306/mcp
# 暂时注释掉，使用 recording_agent 替代
# agent = create_ui_automation_agent()
agent = None
