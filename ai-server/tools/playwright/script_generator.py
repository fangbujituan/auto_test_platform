"""Playwright脚本生成和保存工具."""

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from langchain_core.tools import StructuredTool, BaseTool

from tools.playwright.config import UIAutomationConfig, DEFAULT_CONFIG


def _resolve_virtual_path(virtual_path: str, workspace_root: str) -> Path:
    """将虚拟路径解析为实际文件系统路径.

    虚拟路径以 / 开头，例如 /playwright_scripts/test.spec.ts
    映射到 {workspace_root}/playwright_scripts/test.spec.ts

    Args:
        virtual_path: 虚拟路径（以 / 开头）
        workspace_root: 工作空间根目录

    Returns:
        实际文件系统路径
    """
    # 移除开头的 /
    relative_path = virtual_path.lstrip("/")
    return Path(workspace_root).resolve() / relative_path


def _to_virtual_path(scripts_dir: str, script_name: str) -> str:
    """生成虚拟路径.

    Args:
        scripts_dir: 虚拟脚本目录（如 /playwright_scripts）
        script_name: 脚本名称

    Returns:
        虚拟路径（如 /playwright_scripts/test.spec.ts）
    """
    # 确保目录以 / 开头
    if not scripts_dir.startswith("/"):
        scripts_dir = "/" + scripts_dir
    # 移除末尾的 /
    scripts_dir = scripts_dir.rstrip("/")
    return f"{scripts_dir}/{script_name}"


def create_script_save_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """创建Playwright脚本保存工具.

    Args:
        config: UI自动化配置

    Returns:
        脚本保存工具
    """
    cfg = config or DEFAULT_CONFIG

    def save_playwright_script(
        script_content: str,
        script_name: str = "",
        language: Literal["typescript", "javascript"] = "typescript",
    ) -> str:
        """保存Playwright测试脚本到文件.

        Args:
            script_content: Playwright脚本内容
            script_name: 脚本名称（可选，默认自动生成）
            language: 脚本语言（typescript 或 javascript）

        Returns:
            保存的脚本虚拟路径（以 / 开头）
        """
        # 确定文件扩展名
        ext = ".spec.ts" if language == "typescript" else ".spec.js"
        
        # 生成脚本名称
        if not script_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_name = f"test_{timestamp}{ext}"
        elif not (script_name.endswith(".spec.ts") or script_name.endswith(".spec.js")):
            script_name = f"{script_name}{ext}"

        # 生成虚拟路径
        virtual_path = _to_virtual_path(cfg.scripts_dir, script_name)

        # 解析为实际路径
        actual_path = _resolve_virtual_path(virtual_path, cfg.workspace_root)

        # 确保目录存在
        actual_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存脚本
        actual_path.write_text(script_content, encoding="utf-8")

        # 返回虚拟路径（用于 deepagents 的文件系统工具）
        return f"✅ Playwright脚本已保存到: {virtual_path}\n实际路径: {actual_path}"

    return StructuredTool.from_function(
        name="save_playwright_script",
        func=save_playwright_script,
        description="""保存Playwright测试脚本到文件。
参数：
- script_content: Playwright脚本内容（必需）
- script_name: 脚本名称（可选，默认自动生成时间戳名称）
- language: 脚本语言，可选 'typescript' 或 'javascript'（默认 typescript）

返回虚拟路径（如 /playwright_scripts/test.spec.ts）和实际文件系统路径。""",
    )
