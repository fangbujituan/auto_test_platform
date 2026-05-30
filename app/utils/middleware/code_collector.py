"""
代码收集中间件

拦截 Playwright MCP 工具调用，从工具调用参数提取并生成 TypeScript 代码。

官方 @playwright/mcp 不会返回代码，但工具调用参数包含了完整的操作信息，
我们可以从中提取并生成 TypeScript 代码。

支持的 Playwright MCP 工具：
- browser_navigate: page.goto(url)
- browser_click: page.click(selector) / page.locator(selector).click()
- browser_type: page.type(selector, text) / page.locator(selector).fill(text)
- browser_screenshot: page.screenshot()
- browser_wait: page.waitForSelector(selector)

语义化选择器支持：
- 优先使用 getByRole(), getByText(), getByLabel() 等语义化选择器
- 当无法生成语义化选择器时，回退到 ref 方式

双阶段代码生成（v2.0）：
- 阶段1：工具调用前，生成初步代码
- 阶段2：工具返回后，优化使用 ref 的代码（利用快照更新后的语义信息）
"""

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.utils.debug.readlog import logs

if TYPE_CHECKING:
    from app.utils.middleware.semantic_selector import SemanticSelectorMiddleware


@dataclass
class PendingOperation:
    """待优化的操作"""
    tool_name: str
    tool_args: dict
    code_index: int  # 在 _collected_code 中的索引
    ref: str
    element: str
    action: str
    value: Optional[str] = None


class CodeCollectorMiddleware(AgentMiddleware):
    """
    代码收集中间件
    
    拦截 Playwright MCP 工具调用，从工具调用参数提取并生成 TypeScript 代码。
    支持语义化选择器：优先使用 getByRole(), getByText() 等。
    
    双阶段代码生成：
    1. 工具调用前：记录操作参数，生成初步代码
    2. 工具返回后：优化使用 ref 的代码
    """
    
    @property
    def name(self) -> str:
        return "code_collector"
    
    def __init__(self, semantic_selector: Optional["SemanticSelectorMiddleware"] = None):
        """
        初始化中间件
        
        Args:
            semantic_selector: 语义选择器中间件实例，用于生成语义化代码
        """
        super().__init__()
        self._collected_code: List[str] = []
        self._current_url: Optional[str] = None
        self._semantic_selector = semantic_selector
        # 待优化的操作列表（双阶段生成）
        self._pending_operations: List[PendingOperation] = []
        # 统计信息
        self._ref_count: int = 0
        self._semantic_count: int = 0
        # 🚀 唯一值字段标记
        self._needs_timestamp: bool = False
        # 🚀 P1-001: 上一次操作跟踪（用于智能等待插入）
        self._last_tool_name: Optional[str] = None
        # 🚀 P2-005: 操作序列跟踪（用于模式识别和断言生成）
        self._operation_sequence: List[dict] = []
        logs.info("[CodeCollectorMiddleware] 初始化完成（v2.0 - 双阶段生成）")
    
    def reset(self):
        """重置收集的代码"""
        self._collected_code = []
        self._current_url = None
        self._pending_operations = []
        self._ref_count = 0
        self._semantic_count = 0
        self._needs_timestamp = False
        self._last_tool_name = None
        self._operation_sequence = []
        logs.info("[CodeCollectorMiddleware] 代码已重置")
    
    def get_collected_code(self) -> str:
        """获取收集到的所有代码"""
        code_lines = []
        
        # 🚀 如果有唯一值字段，添加时间戳变量定义
        if self._needs_timestamp:
            code_lines.append("// 唯一值：使用时间戳避免重复数据")
            code_lines.append("const timestamp = Date.now();")
            code_lines.append("")
        
        code_lines.extend(self._collected_code)
        return "\n".join(code_lines)
    
    def get_code_lines(self) -> List[str]:
        """获取代码行列表"""
        return self._collected_code.copy()
    
    def get_selector_stats(self) -> Tuple[int, int]:
        """
        获取选择器统计信息
        
        Returns:
            (ref_count, semantic_count) ref选择器数量和语义化选择器数量
        """
        return self._ref_count, self._semantic_count
    
    def _extract_tool_call_info(self, request) -> tuple:
        """从请求中提取工具调用信息"""
        tool_call = getattr(request, 'tool_call', None)
        if tool_call:
            tool_name = tool_call.get('name', 'unknown')
            tool_args = tool_call.get('args', {})
            # 兼容不同格式
            if not tool_args:
                tool_args = tool_call.get('arguments', {})
            return tool_name, tool_args
        return 'unknown', {}
    
    def _is_submit_like_button(self, element_desc: str) -> bool:
        """
        🚀 P1-001: 判断按钮是否为提交类按钮
        
        提交类按钮点击后通常会触发网络请求或页面跳转，
        需要插入等待逻辑确保操作完成。
        
        Args:
            element_desc: 元素描述文本（来自 tool_args['element']）
            
        Returns:
            True 如果是提交类按钮
        """
        if not element_desc:
            return False
        desc_lower = element_desc.lower()
        submit_keywords = [
            'submit', 'save', 'confirm', 'ok', 'yes', 'apply', 'create', 'add',
            'delete', 'remove', 'update', 'send', 'login', 'sign in', 'register',
            '提交', '保存', '确认', '确定', '删除', '新增', '添加', '登录', '注册',
            '发送', '应用', '创建', '更新',
        ]
        return any(kw in desc_lower for kw in submit_keywords)
    
    def _generate_code_from_tool_call(self, tool_name: str, tool_args: dict) -> Tuple[List[str], Optional[PendingOperation]]:
        """
        根据工具调用生成 TypeScript 代码（阶段1：初步生成）
        
        优先使用语义化选择器，当无法生成时回退到 ref 方式，并记录待优化操作。
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            
        Returns:
            (生成的代码行列表, 待优化操作或None)
        """
        code_lines = []
        pending_op = None
        
        # browser_navigate - 导航
        if tool_name == "browser_navigate":
            url = tool_args.get("url", "")
            if url:
                code_lines.append(f"await page.goto('{url}');")
                # 🚀 P1-001: 导航后自动插入等待，确保页面加载完成
                code_lines.append(f"await page.waitForLoadState('networkidle');")
                self._current_url = url
        
        # browser_click - 点击
        elif tool_name == "browser_click":
            element = tool_args.get("element", "")
            ref = tool_args.get("ref", "")
            
            # 🤖 优先使用 AI 实时生成的代码（最新、最准确）
            ai_code = None
            if self._semantic_selector and ref:
                ai_code = self._semantic_selector.get_ai_generated_code(ref)
            
            if ai_code:
                code_lines.append(f"{ai_code}  // {element}")
                self._semantic_count += 1
                logs.info(f"[CodeCollectorMiddleware] 🤖 使用 AI 实时生成的代码: {ai_code}")
            elif ref:
                # 尝试使用规则生成的语义化选择器
                semantic_code = None
                if self._semantic_selector:
                    # 🚀 传递 element 作为 hint，用于按钮文本提取
                    semantic_code = self._semantic_selector.get_semantic_code(ref, 'click', element_hint=element)
                
                if semantic_code:
                    code_lines.append(f"{semantic_code}  // {element}")
                    self._semantic_count += 1
                    logs.info(f"[CodeCollectorMiddleware] 使用语义化选择器: {semantic_code}")
                else:
                    # 🚨 语义选择器生成失败，使用智能回退策略
                    logs.warning(f"[CodeCollectorMiddleware] ⚠️ 语义选择器生成失败，使用智能回退策略 ref={ref}")
                    
                    # 策略1: 如果 element 有描述性文本，尝试用 getByText（精确匹配）
                    if element and len(element) > 2:
                        safe_element = element.replace("'", "\\'")
                        code_lines.append(f"await page.getByText('{safe_element}', {{ exact: true }}).click();  // {element}")
                        logs.info(f"[CodeCollectorMiddleware] 使用 element 文本作为选择器（精确匹配）: {element}")
                    # 策略2: 使用 JavaScript 执行（终极备用，更稳定）
                    else:
                        code_lines.append(f"// ⚠️ 无法生成稳定选择器，使用 JavaScript 执行")
                        code_lines.append(f"await page.evaluate(() => {{")
                        code_lines.append(f"  // TODO: 手动修改选择器")
                        code_lines.append(f"  document.querySelector('button').click();")
                        code_lines.append(f"}});  // {element}")
                        logs.warning(f"[CodeCollectorMiddleware] 使用 JavaScript 执行作为备用方案")
                    self._ref_count += 1
            elif element:
                code_lines.append(f"await page.click('{element}');")
            
            # 🚀 P1-001: 提交类按钮点击后自动插入等待
            if self._is_submit_like_button(element):
                code_lines.append(f"await page.waitForLoadState('networkidle');  // 等待提交完成")
        
        # browser_type - 输入文本
        elif tool_name == "browser_type":
            element = tool_args.get("element", "")
            text = tool_args.get("text", "")
            ref = tool_args.get("ref", "")
            submit = tool_args.get("submit", False)
            
            # 🚀 检测是否需要唯一值（Charge Code, Item Name, Code, 编号等）
            unique_fields = ['charge code', 'item name', 'code', '编号', 'code:', 'name:', 'item:', 'id']
            is_unique_field = any(kw in element.lower() for kw in unique_fields)
            
            # 🤖 优先使用 AI 实时生成的代码（最新、最准确）
            ai_code = None
            if self._semantic_selector and ref:
                ai_code = self._semantic_selector.get_ai_generated_code(ref)
            
            if ai_code:
                # 如果是唯一值字段，替换文本为时间戳变量
                if is_unique_field and text:
                    # 标记需要生成时间戳变量
                    self._needs_timestamp = True
                    # 将 fill('原文本') 替换为 fill(`${timestamp}`)
                    import re
                    ai_code_modified = re.sub(r"\.fill\(['\"][^'\"]*['\"]\)", ".fill(`${timestamp}`)", ai_code)
                    code_lines.append(f"{ai_code_modified}  // {element} (唯一值)")
                else:
                    code_lines.append(f"{ai_code}  // {element}")
                self._semantic_count += 1
                logs.info(f"[CodeCollectorMiddleware] 🤖 使用 AI 实时生成的代码: {ai_code}")
            elif ref:
                # 尝试使用规则生成的语义化选择器
                semantic_code = None
                if self._semantic_selector:
                    # 🚀 传递 element 作为 hint，用于表单标签提取
                    semantic_code = self._semantic_selector.get_semantic_code(ref, 'fill', text, element_hint=element)
                
                if semantic_code:
                    # 如果是唯一值字段，替换文本为时间戳变量
                    if is_unique_field and text:
                        self._needs_timestamp = True
                        # 将 fill('原文本') 替换为 fill(`${timestamp}`)
                        import re
                        semantic_code = re.sub(r"\.fill\(['\"][^'\"]*['\"]\)", ".fill(`${timestamp}`)", semantic_code)
                        code_lines.append(f"{semantic_code}  // {element} (唯一值)")
                    else:
                        code_lines.append(f"{semantic_code}  // {element}")
                    self._semantic_count += 1
                    logs.info(f"[CodeCollectorMiddleware] 使用语义化选择器: {semantic_code}")
                else:
                    # 🚨 语义选择器生成失败，使用带上下文的回退策略
                    logs.warning(f"[CodeCollectorMiddleware] ⚠️ 语义选择器生成失败，使用上下文回退 ref={ref}")
                    if is_unique_field and text:
                        self._needs_timestamp = True
                        code_lines.append(f"// ⚠️ TODO: 需要手动确认选择器 - 元素描述: {element}")
                        code_lines.append(f"await page.getByRole('textbox').filter({{ hasText: /.*/ }}).first().fill(`${{timestamp}}`);  // {element} (唯一值)")
                    else:
                        code_lines.append(f"// ⚠️ TODO: 需要手动确认选择器 - 元素描述: {element}")
                        code_lines.append(f"await page.getByRole('textbox').filter({{ hasText: /.*/ }}).first().fill('{text}');  // {element}")
                    self._ref_count += 1
            elif element:
                if is_unique_field and text:
                    self._needs_timestamp = True
                    code_lines.append(f"await page.fill('{element}', `${{timestamp}}`);  // 唯一值")
                else:
                    code_lines.append(f"await page.fill('{element}', '{text}');")
            
            if submit:
                code_lines.append("await page.keyboard.press('Enter');")
        
        # browser_screenshot - 截图
        elif tool_name == "browser_screenshot":
            filename = tool_args.get("filename", "screenshot.png")
            code_lines.append(f"await page.screenshot({{ path: '{filename}' }});")
        
        # browser_wait_for - 等待
        elif tool_name == "browser_wait_for":
            selector = tool_args.get("selector", "")
            time = tool_args.get("time", 0)
            if selector:
                code_lines.append(f"await page.waitForSelector('{selector}');")
            elif time:
                # 🚨 时间单位转换：Playwright 的 waitForTimeout 参数是毫秒
                # 如果 time < 1000，假设用户输入的是秒，需要转换为毫秒
                try:
                    time_value = float(time)
                    if time_value < 1000:
                        time_ms = int(time_value * 1000)  # 秒转毫秒
                        logs.info(f"[CodeCollectorMiddleware] 时间单位转换: {time_value}秒 -> {time_ms}毫秒")
                    else:
                        time_ms = int(time_value)  # 已经是毫秒
                except (ValueError, TypeError):
                    time_ms = 1000  # 默认 1 秒
                code_lines.append(f"await page.waitForTimeout({time_ms});")
        
        # browser_scroll - 滚动
        elif tool_name == "browser_scroll":
            direction = tool_args.get("direction", "down")
            amount = tool_args.get("amount", 100)
            if direction == "down":
                code_lines.append(f"await page.mouse.wheel(0, {amount});")
            elif direction == "up":
                code_lines.append(f"await page.mouse.wheel(0, -{amount});")
        
        # browser_hover - 悬停
        elif tool_name == "browser_hover":
            element = tool_args.get("element", "")
            ref = tool_args.get("ref", "")
            
            # 🤖 优先使用 AI 实时生成的代码（最新、最准确）
            ai_code = None
            if self._semantic_selector and ref:
                ai_code = self._semantic_selector.get_ai_generated_code(ref)
            
            if ai_code:
                code_lines.append(f"{ai_code}  // {element}")
                self._semantic_count += 1
                logs.info(f"[CodeCollectorMiddleware] 🤖 使用 AI 实时生成的代码: {ai_code}")
            elif ref:
                # 尝试使用规则生成的语义化选择器
                semantic_code = None
                if self._semantic_selector:
                    semantic_code = self._semantic_selector.get_semantic_code(ref, 'hover')
                
                if semantic_code:
                    code_lines.append(f"{semantic_code}  // {element}")
                    self._semantic_count += 1
                else:
                    # 🚨 hover 语义选择器生成失败，使用元素描述回退
                    logs.warning(f"[CodeCollectorMiddleware] ⚠️ hover 语义选择器生成失败，使用元素描述回退 ref={ref}")
                    if element and len(element) > 2:
                        safe_element = element.replace("'", "\\'")
                        code_lines.append(f"await page.getByText('{safe_element}', {{ exact: true }}).hover();  // {element}")
                    else:
                        code_lines.append(f"// ⚠️ TODO: 需要手动修改选择器 - hover 目标: {element}")
                        code_lines.append(f"await page.locator('[role=\"button\"], [role=\"link\"]').filter({{ hasText: '{element}' }}).first().hover();")
                    self._ref_count += 1
            elif element:
                code_lines.append(f"await page.hover('{element}');")
        
        # browser_evaluate - 执行脚本（增强版：解析 JS 生成等效 Playwright 代码）
        # 🚨 警告：browser_evaluate 操作无法保证稳定性，建议改用语义化工具
        elif tool_name == "browser_evaluate":
            function_code = tool_args.get("function", "") or tool_args.get("script", "")
            if function_code:
                # 尝试解析 JavaScript 代码并生成等效的 Playwright 代码
                parsed_code = self._parse_javascript_to_playwright(function_code)
                if parsed_code:
                    code_lines.extend(parsed_code)
                    logs.info(f"[CodeCollectorMiddleware] 🔧 JS → Playwright: {parsed_code}")
                else:
                    # 无法解析时，保留原始代码作为注释，并添加警告
                    code_lines.append(f"// ⚠️ 以下操作无法自动转换，请手动修改")
                    code_lines.append(f"// 💡 建议：改用 browser_click + browser_snapshot 等语义化工具")
                    code_lines.append(f"// await page.evaluate(`{function_code[:200]}...`);")
                    logs.warning(f"[CodeCollectorMiddleware] ⚠️ JS 无法解析: {function_code[:100]}...")
                    self._ref_count += 1  # 计为需要手动修改的操作
        
        # browser_select - 下拉选择
        elif tool_name == "browser_select":
            element = tool_args.get("element", "")
            value = tool_args.get("value", "")
            ref = tool_args.get("ref", "")
            
            semantic_code = None
            if self._semantic_selector and ref:
                semantic_code = self._semantic_selector.get_semantic_code(ref, 'select', value)
            
            if semantic_code:
                code_lines.append(f"{semantic_code}  // {element}")
                self._semantic_count += 1
            elif ref:
                # 🤖 优先使用 AI 实时生成的代码
                ai_code = None
                if self._semantic_selector:
                    ai_code = self._semantic_selector.get_ai_generated_code(ref)
                
                if ai_code:
                    code_lines.append(f"{ai_code}  // {element}")
                    self._semantic_count += 1
                    logs.info(f"[CodeCollectorMiddleware] 🤖 使用 AI 生成的代码: {ai_code}")
                else:
                    # 🚨 select 语义选择器生成失败，使用元素描述回退
                    logs.warning(f"[CodeCollectorMiddleware] ⚠️ select 语义选择器生成失败，使用元素描述回退 ref={ref}")
                    if element and len(element) > 2:
                        safe_element = element.replace("'", "\\'")
                        code_lines.append(f"// ⚠️ TODO: 需要手动确认选择器 - 元素描述: {element}")
                        code_lines.append(f"await page.getByLabel('{safe_element}').selectOption('{value}');  // {element}")
                    else:
                        code_lines.append(f"// ⚠️ TODO: 需要手动确认选择器 - 元素描述: {element}")
                        code_lines.append(f"await page.getByRole('combobox').selectOption('{value}');  // {element}")
                    self._ref_count += 1
            elif element:
                code_lines.append(f"await page.selectOption('{element}', '{value}');")
        
        # browser_drag - 拖拽
        elif tool_name == "browser_drag":
            source = tool_args.get("sourceElement", "")
            target = tool_args.get("targetElement", "")
            source_ref = tool_args.get("sourceRef", "")
            target_ref = tool_args.get("targetRef", "")
            
            if source_ref and target_ref:
                # 🚨 禁止使用 ref 选择器！改用通用选择器
                logs.warning(f"[CodeCollectorMiddleware] ⚠️ drag 使用通用选择器代替 ref")
                code_lines.append(f"// TODO: drag 操作需要手动调整选择器 (source={source_ref}, target={target_ref})")
                self._ref_count += 2
            elif source and target:
                code_lines.append(f"await page.locator('{source}').dragTo(page.locator('{target}'));")
        
        # browser_close - 关闭
        elif tool_name == "browser_close":
            code_lines.append("await page.close();")
        
        # browser_snapshot - 获取快照（不生成代码，但记录注释）
        elif tool_name == "browser_snapshot":
            code_lines.append("// 获取页面快照")
        
        return code_lines, pending_op

    def _parse_javascript_to_playwright(self, js_code: str) -> list:
        """
        解析 JavaScript 代码并生成等效的 Playwright 代码
        
        支持的操作模式：
        1. element.click() → page.click(selector)
        2. element.value = x → page.fill(selector, x)
        3. querySelector → page.locator(selector)
        4. dispatchEvent → page.locator().dispatchEvent()
        
        Args:
            js_code: JavaScript 代码字符串
            
        Returns:
            生成的 Playwright 代码列表，如果无法解析则返回空列表
        """
        import re
        
        code_lines = []
        
        # 清理代码
        js_code = js_code.strip()
        if not js_code:
            return []
        
        # 移除外层的 () => { ... } 或 function() { ... }
        arrow_match = re.match(r'^\s*\(\s*\)\s*=>\s*\{(.*)\}\s*$', js_code, re.DOTALL)
        if arrow_match:
            js_code = arrow_match.group(1).strip()
        
        func_match = re.match(r'^\s*function\s*\(\s*\)\s*\{(.*)\}\s*$', js_code, re.DOTALL)
        if func_match:
            js_code = func_match.group(1).strip()
        
        # 1. 检测 click() 操作
        # 模式: element.click() 或 document.querySelector('xxx').click()
        click_patterns = [
            r"document\.querySelector\(['\"]([^'\"]+)['\"]\)\.click\(\)",
            r"document\.getElementById\(['\"]([^'\"]+)['\"]\)\.click\(\)",
            r"querySelector\(['\"]([^'\"]+)['\"]\)\.click\(\)",
            r"getElementById\(['\"]([^'\"]+)['\"]\)\.click\(\)",
        ]
        
        for pattern in click_patterns:
            match = re.search(pattern, js_code)
            if match:
                selector = match.group(1)
                # 转换为 Playwright 选择器
                pw_selector = self._convert_to_playwright_selector(selector)
                code_lines.append(f"await page.locator('{pw_selector}').click();")
                return code_lines
        
        # 2. 检测 value 赋值操作
        # 模式: element.value = 'xxx'
        value_pattern = r"(?:document\.)?querySelector\(['\"]([^'\"]+)['\"]\)\.value\s*=\s*['\"]([^'\"]*)['\"]"
        match = re.search(value_pattern, js_code)
        if match:
            selector = match.group(1)
            value = match.group(2)
            pw_selector = self._convert_to_playwright_selector(selector)
            code_lines.append(f"await page.locator('{pw_selector}').fill('{value}');")
            return code_lines
        
        # 3. 检测 dispatchEvent 操作
        # 模式: element.dispatchEvent(new Event('input', { bubbles: true }))
        event_pattern = r"(?:document\.)?querySelector\(['\"]([^'\"]+)['\"]\)\.dispatchEvent\(new\s+Event\(['\"]([^'\"]+)['\"]"
        match = re.search(event_pattern, js_code)
        if match:
            selector = match.group(1)
            event_type = match.group(2)
            pw_selector = self._convert_to_playwright_selector(selector)
            code_lines.append(f"await page.locator('{pw_selector}').dispatchEvent('{event_type}');")
            return code_lines
        
        # 4. 检测 console.log 输出（通常是查询操作，跳过）
        if 'console.log' in js_code and 'click' not in js_code.lower():
            # 这是查询/打印操作，不需要生成代码
            return ["// 查询页面元素"]
        
        # 5. 检测 return 语句（返回数据的操作，跳过）
        if js_code.strip().startswith('return '):
            return ["// 获取页面数据"]
        
        # 6. 🚀 新增：检测常见的 DOM 操作模式
        # 检测 .textContent.includes() 模式（查找文本）
        if 'textContent' in js_code and 'includes' in js_code:
            return ["// 查找包含特定文本的元素"]
        
        # 检测 .click() 调用（即使不是 querySelector）
        if '.click()' in js_code:
            # 尝试提取选择器
            selector_match = re.search(r"['\"]([^'\"]+)['\"]", js_code)
            if selector_match:
                selector = selector_match.group(1)
                pw_selector = self._convert_to_playwright_selector(selector)
                return [f"await page.locator('{pw_selector}').click();"]
            else:
                return [f"await page.evaluate(() => {{ {js_code[:200]}... }});  // 复杂 click 操作"]
        
        # 检测 .value = 赋值（即使不是 querySelector）
        if '.value' in js_code and '=' in js_code:
            value_match = re.search(r"\.value\s*=\s*['\"]([^'\"]*)['\"]", js_code)
            selector_match = re.search(r"['\"]([^'\"]+)['\"]", js_code)
            if value_match and selector_match:
                selector = selector_match.group(1)
                value = value_match.group(1)
                pw_selector = self._convert_to_playwright_selector(selector)
                return [f"await page.locator('{pw_selector}').fill('{value}');"]
        
        # 7. 🚀 无法完全解析时，生成 page.evaluate() 调用而不是注释
        # 这样代码仍然可以执行，而不是完全被忽略
        if len(js_code) > 50:
            # 截断长代码，避免生成的文件过大
            truncated_js = js_code[:300] + "..." if len(js_code) > 300 else js_code
            # 转义字符串中的特殊字符
            escaped_js = truncated_js.replace('`', '\\`').replace('$', '\\$')
            return [f"await page.evaluate(() => {{ {escaped_js} }});  // ⚠️ 请手动检查"]
        
        # 无法解析且代码很短，返回空列表
        return []
    
    def _convert_to_playwright_selector(self, css_selector: str) -> str:
        """
        将 CSS 选择器转换为更适合 Playwright 的形式
        
        Args:
            css_selector: CSS 选择器（如 #id, .class, [attr=value]）
            
        Returns:
            Playwright 选择器
        """
        import re
        
        # ID 选择器: #id → #id (保持不变)
        if css_selector.startswith('#'):
            return css_selector
        
        # 类选择器: .class → .class (保持不变)
        if css_selector.startswith('.'):
            return css_selector
        
        # 属性选择器: [name="xxx"] → [name="xxx"] (保持不变)
        if css_selector.startswith('['):
            return css_selector
        
        # 标签选择器: input → input (保持不变)
        if re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', css_selector):
            return css_selector
        
        # 复合选择器，保持原样
        return css_selector

    def _optimize_pending_code(self):
        """
        优化待处理的代码（阶段2：后处理）
        
        在快照更新后，尝试将 ref 选择器替换为语义化选择器。
        未优化的操作会保留，等待下次快照更新时重试。
        """
        if not self._pending_operations or not self._semantic_selector:
            return

        optimized = 0
        remaining_ops = []  # 保留未优化的操作

        for op in self._pending_operations:
            # 尝试获取语义化代码
            semantic_code = self._semantic_selector.get_semantic_code(op.ref, op.action, op.value)
            
            if semantic_code:
                # 替换代码
                old_code = self._collected_code[op.code_index]
                new_code = f"{semantic_code}  // {op.element}"
                
                if old_code != new_code:
                    self._collected_code[op.code_index] = new_code
                    self._ref_count -= 1
                    self._semantic_count += 1
                    optimized += 1
                    logs.info(f"[CodeCollectorMiddleware] 后处理优化: ref={op.ref} → {semantic_code}")
                else:
                    # 代码已相同，标记为已处理
                    pass
            else:
                # 无法优化，保留等待下次快照更新
                remaining_ops.append(op)
                logs.debug(f"[CodeCollectorMiddleware] 无法优化 ref={op.ref}，等待下次快照更新")

        # 只保留未优化的操作
        self._pending_operations = remaining_ops
        
        if optimized > 0:
            logs.info(f"[CodeCollectorMiddleware] 后处理完成，优化了 {optimized} 个选择器，剩余 {len(remaining_ops)} 个待优化")
        elif remaining_ops:
            logs.info(f"[CodeCollectorMiddleware] 快照中未找到语义信息，{len(remaining_ops)} 个操作等待下次快照更新")

    async def awrap_tool_call(self, request, handler):
        """
        异步拦截工具执行，生成代码
        
        新流程（实时 AI 生成）：
        1. 工具调用前，生成代码（优先使用 AI 实时生成的语义化代码）
        2. 无需后处理优化
        
        AI 实时生成由 SemanticSelectorMiddleware 完成，
        这里只需获取生成的代码即可。
        """
        # 提取工具调用信息
        tool_name, tool_args = self._extract_tool_call_info(request)
        
        # 🚀 P0-004: 跳过内部自动注入的工具调用（不生成代码）
        tool_call = getattr(request, 'tool_call', None)
        if tool_call and isinstance(tool_call, dict) and tool_call.get('_internal'):
            logs.debug(f"[CodeCollectorMiddleware] 跳过内部工具调用: {tool_name}")
            return await handler(request)
        
        logs.info(f"[CodeCollectorMiddleware] 拦截工具调用: {tool_name}")
        if tool_args:
            args_str = json.dumps(tool_args, ensure_ascii=False)
            logs.info(f"[CodeCollectorMiddleware] 工具参数: {args_str[:200]}")
        
        # 生成代码（优先使用 AI 实时生成的语义化代码）
        if tool_name.startswith('browser_'):
            # 🚀 P2-005: 跟踪操作序列
            self._track_operation(tool_name, tool_args)
            
            # 🚀 P2-005: 检测操作模式，插入结构化注释
            pattern_comment = self._detect_pattern_and_comment()
            if pattern_comment:
                self._collected_code.append(pattern_comment)
            
            generated_code, _ = self._generate_code_from_tool_call(tool_name, tool_args)
            if generated_code:
                logs.info(f"[CodeCollectorMiddleware] 生成代码: {generated_code}")
                self._collected_code.extend(generated_code)
            self._last_tool_name = tool_name
        
        # 调用原始工具
        result = await handler(request)
        
        # 🚀 P2-005: 工具返回后生成断言
        if tool_name.startswith('browser_'):
            result_content = None
            if hasattr(result, 'content'):
                result_content = str(result.content)[:500] if result.content else None
            assertions = self._generate_assertion(tool_name, tool_args, result_content)
            if assertions:
                self._collected_code.extend(assertions)
        
        return result
    
    def optimize_all_selectors_with_ai(self) -> int:
        """
        使用 AI 优化所有选择器（在脚本保存前调用）
        
        遍历所有收集的代码行，将使用 ref 选择器的代码行交给 AI 优化。
        这是一次性投资，优化后的脚本可以重复使用无需再次调用 AI。
        
        Returns:
            优化的代码行数
        """
        if not self._semantic_selector:
            logs.warning("[CodeCollectorMiddleware] ⚠️ semantic_selector 未设置，跳过 AI 优化")
            return 0
        
        if not self._collected_code:
            logs.info("[CodeCollectorMiddleware] 没有收集到代码，跳过 AI 优化")
            return 0
        
        import re
        
        optimized_count = 0
        pending_for_ai = []  # 收集需要 AI 优化的操作
        
        # 找出所有使用 ref 选择器的代码行
        ref_pattern = re.compile(r"\[ref=\"(e\d+)\"\]")
        
        for i, code_line in enumerate(self._collected_code):
            match = ref_pattern.search(code_line)
            if not match:
                continue
            
            ref = match.group(1)
            
            # 判断操作类型
            action = None
            value = None
            
            if '.click()' in code_line:
                action = 'click'
            elif '.fill(' in code_line:
                action = 'fill'
                # 提取 fill 的值
                fill_match = re.search(r"\.fill\('([^']*)'\)", code_line)
                if fill_match:
                    value = fill_match.group(1)
            elif '.hover()' in code_line:
                action = 'hover'
            elif '.selectOption(' in code_line:
                action = 'select'
                select_match = re.search(r"\.selectOption\('([^']*)'\)", code_line)
                if select_match:
                    value = select_match.group(1)
            
            if action:
                pending_for_ai.append({
                    'index': i,
                    'ref': ref,
                    'action': action,
                    'value': value,
                    'original_code': code_line
                })
        
        if not pending_for_ai:
            logs.info("[CodeCollectorMiddleware] 没有需要 AI 优化的选择器")
            return 0
        
        logs.info(f"[CodeCollectorMiddleware] 🤖 开始 AI 优化 {len(pending_for_ai)} 个选择器...")
        
        # 逐个优化
        for item in pending_for_ai:
            ai_code = self._semantic_selector.optimize_selector_with_ai(
                item['ref'], 
                item['action'], 
                item['value']
            )
            
            if ai_code:
                # 提取注释（如果有）
                comment = ""
                if '//' in item['original_code']:
                    comment = "  // " + item['original_code'].split('//', 1)[1].strip()
                
                # 替换代码
                new_code = ai_code + comment
                self._collected_code[item['index']] = new_code
                self._ref_count -= 1
                self._semantic_count += 1
                optimized_count += 1
                logs.info(f"[CodeCollectorMiddleware] AI 优化成功: ref={item['ref']} → {ai_code}")
            else:
                logs.warning(f"[CodeCollectorMiddleware] AI 优化失败，保留原代码: ref={item['ref']}")
        
        # 清空 pending operations（因为已经尝试过 AI 优化）
        self._pending_operations = []
        
        logs.info(f"[CodeCollectorMiddleware] AI 优化完成: {optimized_count}/{len(pending_for_ai)} 个选择器已优化")
        return optimized_count
    
    def _track_operation(self, tool_name: str, tool_args: dict):
        """
        P2-005: 跟踪操作序列，用于模式识别和断言生成
        """
        self._operation_sequence.append({
            'tool': tool_name,
            'args': tool_args,
            'url': self._current_url,
        })
    
    def _generate_assertion(self, tool_name: str, tool_args: dict, result_content: str = None) -> List[str]:
        """
        P2-005: 根据操作类型和结果生成断言代码
        
        断言策略：
        - navigate 后：验证 URL
        - 提交类 click 后：验证成功提示
        - fill 后：不生成断言（中间操作）
        """
        assertions = []
        
        if tool_name == "browser_navigate":
            url = tool_args.get("url", "")
            if url:
                # 提取 URL 的关键路径部分作为正则
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path_pattern = parsed.path.rstrip('/') if parsed.path else ''
                if path_pattern and path_pattern != '/':
                    assertions.append(f"await expect(page).toHaveURL(/{re.escape(path_pattern).replace(chr(92) + chr(92), chr(92))}/);")
        
        elif tool_name == "browser_click":
            element = tool_args.get("element", "")
            # 提交类按钮点击后，检查成功提示
            if self._is_submit_like_button(element):
                assertions.append(f"// 断言：验证操作结果")
                assertions.append(f"await expect(page.getByText(/成功|success|saved|completed/i)).toBeVisible({{ timeout: 10000 }});")
        
        return assertions
    
    def _detect_pattern_and_comment(self) -> Optional[str]:
        """
        P2-005: 检测操作序列模式，生成结构化注释
        
        支持的模式：
        - 登录：navigate + fill + fill + click
        - 表单填写：连续 3+ 个 fill
        - 搜索：fill + click(search)
        """
        seq = self._operation_sequence
        if len(seq) < 3:
            return None
        
        # 检测最近的操作模式
        recent = seq[-4:] if len(seq) >= 4 else seq
        tools = [op['tool'] for op in recent]
        
        # 登录模式：navigate + type + type + click
        if (len(tools) >= 4 and 
            tools[-4] == 'browser_navigate' and 
            tools[-3] == 'browser_type' and 
            tools[-2] == 'browser_type' and 
            tools[-1] == 'browser_click'):
            return "// === 登录流程 ==="
        
        # 表单填写模式：连续 3+ 个 type
        type_count = 0
        for op in reversed(seq):
            if op['tool'] == 'browser_type':
                type_count += 1
            else:
                break
        if type_count >= 3:
            return f"// === 表单填写（{type_count} 个字段）==="
        
        # 搜索模式：type + click(search/查询/搜索)
        if (len(tools) >= 2 and 
            tools[-2] == 'browser_type' and 
            tools[-1] == 'browser_click'):
            element = seq[-1]['args'].get('element', '')
            search_keywords = ['search', '搜索', '查询', 'filter', '筛选', 'query']
            if any(kw in element.lower() for kw in search_keywords):
                return "// === 搜索/筛选操作 ==="
        
        return None

    def generate_script(
        self,
        name: str = "recorded_test",
        description: str = "",
        variables: Optional[List[str]] = None
    ) -> str:
        """
        生成完整的 Playwright TypeScript 测试脚本
        
        Args:
            name: 测试名称
            description: 测试描述
            variables: 变量名列表（如 ['username', 'password']）
            
        Returns:
            完整的 TypeScript 测试脚本
        """
        lines = [
            "import { test, expect } from '@playwright/test';",
            "",
            f"test('{name}', async ({{ page }}) => {{",
        ]
        
        if description:
            lines.insert(2, f"/* {description} */")
            lines.insert(3, "")
        
        # 添加收集的代码
        for code_line in self._collected_code:
            lines.append(f"  {code_line}")
        
        lines.append("});")
        
        return "\n".join(lines)


# 单例实例，用于在整个会话中共享
_collector_instance: Optional[CodeCollectorMiddleware] = None


def get_collector(semantic_selector: Optional["SemanticSelectorMiddleware"] = None) -> CodeCollectorMiddleware:
    """
    获取代码收集器单例
    
    Args:
        semantic_selector: 语义选择器中间件实例
        
    Returns:
        CodeCollectorMiddleware 实例
    """
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = CodeCollectorMiddleware(semantic_selector=semantic_selector)
    elif semantic_selector and _collector_instance._semantic_selector is None:
        _collector_instance._semantic_selector = semantic_selector
    return _collector_instance


def reset_collector():
    """重置代码收集器"""
    global _collector_instance
    if _collector_instance:
        _collector_instance.reset()