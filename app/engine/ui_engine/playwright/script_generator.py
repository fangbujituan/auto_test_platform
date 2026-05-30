"""
UI引擎 - Playwright脚本生成器

生成和保存Playwright测试脚本。

作者: yandc
创建时间: 2026-05-30
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.tools import StructuredTool, BaseTool

from app.engine.ui_engine.config import UIAutomationConfig, DEFAULT_CONFIG


def _resolve_virtual_path(virtual_path: str, workspace_root: str) -> Path:
    """将虚拟路径解析为实际文件系统路径."""
    relative_path = virtual_path.lstrip("/")
    return Path(workspace_root).resolve() / relative_path


def create_script_save_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """创建Playwright脚本保存工具.

    Args:
        config: UI自动化配置

    Returns:
        脚本保存工具
    """
    cfg = config or DEFAULT_CONFIG

    def save_playwright_script(
        script_name: str,
        script_content: str,
        description: str = "",
        tags: List[str] = None,
        overwrite: bool = False
    ) -> str:
        """保存Playwright测试脚本.

        Args:
            script_name: 脚本名称（不含扩展名，如 "login_test"）
            script_content: 脚本内容（TypeScript代码）
            description: 脚本描述
            tags: 标签列表
            overwrite: 是否覆盖已存在的脚本

        Returns:
            保存结果（JSON格式）
        """
        # 清理脚本名称
        script_name = script_name.strip()
        if not script_name:
            return json.dumps({
                "success": False,
                "error": "脚本名称不能为空"
            }, ensure_ascii=False, indent=2)
        
        # 确保脚本名称以 .spec.ts 结尾
        if not script_name.endswith(".spec.ts"):
            script_name = f"{script_name}.spec.ts"
        
        # 构建虚拟路径
        virtual_path = f"/playwright_scripts/tests/{script_name}"
        
        # 解析为实际路径
        actual_path = _resolve_virtual_path(virtual_path, cfg.workspace_root)
        
        # 检查文件是否已存在
        if actual_path.exists() and not overwrite:
            return json.dumps({
                "success": False,
                "error": f"脚本已存在: {script_name}",
                "path": virtual_path,
                "hint": "使用 overwrite=True 参数覆盖现有文件"
            }, ensure_ascii=False, indent=2)
        
        # 确保目录存在
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 保存脚本
            actual_path.write_text(script_content, encoding="utf-8")
            
            # 更新脚本索引
            try:
                from app.engine.ui_engine.playwright.script_index import get_index_manager
                index_manager = get_index_manager()
                
                # 提取脚本名称（不含扩展名）
                script_base_name = script_name.replace(".spec.ts", "")
                
                # 保存到索引
                index_manager.add_script(
                    name=script_base_name,
                    path=virtual_path,
                    description=description,
                    tags=tags or []
                )
            except Exception as e:
                # 索引更新失败不影响脚本保存
                print(f"更新脚本索引失败: {e}")
            
            return json.dumps({
                "success": True,
                "message": f"脚本保存成功: {script_name}",
                "path": virtual_path,
                "actual_path": str(actual_path),
                "script_name": script_base_name,
                "description": description,
                "tags": tags or []
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"保存脚本失败: {e}",
                "path": virtual_path
            }, ensure_ascii=False, indent=2)

    return StructuredTool.from_function(
        name="save_playwright_script",
        func=save_playwright_script,
        description="""保存Playwright测试脚本。
        
参数：
- script_name: 脚本名称（必需，如 "login_test"，会自动添加 .spec.ts 后缀）
- script_content: 脚本内容（必需，TypeScript代码）
- description: 脚本描述（可选）
- tags: 标签列表（可选，如 ["login", "auth", "ui"]）
- overwrite: 是否覆盖已存在的脚本（可选，默认 False）

脚本将保存到 /playwright_scripts/tests/ 目录下，并自动添加到脚本索引中。

返回JSON格式的保存结果。""",
    )


def create_script_generator_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """创建Playwright脚本生成工具.

    Args:
        config: UI自动化配置

    Returns:
        脚本生成工具
    """
    cfg = config or DEFAULT_CONFIG

    def generate_playwright_script(
        test_scenario: str,
        test_steps: List[Dict],
        test_name: str = "",
        include_setup: bool = True,
        include_teardown: bool = True,
        browser: str = "chromium",
        headless: bool = True,
        viewport: Dict = None,
        base_url: str = ""
    ) -> str:
        """生成Playwright测试脚本.

        Args:
            test_scenario: 测试场景描述
            test_steps: 测试步骤列表，每个步骤包含 type 和 details
            test_name: 测试名称（可选，自动生成）
            include_setup: 是否包含setup代码
            include_teardown: 是否包含teardown代码
            browser: 浏览器类型
            headless: 是否无头模式
            viewport: 视口大小
            base_url: 基础URL

        Returns:
            生成的TypeScript脚本
        """
        # 生成测试名称
        if not test_name:
            # 从场景描述中提取有意义的名称
            test_name = _generate_test_name(test_scenario)
        
        # 清理测试名称
        test_name = re.sub(r'[^a-zA-Z0-9_]', '_', test_name)
        if not test_name.startswith("test_"):
            test_name = f"test_{test_name}"
        
        # 生成脚本
        script = _generate_script_template(
            test_name=test_name,
            test_scenario=test_scenario,
            test_steps=test_steps,
            include_setup=include_setup,
            include_teardown=include_teardown,
            browser=browser,
            headless=headless,
            viewport=viewport or {"width": 1920, "height": 1080},
            base_url=base_url
        )
        
        return script
    
    return StructuredTool.from_function(
        name="generate_playwright_script",
        func=generate_playwright_script,
        description="""生成Playwright测试脚本。
        
参数：
- test_scenario: 测试场景描述（必需）
- test_steps: 测试步骤列表（必需），每个步骤格式：
  [
    {"type": "navigate", "url": "https://example.com"},
    {"type": "click", "selector": "button.submit"},
    {"type": "fill", "selector": "#username", "value": "testuser"},
    {"type": "assert", "selector": ".success", "expected": "Login successful"}
  ]
- test_name: 测试名称（可选，自动生成）
- include_setup: 是否包含setup代码（可选，默认 True）
- include_teardown: 是否包含teardown代码（可选，默认 True）
- browser: 浏览器类型（可选，默认 "chromium"）
- headless: 是否无头模式（可选，默认 True）
- viewport: 视口大小（可选，默认 {"width": 1920, "height": 1080}）
- base_url: 基础URL（可选）

返回生成的TypeScript脚本代码。""",
    )


def _generate_test_name(scenario: str) -> str:
    """从场景描述生成测试名称."""
    # 提取关键词
    words = re.findall(r'\b\w+\b', scenario.lower())
    
    # 常见测试类型关键词
    test_types = ["login", "logout", "register", "search", "add", "delete", 
                  "update", "view", "list", "filter", "sort", "export", "import"]
    
    # 查找测试类型
    test_type = ""
    for word in words:
        if word in test_types:
            test_type = word
            break
    
    # 如果没有找到特定类型，使用前几个单词
    if not test_type and words:
        test_type = "_".join(words[:3])
    elif not test_type:
        test_type = "scenario"
    
    # 添加时间戳确保唯一性
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return f"{test_type}_{timestamp}"


def _generate_script_template(
    test_name: str,
    test_scenario: str,
    test_steps: List[Dict],
    include_setup: bool,
    include_teardown: bool,
    browser: str,
    headless: bool,
    viewport: Dict,
    base_url: str
) -> str:
    """生成脚本模板."""
    
    # 导入语句
    imports = """import { test, expect } from '@playwright/test';\n"""
    
    # 测试描述
    description = f"""/**
 * {test_scenario}
 * 
 * 测试名称: {test_name}
 * 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 */\n\n"""
    
    # 测试配置
    config = ""
    if base_url:
        config += f"""// 使用项目配置中的 baseURL
test.use({{ baseURL: '{base_url}' }});\n\n"""
    
    # 测试函数
    test_func = f"""test('{test_scenario}', async ({{ page }}) => {{\n"""
    
    # 添加步骤
    for i, step in enumerate(test_steps, 1):
        step_code = _generate_step_code(step, i)
        if step_code:
            test_func += f"  // 步骤 {i}: {step.get('description', step.get('type', 'unknown'))}\n"
            test_func += f"  {step_code}\n"
    
    test_func += "});\n"
    
    # 组合所有部分
    script = imports + "\n" + description + config + test_func
    
    return script


def _generate_step_code(step: Dict, step_num: int) -> str:
    """生成步骤代码."""
    step_type = step.get("type", "").lower()
    
    if step_type == "navigate":
        url = step.get("url", "")
        if url:
            return f"await page.goto('{url}');"
    
    elif step_type == "click":
        selector = step.get("selector", "")
        if selector:
            return f"await page.click('{selector}');"
    
    elif step_type == "fill":
        selector = step.get("selector", "")
        value = step.get("value", "")
        if selector and value is not None:
            return f"await page.fill('{selector}', '{value}');"
    
    elif step_type == "select":
        selector = step.get("selector", "")
        value = step.get("value", "")
        if selector and value:
            return f"await page.selectOption('{selector}', '{value}');"
    
    elif step_type == "hover":
        selector = step.get("selector", "")
        if selector:
            return f"await page.hover('{selector}');"
    
    elif step_type == "press":
        key = step.get("key", "")
        if key:
            return f"await page.press('{key}');"
    
    elif step_type == "wait_for_selector":
        selector = step.get("selector", "")
        timeout = step.get("timeout", 30000)
        if selector:
            return f"await page.waitForSelector('{selector}', {{ timeout: {timeout} }});"
    
    elif step_type == "wait_for_timeout":
        timeout = step.get("timeout", 1000)
        return f"await page.waitForTimeout({timeout});"
    
    elif step_type == "screenshot":
        path = step.get("path", f"step_{step_num}.png")
        return f"await page.screenshot({{ path: '{path}' }});"
    
    elif step_type == "assert":
        selector = step.get("selector", "")
        expected = step.get("expected", "")
        assertion_type = step.get("assertion_type", "to_have_text").lower()
        
        if selector and expected is not None:
            if assertion_type == "to_have_text":
                return f"await expect(page.locator('{selector}')).toHaveText('{expected}');"
            elif assertion_type == "to_be_visible":
                return f"await expect(page.locator('{selector}')).toBeVisible();"
            elif assertion_type == "to_be_hidden":
                return f"await expect(page.locator('{selector}')).toBeHidden();"
            elif assertion_type == "to_have_value":
                return f"await expect(page.locator('{selector}')).toHaveValue('{expected}');"
            elif assertion_type == "to_have_attribute":
                attribute = step.get("attribute", "value")
                return f"await expect(page.locator('{selector}')).toHaveAttribute('{attribute}', '{expected}');"
    
    elif step_type == "custom":
        code = step.get("code", "")
        if code:
            return code
    
    # 未知步骤类型
    return f"// 未知步骤类型: {step_type}"


# 示例脚本模板
EXAMPLE_SCRIPT = """import { test, expect } from '@playwright/test';

/**
 * 示例：用户登录测试
 * 
 * 测试名称: test_login_example
 * 生成时间: 2026-05-30 14:30:00
 */

test('用户登录测试', async ({ page }) => {
  // 步骤 1: 导航到登录页面
  await page.goto('https://example.com/login');
  
  // 步骤 2: 填写用户名
  await page.fill('#username', 'testuser');
  
  // 步骤 3: 填写密码
  await page.fill('#password', 'password123');
  
  // 步骤 4: 点击登录按钮
  await page.click('button[type="submit"]');
  
  // 步骤 5: 验证登录成功
  await expect(page.locator('.welcome-message')).toHaveText('Welcome, testuser!');
  
  // 步骤 6: 截图保存
  await page.screenshot({ path: 'login_success.png' });
});"""