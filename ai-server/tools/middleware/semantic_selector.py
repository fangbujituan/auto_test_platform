"""
语义选择器中间件

拦截 Playwright MCP 工具调用，从快照中提取语义信息，
用于生成语义化的 TypeScript 代码。

核心功能：
1. 解析页面快照，提取元素的语义信息（role, name, text 等）
2. 为 CodeCollectorMiddleware 提供语义信息
3. 记录转换日志，便于调试
4. 智能自动恢复机制：
   - 维护元素语义缓存（ref -> 语义信息）
   - 当 ref 失效时，使用元素描述在快照中搜索匹配元素
   - 如果找到匹配元素，自动构造新请求重试
   - 支持模糊匹配和相似度评分

注意：由于 Playwright MCP 的 browser_click 工具只接受 ref 参数，
运行时仍使用 ref，但录制的脚本可以使用语义化选择器。

第四次修复 (2026-03-17)：
- 增强元素语义缓存机制（ref → 语义信息的持久缓存）
- 支持从缓存中获取语义信息（用于双阶段代码生成）
- 提取更多稳定属性（data-testid, aria-label 等）
- 支持选择器优先级策略
- 提供选择器质量评估
"""

import re
import json
from typing import Any, Optional, Dict, List, Tuple
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import ToolException
from langchain_core.messages import ToolMessage

from tools.debug.readlog import logs
from tools.middleware.selector_scores import (
    TEXT_SCORE_RANGE, EXACT_PENALTY,
    TEST_ID, OTHER_TEST_ID, IFRAME_BY_ATTRIBUTE,
    BEGIN_PENALIZED, ROLE_WITH_NAME, ARIA_LABEL,
    PLACEHOLDER, LABEL, ALT_TEXT, TEXT, TITLE, TEXT_REGEX,
    ROLE_WITH_NAME_EXACT, PLACEHOLDER_EXACT, LABEL_EXACT,
    ALT_TEXT_EXACT, TEXT_EXACT, TITLE_EXACT,
    END_PENALIZED, CSS_ID, ROLE_WITHOUT_NAME,
    CSS_NAME, CSS_INPUT_TYPE, CSS_TAG_NAME,
    NTH, CSS_FALLBACK, SCORE_THRESHOLD_FOR_TEXT_EXPECT,
    SELECTOR_SCORES,
)


# 选择器优先级（从高到低）
SELECTOR_PRIORITY = [
    # 1. 最稳定：语义化选择器
    ("getByRole", "role + name"),           # button, link, textbox 等
    ("getByLabel", "关联 label"),           # 表单元素
    ("getByPlaceholder", "placeholder"),    # 输入框
    ("getByText", "文本内容"),              # 通用
    
    # 2. 较稳定：属性选择器
    ("getByTestId", "data-testid"),         # 测试专用属性
    ("[name]", "name 属性"),                # 表单 name
    ("[id]", "稳定 ID"),                    # 需要判断是否动态生成
    
    # 3. 最后手段（需要警告）
    ("[ref]", "临时引用 - 警告：不稳定！"),
]


# ============================================================================
# Codegen 风格的选择器评分常量（统一从 selector_scores.py 导入）
# 分数越低越好！分数越低代表选择器越稳定、越可靠。
# 以下 K_* 别名保持向后兼容
# ============================================================================

K_TEXT_SCORE_RANGE = TEXT_SCORE_RANGE
K_EXACT_PENALTY = EXACT_PENALTY
K_TEST_ID_SCORE = TEST_ID
K_OTHER_TEST_ID_SCORE = OTHER_TEST_ID
K_IFRAME_BY_ATTRIBUTE_SCORE = IFRAME_BY_ATTRIBUTE
K_BEGIN_PENALIZED_SCORE = BEGIN_PENALIZED
K_ROLE_WITH_NAME_SCORE = ROLE_WITH_NAME
K_ARIA_LABEL_SCORE = ARIA_LABEL
K_PLACEHOLDER_SCORE = PLACEHOLDER
K_LABEL_SCORE = LABEL
K_ALT_TEXT_SCORE = ALT_TEXT
K_TEXT_SCORE = TEXT
K_TITLE_SCORE = TITLE
K_TEXT_SCORE_REGEX = TEXT_REGEX
K_PLACEHOLDER_SCORE_EXACT = PLACEHOLDER_EXACT
K_LABEL_SCORE_EXACT = LABEL_EXACT
K_ROLE_WITH_NAME_SCORE_EXACT = ROLE_WITH_NAME_EXACT
K_ALT_TEXT_SCORE_EXACT = ALT_TEXT_EXACT
K_TEXT_SCORE_EXACT = TEXT_EXACT
K_TITLE_SCORE_EXACT = TITLE_EXACT
K_END_PENALIZED_SCORE = END_PENALIZED
K_CSS_ID_SCORE = CSS_ID
K_ROLE_WITHOUT_NAME_SCORE = ROLE_WITHOUT_NAME
K_CSS_NAME_SCORE = CSS_NAME
K_CSS_INPUT_TYPE_NAME_SCORE = CSS_INPUT_TYPE
K_CSS_TAG_NAME_SCORE = CSS_TAG_NAME
K_NTH_SCORE = NTH
K_CSS_FALLBACK_SCORE = CSS_FALLBACK
K_SCORE_THRESHOLD_FOR_TEXT_EXPECT = SCORE_THRESHOLD_FOR_TEXT_EXPECT


# ============================================================================
# Codegen 风格的文本变体生成函数（移植自 Playwright selectorGenerator.ts）
# ============================================================================

def _trim_word_boundary(text: str, max_length: int) -> str:
    """
    在单词边界处截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    text = text[:max_length]
    
    # 找到最后一个单词边界
    import re
    match = re.match(r'^(.*)\b(.+?)$', text)
    if not match:
        return ''
    
    return match.group(1).rstrip()


def suitable_text_alternatives(text: str) -> List[Dict[str, Any]]:
    """
    生成文本的多个匹配方案（Codegen 风格 + 增强）
    
    策略：
    1. 去掉开头的数字部分
    2. 去掉结尾的数字部分
    3. 去掉括号内容（如 "保存 (Ctrl+S)" → "保存"）
    4. 去掉省略号（如 "更多..." → "更多"）
    5. 去掉数量词（如 "删除 3 项" → "删除"）
    6. 截断到 80 字符
    7. 截断到 30 字符
    8. 原始文本
    
    Args:
        text: 原始文本
        
    Returns:
        变体列表 [{'text': 变体文本, 'score_bonus': 分数奖励}, ...]
        score_bonus: 0 表示最好，越大越差
    """
    from typing import Any, List, Dict
    
    result: List[Dict[str, Any]] = []
    
    # 策略 1: 去掉开头的数字部分
    match = re.match(r'^([\d.,]+)[^.,\w]', text)
    leading_number_length = match.group(1).__len__() if match else 0
    if leading_number_length:
        alt = _trim_word_boundary(text[leading_number_length:].lstrip(), 80)
        if alt:
            result.append({'text': alt, 'score_bonus': 2 if len(alt) <= 30 else 1})
    
    # 策略 2: 去掉结尾的数字部分
    match = re.search(r'[^.,\w]([\d.,]+)$', text)
    trailing_number_length = match.group(1).__len__() if match else 0
    if trailing_number_length:
        alt = _trim_word_boundary(text[:-trailing_number_length].rstrip(), 80)
        if alt:
            result.append({'text': alt, 'score_bonus': 2 if len(alt) <= 30 else 1})
    
    # 🚀 P3-003: 策略 3: 去掉括号内容（中英文括号）
    bracket_stripped = re.sub(r'\s*[\(（][^)）]*[\)）]', '', text).strip()
    if bracket_stripped and bracket_stripped != text and len(bracket_stripped) >= 2:
        result.append({'text': bracket_stripped, 'score_bonus': 1})
    
    # 🚀 P3-003: 策略 4: 去掉省略号
    ellipsis_stripped = re.sub(r'[.。…]+$', '', text).strip()
    if ellipsis_stripped and ellipsis_stripped != text and len(ellipsis_stripped) >= 2:
        result.append({'text': ellipsis_stripped, 'score_bonus': 1})
    
    # 🚀 P3-003: 策略 5: 去掉数量词（中文：N 项/个/条/件，英文：N items）
    quantity_stripped = re.sub(r'\s*\d+\s*(项|个|条|件|次|份|张|页|items?|records?|rows?)\s*$', '', text).strip()
    if quantity_stripped and quantity_stripped != text and len(quantity_stripped) >= 2:
        result.append({'text': quantity_stripped, 'score_bonus': 2})
    
    # 策略 6 & 7: 根据长度决定
    if len(text) <= 30:
        result.append({'text': text, 'score_bonus': 0})
    else:
        result.append({'text': _trim_word_boundary(text, 80), 'score_bonus': 0})
        result.append({'text': _trim_word_boundary(text, 30), 'score_bonus': 1})
    
    # 过滤空结果并去重
    result = [r for r in result if r['text']]
    seen = set()
    unique_result = []
    for r in result:
        if r['text'] not in seen:
            seen.add(r['text'])
            unique_result.append(r)
    
    # 如果没有有效变体，返回原始文本截断
    if not unique_result:
        unique_result.append({'text': text[:80], 'score_bonus': 0})
    
    return unique_result


class SemanticSelectorMiddleware(AgentMiddleware):
    """
    语义选择器中间件
    
    从页面快照中提取元素语义信息，用于生成语义化选择器。
    
    智能恢复机制：
    当 ref 失效时，自动尝试在快照中找到语义匹配的元素并重试。
    
    缓存机制：
    维护 ref → 语义信息 的映射，支持双阶段代码生成。
    
    🆕 原始 HTML 增强功能：
    1. 缓存原始 HTML，提取 label for 关联
    2. 提取所有元素的稳定属性（id, name, data-*, class, type 等）
    3. 建立 ref → HTML 属性 的映射关系
    4. 在生成选择器时，优先使用 HTML 中的稳定属性
    """
    
    @property
    def name(self) -> str:
        return "semantic_selector"
    
    def __init__(self):
        """初始化中间件"""
        super().__init__()
        self._current_snapshot: str = ""
        # 🚀 P3-001: 缓存大小限制
        self._CACHE_MAX_SIZE = 500
        # 元素语义缓存：ref -> 语义信息（持久缓存）
        self._element_cache: Dict[str, dict] = {}
        # 快照上下文缓存：ref -> 快照片段（用于 AI 优化）
        self._snapshot_context_cache: Dict[str, str] = {}
        # AI 实时生成的语义化代码：ref -> 语义化代码
        self._ai_generated_code: Dict[str, str] = {}
        # 快照中的所有元素列表（用于搜索）
        self._all_elements: List[dict] = []
        # 操作计数器（用于触发快照更新提醒）
        self._operation_count: int = 0
        self._snapshot_age: int = 0
        # 选择器统计
        self._selector_stats: Dict[str, int] = {
            'semantic': 0,  # 语义化选择器数量
            'ref': 0,       # ref 选择器数量
            'fallback': 0,  # 回退选择器数量
        }
        # 🆕 原始 HTML DOM 缓存（用于判断 label for 关联）
        self._raw_html_cache: str = ""
        # 🆕 label for 映射缓存：input_id -> label_text
        self._label_for_cache: Dict[str, str] = {}
        # 🆕 HTML 元素属性缓存：用于生成更精确的选择器
        # 格式: {element_signature: {id, name, class, data-*, type, placeholder, ...}}
        self._html_element_attrs: Dict[str, dict] = {}
        # 🆕 ref → HTML 属性映射（通过位置关联）
        self._ref_to_html_attrs: Dict[str, dict] = {}
        # 🆕🚀 JS 注入检测结果缓存：存储通过 JS 检测的可交互元素
        self._js_detected_elements: List[dict] = []
        # 🆕🚀 JS 增强的 label[for] 关联缓存（比 HTML 解析更准确）
        self._js_label_for_cache: Dict[str, str] = {}
        # 🆕🚀 元素 xpath → JS 检测属性映射
        self._xpath_to_js_attrs: Dict[str, dict] = {}
        # 🆕🚀 xpath → JS 最佳选择器映射
        self._js_best_selector_map: Dict[str, dict] = {}
        # 🚀 P0-004: 自动 JS 注入跟踪
        self._js_auto_injected_url: Optional[str] = None  # 已注入的 URL，避免重复注入
        self._js_auto_inject_enabled: bool = True  # 是否启用自动注入
        # 🚀 P0-004: 外部注入的工具列表（由 make_recording_agent 设置）
        self._available_tools: List[Any] = []
        self._browser_evaluate_tool: Any = None  # 缓存的 browser_evaluate 工具实例
        self._evaluate_param_name: Optional[str] = None  # 缓存的 browser_evaluate 参数名
        logs.info("[SemanticSelectorMiddleware] 初始化完成（v9 - 自动 JS 注入版）")
    
    def set_tools(self, tools: list):
        """
        🚀 P0-004: 设置可用工具列表（由 make_recording_agent 在工具加载后调用）
        
        从工具列表中查找并缓存 browser_evaluate 工具实例，
        用于自动 JS 注入检测。
        
        Args:
            tools: MCP 工具列表（StructuredTool 实例）
        """
        self._available_tools = tools or []
        self._browser_evaluate_tool = None  # 重置缓存
        
        for t in self._available_tools:
            tool_name = getattr(t, 'name', '')
            if tool_name == 'browser_evaluate':
                self._browser_evaluate_tool = t
                # 打印工具的输入 schema，用于调试参数名
                schema = getattr(t, 'args_schema', None)
                if schema:
                    try:
                        schema_info = schema.schema() if hasattr(schema, 'schema') else str(schema)
                        logs.info(f"[SemanticSelectorMiddleware] ✅ 找到 browser_evaluate 工具，schema: {schema_info}")
                    except Exception:
                        logs.info(f"[SemanticSelectorMiddleware] ✅ 找到 browser_evaluate 工具（schema 解析失败）")
                else:
                    logs.info(f"[SemanticSelectorMiddleware] ✅ 找到 browser_evaluate 工具（无 schema）")
                break
        
        if not self._browser_evaluate_tool:
            logs.warning(f"[SemanticSelectorMiddleware] ⚠️ 未在工具列表中找到 browser_evaluate")
            tool_names = [getattr(t, 'name', '?') for t in self._available_tools[:20]]
            logs.debug(f"[SemanticSelectorMiddleware] 可用工具（前20）: {tool_names}")
    
    def get_selector_stats(self) -> Dict[str, int]:
        """获取选择器统计信息"""
        return self._selector_stats.copy()
    
    def reset(self):
        """
        重置中间件状态
        
        清空快照缓存、元素缓存和统计信息。
        在开始新任务或切换页面时应调用此方法。
        """
        self._current_snapshot = ""
        self._element_cache = {}
        self._snapshot_context_cache = {}
        self._ai_generated_code = {}
        self._all_elements = []
        self._operation_count = 0
        self._snapshot_age = 0
        self._selector_stats = {
            'semantic': 0,
            'ref': 0,
            'fallback': 0,
        }
        # 清空原始 DOM 缓存
        self._raw_html_cache = ""
        self._label_for_cache = {}
        # 清空 HTML 属性缓存
        self._html_element_attrs = {}
        self._ref_to_html_attrs = {}
        # 🆕🚀 清空 JS 注入检测缓存
        self._js_detected_elements = []
        self._js_label_for_cache = {}
        self._xpath_to_js_attrs = {}
        self._js_best_selector_map = {}
        self._js_auto_injected_url = None
        logs.info("[SemanticSelectorMiddleware] 状态已重置")
    
    def _parse_element_from_snapshot(self, ref: str) -> Optional[dict]:
        """
        从当前快照中解析元素的语义信息
        
        Args:
            ref: 元素引用（如 e45）
            
        Returns:
            包含 role, name, text 等信息的字典
        """
        if not self._current_snapshot or not ref:
            return None
        
        # 查找包含 ref 的行
        for line in self._current_snapshot.split('\n'):
            if f'[ref={ref}]' in line:
                element_info = self._parse_element_line(line, ref)
                if element_info:
                    return element_info
        
        return None
    
    def _parse_element_line(self, line: str, ref: str = None) -> Optional[dict]:
        """
        解析快照中的一行元素信息
        
        支持提取：
        - role: 元素角色（button, link, textbox 等）
        - name: 可访问名称
        - text: 文本内容
        - type: 元素类型
        - data-testid: 测试 ID
        - aria-label: ARIA 标签
        - placeholder: 占位符
        
        Args:
            line: 快照中的一行
            ref: 元素引用（可选，会从行中提取）
            
        Returns:
            元素信息字典
        """
        element_info = {}
        
        # 提取 ref
        if not ref:
            ref_match = re.search(r'\[ref=(\w+)\]', line)
            if ref_match:
                ref = ref_match.group(1)
        
        if ref:
            element_info['ref'] = ref
        
        # 提取 role
        role_match = re.search(r'\[role=(\w+)\]', line)
        if role_match:
            element_info['role'] = role_match.group(1)
        
        # 提取 name
        name_match = re.search(r'\[name="([^"]+)"\]', line)
        if name_match:
            element_info['name'] = name_match.group(1)
        
        # 提取 data-testid
        testid_match = re.search(r'\[data-testid="([^"]+)"\]', line)
        if testid_match:
            element_info['data-testid'] = testid_match.group(1)
        
        # 提取 aria-label
        aria_label_match = re.search(r'\[aria-label="([^"]+)"\]', line)
        if aria_label_match:
            element_info['aria-label'] = aria_label_match.group(1)
        
        # 提取 placeholder
        placeholder_match = re.search(r'\[placeholder="([^"]+)"\]', line)
        if placeholder_match:
            element_info['placeholder'] = placeholder_match.group(1)
        
        # 提取元素类型和文本（针对 link, button 等）
        # 格式: - link "Invoice" [ref=e204]:
        type_text_match = re.search(r'- (\w+)\s+"([^"]+)"\s*\[ref=', line)
        if type_text_match:
            element_info['type'] = type_text_match.group(1)
            element_info['text'] = type_text_match.group(2)
            # 如果没有 role，从类型推断
            if 'role' not in element_info:
                element_info['role'] = type_text_match.group(1)
        
        # 提取 generic 后的文本
        # 格式: - generic [ref=e30]: Billing
        # 格式: - generic [ref=e6] [cursor=pointer]: "Username:"
        generic_text_match = re.search(r'- generic\s+\[ref=\w+\].*?:\s*(.+)$', line)
        if generic_text_match and not element_info.get('name'):
            element_info['name'] = generic_text_match.group(1).strip()
        
        # 提取 textbox 后的文本（输入框）
        # 格式: - textbox "Username" [ref=e123]:
        textbox_match = re.search(r'- textbox\s+"([^"]+)"\s*\[ref=', line)
        if textbox_match:
            element_info['type'] = 'textbox'
            element_info['text'] = textbox_match.group(1)
            element_info['role'] = 'textbox'
        
        # 提取 combobox 后的文本（下拉框）
        combobox_match = re.search(r'- combobox\s+"([^"]+)"\s*\[ref=', line)
        if combobox_match:
            element_info['type'] = 'combobox'
            element_info['text'] = combobox_match.group(1)
            element_info['role'] = 'combobox'
        
        # 提取 checkbox
        checkbox_match = re.search(r'- checkbox\s+"([^"]+)"\s*\[ref=', line)
        if checkbox_match:
            element_info['type'] = 'checkbox'
            element_info['text'] = checkbox_match.group(1)
            element_info['role'] = 'checkbox'
        
        # 提取 radio
        radio_match = re.search(r'- radio\s+"([^"]+)"\s*\[ref=', line)
        if radio_match:
            element_info['type'] = 'radio'
            element_info['text'] = radio_match.group(1)
            element_info['role'] = 'radio'
        
        # 提取 cursor=pointer（可点击元素）
        if '[cursor=pointer]' in line:
            element_info['clickable'] = True
        
        # 🚀 新增：处理 generic 类型的可点击元素
        # 格式: - generic [ref=e157] [cursor=pointer]:
        # 这种元素通常是自定义下拉框、按钮等，需要从兄弟元素获取标签
        if 'generic' in line and '[ref=' in line:
            element_info['type'] = 'generic'
            # 如果没有 role 但有 cursor=pointer，标记为可点击的 generic
            if 'role' not in element_info and '[cursor=pointer]' in line:
                element_info['role'] = 'generic_clickable'  # 自定义角色标识
        
        # 提取完整行内容（用于调试）
        element_info['raw_line'] = line.strip()
        
        return element_info if element_info else None
    
    def _parse_all_elements(self):
        """
        解析快照中的所有元素，更新元素列表和缓存
        
        增强功能：支持多种方式的隐式标签提取（兼容模式）
        
        标签提取策略（按优先级）：
        1. 直接属性：元素自身的 name, text, aria-label, placeholder
        2. 前一个兄弟元素：同一层级的前一个元素的文本
        3. 同行前缀文本：同一行中元素前面的文本（如 `- generic: "Username:" textbox`）
        4. 父级标签：通过缩进层级判断，父元素的文本
        5. 关联元素：查找附近有 label 关键字的元素
        
        支持的表单元素类型：textbox, combobox, checkbox, radio, listbox, spinbutton
        """
        self._all_elements = []
        
        if not self._current_snapshot:
            return
        
        # 第一步：按行解析所有元素，同时记录缩进层级
        lines = self._current_snapshot.split('\n')
        parsed_elements = []  # 临时存储：(line_index, indent_level, element_info)
        
        for i, line in enumerate(lines):
            if '[ref=' in line:
                element_info = self._parse_element_line(line)
                if element_info and element_info.get('ref'):
                    # 计算缩进层级（用于判断父子关系）
                    indent_level = len(line) - len(line.lstrip())
                    parsed_elements.append((i, indent_level, element_info))
        
        # 表单元素类型
        form_element_types = {'textbox', 'combobox', 'checkbox', 'radio', 'listbox', 'spinbutton'}
        
        # 第二步：为表单元素提取隐式标签（多策略兼容模式）
        for idx, (line_idx, indent_level, element_info) in enumerate(parsed_elements):
            elem_type = element_info.get('type', '')
            elem_role = element_info.get('role', '')
            raw_line = element_info.get('raw_line', '').lower()
            
            # 判断是否是表单元素（包括可点击的 generic 元素）
            is_form_element = (
                elem_type in form_element_types or 
                elem_role in form_element_types or
                elem_role == 'generic_clickable' or  # 🚀 新增：可点击的 generic 元素
                any(t in raw_line for t in ['textbox', 'combobox', 'checkbox', 'radio', 'input'])
            )
            
            # 如果已有直接的语义信息，跳过
            if element_info.get('name') or element_info.get('text'):
                self._all_elements.append(element_info)
                self._update_cache(element_info)
                continue
            
            # 为表单元素提取隐式标签
            if is_form_element:
                implicit_label = self._extract_implicit_label(
                    idx, line_idx, indent_level, parsed_elements, lines
                )
                if implicit_label:
                    element_info['implicit_label'] = implicit_label
                    logs.info(f"[SemanticSelectorMiddleware] 为 {element_info['ref']} 提取隐式标签: '{implicit_label}' (策略: {element_info.get('_label_strategy', 'unknown')})")
                    # 清理临时字段
                    element_info.pop('_label_strategy', None)
            
            # 添加到最终列表
            self._all_elements.append(element_info)
            self._update_cache(element_info)
        
        logs.info(f"[SemanticSelectorMiddleware] 解析到 {len(self._all_elements)} 个元素，缓存 {len(self._element_cache)} 个")
    
    def _update_cache(self, element_info: dict):
        """更新元素缓存"""
        ref = element_info.get('ref')
        if ref:
            if ref not in self._element_cache:
                self._element_cache[ref] = element_info
            else:
                self._element_cache[ref].update(element_info)
            # 🚀 P3-001: 缓存大小限制
            self._trim_caches()
    
    def _trim_caches(self):
        """
        P3-001: 当缓存超过限制时，移除最旧的条目
        """
        max_size = self._CACHE_MAX_SIZE
        for cache in [self._element_cache, self._snapshot_context_cache, 
                      self._ai_generated_code, self._html_element_attrs,
                      self._ref_to_html_attrs, self._xpath_to_js_attrs,
                      self._js_best_selector_map]:
            if len(cache) > max_size:
                # 移除最旧的条目（dict 保持插入顺序，Python 3.7+）
                excess = len(cache) - max_size
                keys_to_remove = list(cache.keys())[:excess]
                for key in keys_to_remove:
                    del cache[key]
    
    def _extract_implicit_label(self, idx: int, line_idx: int, indent_level: int, 
                                 parsed_elements: list, lines: list) -> Optional[str]:
        """
        从多种来源提取隐式标签（兼容模式）
        
        策略优先级：
        1. 前一个兄弟元素的文本
        2. 同行前面的文本
        3. 父级元素的文本（通过缩进判断）
        4. 附近包含 label 关键字的元素
        
        Args:
            idx: 当前元素在 parsed_elements 中的索引
            line_idx: 当前元素在原始行中的索引
            indent_level: 当前元素的缩进层级
            parsed_elements: 所有已解析元素的列表
            lines: 原始行列表
            
        Returns:
            提取到的标签文本，或 None
        """
        current_ref = parsed_elements[idx][2].get('ref', 'unknown')
        
        # 策略 1：前一个兄弟元素的文本
        if idx > 0:
            prev_line_idx, prev_indent, prev_element = parsed_elements[idx - 1]
            
            # 如果前一个元素在同一层级或父层级（缩进相近）
            if prev_indent >= indent_level - 2:
                prev_text = prev_element.get('name') or prev_element.get('text') or ''
                prev_ref = prev_element.get('ref', 'unknown')
                prev_raw = prev_element.get('raw_line', '')[:80]
                
                logs.debug(f"[SemanticSelectorMiddleware] 标签提取: {current_ref} 前元素 {prev_ref}, raw='{prev_raw}', name='{prev_text}'")
                
                prev_text = self._clean_label_text(prev_text)
                
                if prev_text and not self._is_form_element(prev_element):
                    element_info = parsed_elements[idx][2]
                    element_info['_label_strategy'] = 'prev_sibling'
                    logs.info(f"[SemanticSelectorMiddleware] ✅ 标签提取成功: {current_ref} -> '{prev_text}' (策略: prev_sibling)")
                    return prev_text
        
        # 策略 2：同行前面的文本（某些快照格式）
        current_line = lines[line_idx] if line_idx < len(lines) else ''
        label_in_line = self._extract_label_from_line(current_line)
        if label_in_line:
            element_info = parsed_elements[idx][2]
            element_info['_label_strategy'] = 'same_line'
            logs.info(f"[SemanticSelectorMiddleware] ✅ 标签提取成功: {current_ref} -> '{label_in_line}' (策略: same_line)")
            return label_in_line
        
        # 策略 3：父级元素的文本（通过缩进判断）
        for prev_idx in range(idx - 1, -1, -1):
            prev_line_idx, prev_indent, prev_element = parsed_elements[prev_idx]
            
            # 找到缩进更小的父级元素
            if prev_indent < indent_level - 2:
                parent_text = prev_element.get('name') or prev_element.get('text') or ''
                parent_text = self._clean_label_text(parent_text)
                
                if parent_text and not self._is_form_element(prev_element):
                    element_info = parsed_elements[idx][2]
                    element_info['_label_strategy'] = 'parent'
                    logs.info(f"[SemanticSelectorMiddleware] ✅ 标签提取成功: {current_ref} -> '{parent_text}' (策略: parent)")
                    return parent_text
                break  # 只找最近的父级
        
        # 策略 4：附近包含 label 关键字的元素
        for search_idx in range(max(0, idx - 3), min(len(parsed_elements), idx + 3)):
            if search_idx == idx:
                continue
            _, _, nearby_element = parsed_elements[search_idx]
            nearby_text = nearby_element.get('name') or nearby_element.get('text') or ''
            nearby_text_lower = nearby_text.lower()
            
            # 检查是否包含 label 相关关键字
            if any(kw in nearby_text_lower for kw in ['label', '标签', '名', 'name', 'user', 'pass', 'email', 'phone', '地址', '手机', '邮箱']):
                nearby_text = self._clean_label_text(nearby_text)
                if nearby_text:
                    element_info = parsed_elements[idx][2]
                    element_info['_label_strategy'] = 'nearby_keyword'
                    return nearby_text
        
        return None
    
    def _clean_label_text(self, text: str) -> str:
        """清理标签文本"""
        if not text:
            return ''
        # 去除引号包裹
        text = text.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]
        # 去除冒号、星号（必填标记）、多余空格
        text = text.strip()
        text = text.rstrip(':*').strip()
        text = text.rstrip('：*').strip()  # 中文冒号
        # 限制长度
        if len(text) > 50:
            return ''
        return text
    
    def _is_form_element(self, element_info: dict) -> bool:
        """判断是否是表单元素"""
        form_element_types = {'textbox', 'combobox', 'checkbox', 'radio', 'listbox', 'spinbutton'}
        elem_type = element_info.get('type', '')
        elem_role = element_info.get('role', '')
        raw_line = element_info.get('raw_line', '').lower()
        
        return (
            elem_type in form_element_types or 
            elem_role in form_element_types or
            any(t in raw_line for t in ['textbox', 'combobox', 'checkbox', 'radio', 'input', 'button'])
        )
    
    def _extract_label_from_line(self, line: str) -> Optional[str]:
        """从同行提取标签文本"""
        # 匹配模式：- element_type: "label text" textbox [ref=...]
        # 或：- generic: "Username:" textbox
        import re
        
        # 尝试匹配引号中的文本
        quote_match = re.search(r':\s*"([^"]+)"\s+(?:textbox|combobox|checkbox|radio|input)', line, re.IGNORECASE)
        if quote_match:
            return self._clean_label_text(quote_match.group(1))
        
        # 尝试匹配冒号后的文本
        colon_match = re.search(r':\s*([^\[\]]+?)\s+(?:textbox|combobox|checkbox|radio|input)', line, re.IGNORECASE)
        if colon_match:
            return self._clean_label_text(colon_match.group(1))
        
        return None
    
    def _find_similar_elements(self, element_description: str, threshold: float = 0.3) -> List[dict]:
        """
        在快照中搜索语义相似的元素
        
        使用多种匹配策略：
        1. 完全匹配：元素描述与 name/text 完全相同
        2. 包含匹配：元素描述包含 name/text，或反之
        3. 相似度匹配：使用文本相似度评分
        
        Args:
            element_description: 元素描述（如 "BNP-TWO-0123选项"）
            threshold: 相似度阈值（0-1）
            
        Returns:
            匹配的元素列表（按相似度降序）
        """
        if not element_description or not self._all_elements:
            return []
        
        matches = []
        desc_lower = element_description.lower().strip()
        
        for elem in self._all_elements:
            score = 0.0
            match_reason = []
            
            # 获取元素的各种文本属性
            name = elem.get('name', '').lower().strip()
            text = elem.get('text', '').lower().strip()
            elem_type = elem.get('type', '')
            role = elem.get('role', '')
            aria_label = elem.get('aria-label', '').lower().strip()
            placeholder = elem.get('placeholder', '').lower().strip()
            implicit_label = elem.get('implicit_label', '').lower().strip()  # 新增：隐式标签
            
            # 策略 1: 完全匹配
            if name == desc_lower or text == desc_lower or aria_label == desc_lower or implicit_label == desc_lower:
                score = 1.0
                match_reason.append("完全匹配")
            
            # 策略 2: 包含匹配
            elif name and (desc_lower in name or name in desc_lower):
                score = 0.8
                match_reason.append(f"包含匹配(name: {name})")
            elif text and (desc_lower in text or text in desc_lower):
                score = 0.8
                match_reason.append(f"包含匹配(text: {text})")
            elif aria_label and (desc_lower in aria_label or aria_label in desc_lower):
                score = 0.8
                match_reason.append(f"包含匹配(aria-label: {aria_label})")
            elif implicit_label and (desc_lower in implicit_label or implicit_label in desc_lower):
                score = 0.85  # 隐式标签匹配分数稍高
                match_reason.append(f"包含匹配(implicit_label: {implicit_label})")
            elif placeholder and (desc_lower in placeholder or placeholder in desc_lower):
                score = 0.75
                match_reason.append(f"包含匹配(placeholder: {placeholder})")
            
            # 策略 3: 词组匹配（分词后匹配）
            else:
                desc_words = set(desc_lower.split())
                name_words = set(name.split()) if name else set()
                text_words = set(text.split()) if text else set()
                aria_words = set(aria_label.split()) if aria_label else set()
                implicit_words = set(implicit_label.split()) if implicit_label else set()  # 新增
                
                # 计算词组重叠度
                if desc_words:
                    overlaps = []
                    if name_words:
                        overlaps.append(len(desc_words & name_words) / len(desc_words))
                    if text_words:
                        overlaps.append(len(desc_words & text_words) / len(desc_words))
                    if aria_words:
                        overlaps.append(len(desc_words & aria_words) / len(desc_words))
                    if implicit_words:
                        overlaps.append(len(desc_words & implicit_words) / len(desc_words))  # 新增
                    
                    if overlaps:
                        word_score = max(overlaps)
                        if word_score >= threshold:
                            score = word_score * 0.6
                            match_reason.append(f"词组匹配(重叠度: {word_score:.2f})")
            
            # 策略 4: 类型提示匹配
            type_keywords = {
                'button': ['button', '按钮', 'btn'],
                'link': ['link', '链接', 'a'],
                'textbox': ['textbox', 'input', '输入框', '文本框'],
                'combobox': ['combobox', 'select', '下拉', '选择框'],
                'checkbox': ['checkbox', '复选框', '勾选'],
                'radio': ['radio', '单选', '单选框'],
            }
            
            for kw_type, keywords in type_keywords.items():
                if any(kw in desc_lower for kw in keywords):
                    if elem_type == kw_type or role == kw_type:
                        score = max(score, 0.5)
                        match_reason.append(f"类型匹配({kw_type})")
                        break
            
            if score >= threshold:
                elem['match_score'] = score
                elem['match_reason'] = ', '.join(match_reason)
                matches.append(elem)
        
        # 按相似度降序排序
        matches.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        return matches
    
    def _generate_semantic_selector(self, element_info: dict, action: str, value: str = None) -> Optional[str]:
        """
        统一选择器生成入口（P1-002 重构）
        
        快速路径处理简单场景（JS 推荐、testid、button/link），
        复杂场景委托给候选排序路径 _generate_all_candidate_selectors。
        
        Args:
            element_info: 元素信息
            action: 动作类型
            value: 填充的值
            
        Returns:
            Playwright TypeScript 代码
        """
        # 转义单引号
        def escape(s):
            return s.replace("'", "\\'") if s else s
        
        # ====================================================================
        # 快速路径 1：JS 推荐选择器（score < 300 且唯一）
        # ====================================================================
        js_best_selector = element_info.get('_js_best_selector')
        js_score = element_info.get('_js_score', 999999)
        js_selector_reason = element_info.get('_js_selector_reason', '')
        js_unique = element_info.get('_js_unique')
        js_match_count = element_info.get('_js_match_count')
        
        if js_best_selector and js_score < 300:
            if js_unique is False:
                logs.warning(
                    f"[SemanticSelectorMiddleware] ⚠️ JS 推荐选择器非唯一 "
                    f"(score={js_score}, matches={js_match_count}): {js_best_selector}，降级到候选排序"
                )
            else:
                unique_mark = "✓唯一" if js_unique else ""
                logs.info(f"[SemanticSelectorMiddleware] 🎯 使用 JS 推荐选择器 (score={js_score}, reason={js_selector_reason}) {unique_mark}: {js_best_selector}")
                if action == 'click':
                    return f"await {js_best_selector}.click();"
                elif action == 'fill':
                    safe_value = escape(value) if value else ''
                    return f"await {js_best_selector}.fill('{safe_value}');"
                elif action == 'hover':
                    return f"await {js_best_selector}.hover();"
                elif action == 'select':
                    safe_value = escape(value) if value else ''
                    return f"await {js_best_selector}.selectOption('{safe_value}');"
        
        # ====================================================================
        # 快速路径 2：testid（最稳定的属性选择器）
        # ====================================================================
        testid = element_info.get('data-testid')
        if testid:
            return self._build_selector('getByTestId', testid, None, action, value)
        
        # ====================================================================
        # 快速路径 3：button/link + name（最常见的语义化场景）
        # ====================================================================
        role = element_info.get('role')
        name = element_info.get('name')
        text = element_info.get('text')
        hint_text = element_info.get('hint_text')
        
        if role in ['button', 'link'] and (name or text):
            safe_name = escape(name or text)
            return self._build_selector('getByRole', role, safe_name, action, value)
        
        # ====================================================================
        # 数据补充：从 JS 检测和 hint 补充缺失信息
        # ====================================================================
        implicit_label = element_info.get('implicit_label')
        
        # 从 JS label[for] 获取标签
        if not implicit_label and element_info.get('id'):
            js_label = self.get_js_label_for_input(element_info.get('id'))
            if js_label:
                implicit_label = js_label
                element_info['implicit_label'] = js_label
                logs.info(f"[SemanticSelectorMiddleware] 🎯 从 JS label[for] 获取标签: '{js_label}'")
        
        # 使用 hint_text 作为备用文本
        if not name and not text and hint_text:
            element_info['text'] = hint_text
            logs.info(f"[SemanticSelectorMiddleware] 使用 hint_text 作为备用: '{hint_text}'")
        
        # cursor:pointer 的 generic 可点击元素快速处理
        js_cursor_pointer = element_info.get('_js_cursor_pointer', False)
        if js_cursor_pointer and role == 'generic_clickable' and action in ['click', 'hover']:
            display_text = text or name or hint_text
            if display_text:
                safe_text = escape(display_text)
                logs.info(f"[SemanticSelectorMiddleware] 🎯 JS cursor:pointer 元素，使用 getByText: '{safe_text}'")
                return self._build_selector('getByText', safe_text, None, action, value)
        
        # ====================================================================
        # P1-002: 候选排序路径（统一处理所有复杂场景）
        # ====================================================================
        candidates = self._generate_all_candidate_selectors(element_info, action, value)
        
        if candidates:
            best_selector, best_score = candidates[0]
            # 分数 <= K_TEXT_SCORE（180）的候选直接使用
            if best_score <= K_TEXT_SCORE:
                logs.info(f"[SemanticSelectorMiddleware] ⚡ 候选排序最佳 (score={best_score}): {best_selector[:80]}")
                return best_selector
            
            # 分数较高但仍有候选，使用最佳候选
            logs.info(f"[SemanticSelectorMiddleware] 📊 候选排序最佳 (score={best_score}): {best_selector[:80]}")
            return best_selector
        
        # ====================================================================
        # 最后手段：hint_text + inferred_role
        # ====================================================================
        inferred_role = element_info.get('inferred_role')
        
        if hint_text and action in ['click', 'fill']:
            safe_hint = escape(hint_text)
            
            if inferred_role:
                if inferred_role in ['checkbox', 'radio', 'button', 'link']:
                    return self._build_selector('getByRole', inferred_role, safe_hint, action, value)
                elif inferred_role in ['textbox', 'combobox']:
                    return self._build_selector('getByLabel', safe_hint, None, action, value)
            
            if action == 'click':
                return f"await page.getByText('{safe_hint}', {{ exact: true }}).click();"
            elif action == 'fill':
                return f"await page.getByText('{safe_hint}', {{ exact: true }}).fill('{escape(value) if value else ''}');"
        
        return None
    
    def _build_selector(self, method: str, first_arg: str, second_arg: str, action: str, value: str = None) -> str:
        """
        构建选择器代码
        
        Args:
            method: 方法名（getByRole, getByTestId 等）
            first_arg: 第一个参数
            second_arg: 第二个参数（可选，如 name）
            action: 动作类型
            value: 填充的值
            
        Returns:
            Playwright TypeScript 代码
        """
        def escape(s):
            return s.replace("'", "\\'") if s else s
        
        # 构建定位器
        if method == 'getByRole':
            if second_arg:
                locator = f"page.getByRole('{first_arg}', {{ name: '{escape(second_arg)}' }})"
            else:
                locator = f"page.getByRole('{first_arg}')"
        elif method == 'getByTestId':
            locator = f"page.getByTestId('{first_arg}')"
        elif method == 'getByLabel':
            locator = f"page.getByLabel('{escape(first_arg)}')"
        elif method == 'getByPlaceholder':
            locator = f"page.getByPlaceholder('{escape(first_arg)}')"
        elif method == 'getByText':
            locator = f"page.getByText('{escape(first_arg)}')"
        else:
            return None
        
        # 构建操作
        if action == 'click':
            return f"await {locator}.click();"
        elif action == 'fill':
            safe_value = escape(value) if value else ''
            return f"await {locator}.fill('{safe_value}');"
        elif action == 'hover':
            return f"await {locator}.hover();"
        elif action == 'select':
            safe_value = escape(value) if value else ''
            return f"await {locator}.selectOption('{safe_value}');"
        
        return None
    
    def get_semantic_info(self, ref: str) -> Optional[dict]:
        """
        获取元素的语义信息（供其他中间件调用）
        
        优先从缓存获取，其次从快照解析。
        
        Args:
            ref: 元素引用
            
        Returns:
            元素语义信息
        """
        # 优先从缓存获取
        if ref in self._element_cache:
            return self._element_cache[ref]
        
        # 从快照解析
        return self._parse_element_from_snapshot(ref)
    
    def _parse_element_hint(self, hint: str) -> dict:
        """
        智能解析元素提示文本，提取元素类型和标签文本
        
        支持的中文元素类型关键词：
        - 复选框 → role: checkbox
        - 按钮 → role: button  
        - 下拉框/选择框 → role: combobox
        - 输入框/文本框 → role: textbox
        - 单选框 → role: radio
        - 链接 → role: link
        
        Args:
            hint: 元素提示文本（如 "数据行的复选框"、"提交按钮"）
            
        Returns:
            {
                'inferred_role': 推断的 role（如 'checkbox'）,
                'label_text': 提取的标签文本（如 "数据行的"）,
                'original_hint': 原始 hint,
                'element_type_cn': 中文元素类型（如 "复选框"）
            }
        """
        if not hint:
            return {'inferred_role': None, 'label_text': hint, 'original_hint': hint, 'element_type_cn': None}
        
        # 元素类型映射（按优先级排序，长的在前避免误匹配）
        element_type_map = [
            # 复选框相关
            ('复选框', 'checkbox'),
            ('勾选框', 'checkbox'),
            ('checkbox', 'checkbox'),
            
            # 下拉框相关
            ('下拉选择框', 'combobox'),
            ('下拉框', 'combobox'),
            ('选择框', 'combobox'),
            ('下拉列表', 'combobox'),
            ('combobox', 'combobox'),
            ('select', 'combobox'),
            
            # 按钮相关
            ('按钮', 'button'),
            ('button', 'button'),
            ('btn', 'button'),
            
            # 输入框相关
            ('输入框', 'textbox'),
            ('文本框', 'textbox'),
            ('搜索框', 'textbox'),
            ('textbox', 'textbox'),
            ('input', 'textbox'),
            
            # 单选框相关
            ('单选框', 'radio'),
            ('radio', 'radio'),
            
            # 链接相关
            ('链接', 'link'),
            ('link', 'link'),
        ]
        
        hint_lower = hint.lower()
        inferred_role = None
        element_type_cn = None
        label_text = hint
        
        # 查找匹配的元素类型
        for type_keyword, role in element_type_map:
            # 检查是否包含该关键词（不区分大小写）
            if type_keyword.lower() in hint_lower:
                inferred_role = role
                element_type_cn = type_keyword
                
                # 提取标签文本：删除元素类型关键词
                # 使用正则替换，确保只删除完整的关键词
                import re
                pattern = re.compile(re.escape(type_keyword), re.IGNORECASE)
                label_text = pattern.sub('', hint).strip()
                
                # 清理残留的空白和标点
                label_text = label_text.strip(' \t\n\r，。、：: ')
                
                logs.info(f"[SemanticSelectorMiddleware] 🧠 hint 解析: '{hint}' → role={role}, label='{label_text}'")
                break
        
        return {
            'inferred_role': inferred_role,
            'label_text': label_text if label_text else hint,
            'original_hint': hint,
            'element_type_cn': element_type_cn
        }
    
    def get_semantic_code(self, ref: str, action: str, value: str = None, element_hint: str = None) -> Optional[str]:
        """
        获取语义化代码（供其他中间件调用）
        
        优先从缓存获取语义信息，支持双阶段代码生成。
        
        Args:
            ref: 元素引用
            action: 动作类型
            value: 填充的值
            element_hint: 元素描述提示（如 "Save Changes按钮"），用于备用选择器生成
            
        Returns:
            Playwright TypeScript 代码
        """
        element_info = self.get_semantic_info(ref)
        
        # 🚀 增强：如果 element_hint 存在，智能解析并补充信息
        if element_info and element_hint:
            parsed_hint = self._parse_element_hint(element_hint)
            
            # 如果快照中没有 name 或 text，使用解析后的 label_text
            if not element_info.get('name') and not element_info.get('text'):
                element_info['hint_text'] = parsed_hint['label_text']
                logs.info(f"[SemanticSelectorMiddleware] 🎯 使用 element_hint 作为备用文本: '{parsed_hint['label_text']}' for ref={ref}")
            
            # 如果快照中没有 role，使用解析后的 inferred_role
            if not element_info.get('role') and parsed_hint['inferred_role']:
                element_info['inferred_role'] = parsed_hint['inferred_role']
                logs.info(f"[SemanticSelectorMiddleware] 🎯 使用 element_hint 推断 role: '{parsed_hint['inferred_role']}' for ref={ref}")
        
        if element_info:
            code = self._generate_semantic_selector(element_info, action, value)
            if code:
                self._selector_stats['semantic'] += 1
                logs.info(f"[SemanticSelectorMiddleware] 生成语义化选择器: {code[:80]}...")
                return code
        
        # 无法生成语义化选择器
        self._selector_stats['ref'] += 1
        return None
    
    def update_snapshot(self, snapshot: str, raw_html: str = None, js_detection_result: dict = None):
        """
        更新当前快照和原始 HTML
        
        Args:
            snapshot: 页面快照内容（清理后的）
            raw_html: 原始 HTML 内容（用于判断 label for 关联）
            js_detection_result: JS 注入检测结果（🚀 新增，可选）
        """
        if snapshot and '### Snapshot' in snapshot:
            # 提取 Snapshot 部分
            match = re.search(r'### Snapshot\s*```yaml\s*(.+?)\s*```', snapshot, re.DOTALL)
            if match:
                self._current_snapshot = match.group(1)
                self._snapshot_age = 0  # 重置快照年龄
                # 解析所有元素并更新缓存
                self._parse_all_elements()
                logs.info(f"[SemanticSelectorMiddleware] 快照已更新，长度: {len(self._current_snapshot)}，元素数: {len(self._all_elements)}")
        
        # 🆕 解析原始 HTML，提取 label for 关联
        if raw_html:
            self._raw_html_cache = raw_html
            self._parse_label_for_associations(raw_html)
        
        # 🚀🆕 处理 JS 注入检测结果
        if js_detection_result:
            self.process_js_detection_result(js_detection_result)
    
    def _parse_label_for_associations(self, html: str):
        """
        从原始 HTML 中解析 label for 关联和所有元素属性
        
        提取：
        1. <label for="inputId">Label Text</label> → _label_for_cache
        2. 所有交互元素（input, button, a, select, textarea）的属性
        3. 建立元素签名 → 属性的映射
        
        Args:
            html: 原始 HTML 内容
        """
        self._label_for_cache = {}
        self._html_element_attrs = {}
        
        if not html:
            return
        
        try:
            # ========== 1. 提取 label for 关联 ==========
            label_pattern = r'<label\s+[^>]*for\s*=\s*["\']([^"\']+)["\'][^>]*>([^<]*)</label>'
            
            for match in re.finditer(label_pattern, html, re.IGNORECASE):
                input_id = match.group(1)
                label_text = match.group(2).strip()
                
                # 清理 label 文本
                label_text = label_text.strip().rstrip(':*').strip()
                
                if input_id and label_text:
                    self._label_for_cache[input_id] = label_text
                    logs.debug(f"[SemanticSelectorMiddleware] 发现 label for 关联: for='{input_id}' -> '{label_text}'")
            
            logs.info(f"[SemanticSelectorMiddleware] 解析到 {len(self._label_for_cache)} 个 label for 关联")
            
            # ========== 2. 提取所有交互元素属性 ==========
            # 定义要提取的元素类型
            element_patterns = [
                # input 元素
                (r'<input\s+([^>]*)/?>', 'input'),
                # button 元素
                (r'<button\s+([^>]*)>([^<]*)</button>', 'button'),
                # a 元素
                (r'<a\s+([^>]*)>([^<]*)</a>', 'link'),
                # select 元素
                (r'<select\s+([^>]*)>', 'select'),
                # textarea 元素
                (r'<textarea\s+([^>]*)>', 'textarea'),
            ]
            
            element_index = 0  # 元素索引，用于生成签名
            
            for pattern, elem_type in element_patterns:
                for match in re.finditer(pattern, html, re.IGNORECASE):
                    attrs_str = match.group(1)
                    text_content = match.group(2) if len(match.groups()) > 1 else ""
                    
                    # 提取属性
                    attrs = self._extract_html_attributes(attrs_str, elem_type, text_content)
                    
                    if attrs:
                        # 生成元素签名（用于关联快照中的 ref）
                        signature = self._generate_element_signature(attrs, elem_type, element_index)
                        attrs['_signature'] = signature
                        attrs['_index'] = element_index
                        attrs['_type'] = elem_type
                        
                        self._html_element_attrs[signature] = attrs
                        element_index += 1
            
            logs.info(f"[SemanticSelectorMiddleware] 解析到 {len(self._html_element_attrs)} 个 HTML 元素属性")
            
            # ========== 3. 建立 ref → HTML 属性映射 ==========
            self._build_ref_to_html_mapping()
            
        except Exception as e:
            logs.warning(f"[SemanticSelectorMiddleware] 解析 HTML 失败: {e}")
    
    def _extract_html_attributes(self, attrs_str: str, elem_type: str, text_content: str = "") -> dict:
        """
        从 HTML 属性字符串中提取属性
        
        提取的属性：
        - id: 元素 ID
        - name: 元素 name
        - type: 输入类型
        - class: CSS 类名
        - placeholder: 占位符
        - data-*: data 属性
        - aria-*: ARIA 属性
        - value: 默认值
        - href: 链接地址
        
        Args:
            attrs_str: 属性字符串（如 'id="username" name="user" class="form-control"'）
            elem_type: 元素类型
            text_content: 文本内容（button, a 元素）
            
        Returns:
            属性字典
        """
        attrs = {}
        
        # 提取常见属性
        attr_patterns = [
            ('id', r'id\s*=\s*["\']([^"\']+)["\']'),
            ('name', r'name\s*=\s*["\']([^"\']+)["\']'),
            ('type', r'type\s*=\s*["\']([^"\']+)["\']'),
            ('class', r'class\s*=\s*["\']([^"\']+)["\']'),
            ('placeholder', r'placeholder\s*=\s*["\']([^"\']+)["\']'),
            ('value', r'value\s*=\s*["\']([^"\']+)["\']'),
            ('href', r'href\s*=\s*["\']([^"\']+)["\']'),
            ('title', r'title\s*=\s*["\']([^"\']+)["\']'),
            ('alt', r'alt\s*=\s*["\']([^"\']+)["\']'),
            ('role', r'role\s*=\s*["\']([^"\']+)["\']'),
        ]
        
        for attr_name, pattern in attr_patterns:
            match = re.search(pattern, attrs_str, re.IGNORECASE)
            if match:
                attrs[attr_name] = match.group(1)
        
        # 提取 data-* 属性
        for match in re.finditer(r'data-([\w-]+)\s*=\s*["\']([^"\']+)["\']', attrs_str, re.IGNORECASE):
            data_attr = f"data-{match.group(1)}"
            attrs[data_attr] = match.group(2)
        
        # 提取 aria-* 属性
        for match in re.finditer(r'aria-([\w-]+)\s*=\s*["\']([^"\']+)["\']', attrs_str, re.IGNORECASE):
            aria_attr = f"aria-{match.group(1)}"
            attrs[aria_attr] = match.group(2)
        
        # 添加文本内容
        if text_content:
            attrs['_text'] = text_content.strip()
        
        return attrs
    
    def _generate_element_signature(self, attrs: dict, elem_type: str, index: int) -> str:
        """
        生成元素签名（用于关联快照中的 ref）
        
        签名规则：
        1. 有 id: 使用 id
        2. 有 name: 使用 type + name
        3. 有 placeholder: 使用 type + placeholder
        4. 有 data-testid: 使用 data-testid
        5. 其他: 使用 type + index
        
        Args:
            attrs: 元素属性
            elem_type: 元素类型
            index: 元素索引
            
        Returns:
            元素签名
        """
        if attrs.get('id'):
            return f"#{attrs['id']}"
        elif attrs.get('data-testid'):
            return f"[data-testid={attrs['data-testid']}]"
        elif attrs.get('name'):
            return f"{elem_type}[name={attrs['name']}]"
        elif attrs.get('placeholder'):
            return f"{elem_type}[placeholder={attrs['placeholder'][:20]}]"
        else:
            return f"{elem_type}[{index}]"
    
    def _build_ref_to_html_mapping(self):
        """
        建立 ref → HTML 属性映射
        
        通过以下方式关联：
        1. 精确匹配：id, name, data-testid
        2. 类型+位置匹配：按相同类型元素的顺序
        3. 文本匹配：button, a 元素的文本内容
        """
        self._ref_to_html_attrs = {}
        
        if not self._all_elements or not self._html_element_attrs:
            return
        
        # 按类型分组快照元素和 HTML 元素
        snapshot_by_type: Dict[str, List[dict]] = {}
        for elem in self._all_elements:
            elem_type = elem.get('type', elem.get('role', 'unknown'))
            if elem_type not in snapshot_by_type:
                snapshot_by_type[elem_type] = []
            snapshot_by_type[elem_type].append(elem)
        
        html_by_type: Dict[str, List[dict]] = {}
        for signature, attrs in self._html_element_attrs.items():
            elem_type = attrs.get('_type', 'unknown')
            # 映射 HTML 类型到快照类型
            type_mapping = {
                'input': 'textbox',
                'button': 'button',
                'link': 'link',
                'select': 'combobox',
                'textarea': 'textbox',
            }
            snapshot_type = type_mapping.get(elem_type, elem_type)
            if snapshot_type not in html_by_type:
                html_by_type[snapshot_type] = []
            html_by_type[snapshot_type].append(attrs)
        
        # 建立映射
        for elem_type, snapshot_elems in snapshot_by_type.items():
            html_elems = html_by_type.get(elem_type, [])
            
            if not html_elems:
                continue
            
            # 按索引顺序匹配
            for i, snapshot_elem in enumerate(snapshot_elems):
                ref = snapshot_elem.get('ref')
                if not ref:
                    continue
                
                # 尝试精确匹配
                matched = False
                
                # 1. 尝试通过 id 匹配
                snapshot_id = snapshot_elem.get('id')
                if snapshot_id:
                    for html_elem in html_elems:
                        if html_elem.get('id') == snapshot_id:
                            self._ref_to_html_attrs[ref] = html_elem
                            matched = True
                            logs.debug(f"[SemanticSelectorMiddleware] 精确匹配(ref={ref}): id={snapshot_id}")
                            break
                
                if matched:
                    continue
                
                # 2. 尝试通过 name 匹配
                snapshot_name = snapshot_elem.get('name')
                if snapshot_name:
                    for html_elem in html_elems:
                        if html_elem.get('name') == snapshot_name:
                            self._ref_to_html_attrs[ref] = html_elem
                            matched = True
                            logs.debug(f"[SemanticSelectorMiddleware] 精确匹配(ref={ref}): name={snapshot_name}")
                            break
                
                if matched:
                    continue
                
                # 3. 尝试通过 data-testid 匹配
                snapshot_testid = snapshot_elem.get('data-testid')
                if snapshot_testid:
                    for html_elem in html_elems:
                        if html_elem.get('data-testid') == snapshot_testid:
                            self._ref_to_html_attrs[ref] = html_elem
                            matched = True
                            logs.debug(f"[SemanticSelectorMiddleware] 精确匹配(ref={ref}): data-testid={snapshot_testid}")
                            break
                
                if matched:
                    continue
                
                # 4. 按索引位置匹配（兜底）+ 🚀 P1-005: 文本交叉验证
                if i < len(html_elems):
                    html_elem = html_elems[i]
                    
                    # 交叉验证：快照元素的文本/name 与 HTML 元素的文本/placeholder 是否匹配
                    snapshot_text = (snapshot_elem.get('name') or snapshot_elem.get('text') or '').lower().strip()
                    html_text = (html_elem.get('placeholder') or html_elem.get('_text') or '').lower().strip()
                    
                    # 至少有一个文本字段匹配，或者两者都为空（纯结构匹配）
                    if (not snapshot_text and not html_text) or \
                       (snapshot_text and html_text and (
                           snapshot_text in html_text or html_text in snapshot_text
                       )):
                        self._ref_to_html_attrs[ref] = html_elem
                        logs.debug(f"[SemanticSelectorMiddleware] 位置匹配+文本验证(ref={ref}): index={i}")
                    else:
                        logs.debug(f"[SemanticSelectorMiddleware] 位置匹配失败(ref={ref}): "
                                     f"快照文本='{snapshot_text[:30]}' vs HTML文本='{html_text[:30]}'，跳过")
        
        logs.info(f"[SemanticSelectorMiddleware] 建立 {len(self._ref_to_html_attrs)} 个 ref→HTML 属性映射")
    
    def get_html_attrs_for_ref(self, ref: str) -> Optional[dict]:
        """
        获取 ref 对应的 HTML 属性
        
        Args:
            ref: 元素引用
            
        Returns:
            HTML 属性字典，不存在返回 None
        """
        return self._ref_to_html_attrs.get(ref)
    
    # ========================================================================
    # 🚀 新增：JS 注入检测增强功能
    # ========================================================================
    
    # JS 注入检测脚本：检测页面上所有可交互元素
    JS_INTERACTIVE_DETECTOR = '''
    (() => {
        const results = [];
        let refCounter = 1;
        
        // 🚀 增强：选择器评分常量（从 Python 端动态注入，确保一致性）
        // __SCORES_INJECTED_FROM_PYTHON__
        
        // 可交互元素选择器
        const interactiveSelectors = [
            'button', 'a[href]', 'input', 'select', 'textarea',
            '[role="button"]', '[role="link"]', '[role="textbox"]',
            '[role="checkbox"]', '[role="radio"]', '[role="combobox"]',
            '[role="listbox"]', '[role="menuitem"]', '[role="tab"]',
            '[tabindex]:not([tabindex="-1"])',
            '[onclick]', '[data-testid]', '[aria-label]',
            'label[for]'
        ];
        
        // 获取所有可交互元素
        const interactiveElements = new Set();
        
        // 1. 通过选择器获取
        interactiveSelectors.forEach(sel => {
            try {
                document.querySelectorAll(sel).forEach(el => interactiveElements.add(el));
            } catch (e) {}
        });
        
        // 2. 通过 cursor:pointer 检测（限制遍历范围，避免全量 querySelectorAll('*')）
        const clickableCandidates = [
            'div[class*="btn"]', 'div[class*="click"]', 'div[class*="link"]',
            'div[class*="item"]', 'div[class*="option"]', 'div[class*="menu"]',
            'div[class*="tab"]', 'div[class*="tag"]', 'div[class*="card"]',
            'span[class*="btn"]', 'span[class*="icon"]', 'span[class*="link"]',
            'li', 'td', 'th', 'img', 'svg', 'i',
            '[style*="cursor"]',
            '[role]'
        ].join(', ');
        try {
            document.querySelectorAll(clickableCandidates).forEach(el => {
                if (!interactiveElements.has(el)) {
                    try {
                        const cursor = window.getComputedStyle(el).cursor;
                        if (cursor === 'pointer' || cursor === 'hand') {
                            interactiveElements.add(el);
                        }
                    } catch(e) {}
                }
            });
        } catch(e) {}
        
        // 辅助函数：生成元素的唯一标识 xpath
        function getElementXPath(element) {
            if (element.id) {
                return '//*[@id="' + element.id + '"]';
            }
            
            const parts = [];
            let current = element;
            
            while (current && current.nodeType === Node.ELEMENT_NODE) {
                let index = 1;
                let sibling = current.previousSibling;
                
                while (sibling) {
                    if (sibling.nodeType === Node.ELEMENT_NODE && sibling.tagName === current.tagName) {
                        index++;
                    }
                    sibling = sibling.previousSibling;
                }
                
                const tagName = current.tagName.toLowerCase();
                const indexStr = index > 1 ? '[' + index + ']' : '';
                parts.unshift(tagName + indexStr);
                current = current.parentNode;
            }
            
            return '/' + parts.join('/');
        }
        
        // 🚀 新增：判断 ID 是否是动态生成的
        function isDynamicId(id) {
            if (!id) return true;
            // React/Aria 动态 ID：:r1:, :r2a:
            if (/^:r\\d+[a-z]?:$/.test(id)) return true;
            // 长随机字符串
            if (/^[a-f0-9]{8,}$/i.test(id)) return true;
            // 包含长数字序列
            if (/\\d{6,}/.test(id)) return true;
            // 以数字开头
            if (/^\\d/.test(id)) return true;
            return false;
        }
        
        // 🚀 唯一性验证：检查选择器在页面上是否唯一匹配
        // 非唯一选择器会被大幅降低优先级（+5000 分），匹配不到的更差（+10000 分）
        function verifyUniqueness(candidate, el) {
            try {
                let matchCount = null;
                const code = candidate.code;
                
                // CSS 选择器验证：通过 querySelectorAll 计数
                if (code.includes("locator('#")) {
                    const idMatch = code.match(/#([^'")]+)/);
                    if (idMatch) {
                        try { matchCount = document.querySelectorAll('#' + CSS.escape(idMatch[1])).length; } catch(e) {}
                    }
                }
                else if (code.includes("[name=")) {
                    const nameMatch = code.match(/name="([^"]+)"/);
                    if (nameMatch) matchCount = document.querySelectorAll('[name="' + nameMatch[1] + '"]').length;
                }
                else if (code.includes("getByTestId")) {
                    const testidMatch = code.match(/getByTestId\\('([^']+)'\\)/);
                    if (testidMatch) matchCount = document.querySelectorAll('[data-testid="' + testidMatch[1] + '"]').length;
                }
                // getByRole 近似验证
                else if (code.includes("getByRole")) {
                    const roleMatch = code.match(/getByRole\\('(\\w+)'/);
                    const nameMatch = code.match(/name:\\s*'([^']+)'/);
                    if (roleMatch) {
                        const role = roleMatch[1];
                        // 收集所有匹配 role 的元素（显式 role + 隐式 role）
                        const tagRoleMap = { button: 'button', a: 'link', input: 'textbox', select: 'combobox', textarea: 'textbox' };
                        const roleEls = [...document.querySelectorAll('[role="' + role + '"]')];
                        Object.entries(tagRoleMap).forEach(([tag, r]) => {
                            if (r === role) {
                                document.querySelectorAll(tag).forEach(e => {
                                    if (!e.getAttribute('role') || e.getAttribute('role') === role) roleEls.push(e);
                                });
                            }
                        });
                        const uniqueEls = [...new Set(roleEls)];
                        
                        if (nameMatch) {
                            const searchName = nameMatch[1];
                            matchCount = uniqueEls.filter(e => {
                                const t = (e.textContent || '').trim();
                                const a = e.getAttribute('aria-label') || '';
                                return t.includes(searchName) || a.includes(searchName);
                            }).length;
                        } else {
                            matchCount = uniqueEls.length;
                        }
                    }
                }
                // getByText 近似验证
                else if (code.includes("getByText")) {
                    const textMatch = code.match(/getByText\\('([^']+)'\\)/);
                    if (textMatch) {
                        const searchText = textMatch[1];
                        // 遍历文本节点计数（近似 Playwright 的 hasText 匹配）
                        const allElements = document.querySelectorAll('*');
                        let count = 0;
                        allElements.forEach(e => {
                            // 只检查直接文本内容（不含子元素），模拟 Playwright 的行为
                            const directText = Array.from(e.childNodes)
                                .filter(n => n.nodeType === Node.TEXT_NODE)
                                .map(n => n.textContent.trim())
                                .join('');
                            if (directText.includes(searchText)) count++;
                        });
                        // 如果直接文本匹配太少，回退到 textContent 匹配
                        if (count === 0) {
                            allElements.forEach(e => {
                                if ((e.textContent || '').trim() === searchText) count++;
                            });
                        }
                        matchCount = count;
                    }
                }
                // getByPlaceholder 验证
                else if (code.includes("getByPlaceholder")) {
                    const phMatch = code.match(/getByPlaceholder\\('([^']+)'\\)/);
                    if (phMatch) matchCount = document.querySelectorAll('[placeholder="' + phMatch[1] + '"]').length;
                }
                // getByLabel 验证（近似：检查 label[for] 指向的元素数）
                else if (code.includes("getByLabel")) {
                    const labelMatch = code.match(/getByLabel\\('([^']+)'\\)/);
                    if (labelMatch) {
                        const labelText = labelMatch[1];
                        const labels = [...document.querySelectorAll('label')].filter(l => 
                            (l.textContent || '').trim().includes(labelText)
                        );
                        matchCount = labels.length > 0 ? labels.length : null;
                    }
                }
                
                if (matchCount !== null) {
                    candidate.unique = matchCount === 1;
                    candidate.matchCount = matchCount;
                    // 非唯一选择器大幅降低优先级
                    if (matchCount > 1) {
                        candidate.score += 5000;
                        candidate.reason += ' [NOT UNIQUE: ' + matchCount + ' matches]';
                    } else if (matchCount === 0) {
                        candidate.score += 10000;
                        candidate.reason += ' [NO MATCH]';
                    } else {
                        candidate.reason += ' [UNIQUE]';
                    }
                }
            } catch(e) {
                // 验证失败不影响候选，保持原始分数
            }
        }
        
        // 🚀 新增：生成 Playwright 选择器（带评分）
        function generatePlaywrightSelector(info, el) {
            const candidates = [];
            
            // 1. data-testid（最优）
            if (info.dataTestid) {
                candidates.push({
                    type: 'getByTestId',
                    code: `page.getByTestId('${info.dataTestid}')`,
                    score: SCORE.TEST_ID,
                    reason: 'data-testid attribute'
                });
            }
            
            // 2. data-test, data-test-id（次优）
            const dataTest = el.getAttribute('data-test') || el.getAttribute('data-test-id');
            if (dataTest && !info.dataTestid) {
                candidates.push({
                    type: 'getByTestId',
                    code: `page.getByTestId('${dataTest}')`,
                    score: SCORE.OTHER_TEST_ID,
                    reason: 'data-test attribute'
                });
            }
            
            // 3. role + name（语义化，推荐）
            const inferredRole = info.role || inferRoleFromTag(el);
            const name = info.ariaLabel || info.text || info.title;
            if (inferredRole && name && name.length <= 80) {
                candidates.push({
                    type: 'getByRole',
                    code: `page.getByRole('${inferredRole}', { name: '${escapeString(name.substring(0, 50))}' })`,
                    score: SCORE.ROLE_WITH_NAME,
                    reason: 'role + name'
                });
            }
            
            // 4. aria-label
            if (info.ariaLabel && !name) {
                candidates.push({
                    type: 'getByLabel',
                    code: `page.getByLabel('${escapeString(info.ariaLabel)}')`,
                    score: SCORE.ARIA_LABEL,
                    reason: 'aria-label attribute'
                });
            }
            
            // 5. placeholder
            if (info.placeholder) {
                candidates.push({
                    type: 'getByPlaceholder',
                    code: `page.getByPlaceholder('${escapeString(info.placeholder)}')`,
                    score: SCORE.PLACEHOLDER,
                    reason: 'placeholder attribute'
                });
            }
            
            // 6. aria-labelledby 关联（通过 ID 查找关联元素的文本）
            if (info.ariaLabelledby) {
                const ids = info.ariaLabelledby.split(/\\s+/);
                const labelParts = [];
                for (const id of ids) {
                    const labelEl = document.getElementById(id);
                    if (labelEl) {
                        const text = (labelEl.textContent || '').trim();
                        if (text) labelParts.push(text);
                    }
                }
                const labelText = labelParts.join(' ');
                if (labelText && labelText.length <= 80) {
                    candidates.push({
                        type: 'getByLabel',
                        code: `page.getByLabel('${escapeString(labelText)}')`,
                        score: SCORE.LABEL,
                        reason: 'aria-labelledby association'
                    });
                }
            }
            
            // 7. 关联的 label（通过 label[for]）
            // 这个需要在主函数中处理
            
            // 8. name 属性
            if (info.name) {
                candidates.push({
                    type: 'locator',
                    code: `page.locator('[name="${info.name}"]')`,
                    score: SCORE.CSS_NAME,
                    reason: 'name attribute'
                });
            }
            
            // 8. 稳定的 ID
            if (info.id && !isDynamicId(info.id)) {
                candidates.push({
                    type: 'locator',
                    code: `page.locator('#${info.id}')`,
                    score: SCORE.CSS_ID,
                    reason: 'stable id'
                });
            }
            
            // 9. text（兜底）
            if (info.text && info.text.length >= 2 && info.text.length <= 50) {
                candidates.push({
                    type: 'getByText',
                    code: `page.getByText('${escapeString(info.text)}')`,
                    score: SCORE.TEXT,
                    reason: 'text content'
                });
            }
            
            // 🚀 唯一性验证：在排序前验证每个候选在页面上是否唯一匹配
            candidates.forEach(c => verifyUniqueness(c, el));
            
            // 按评分排序，返回最佳选择器
            candidates.sort((a, b) => a.score - b.score);
            return candidates;
        }
        
        // 辅助函数：从标签推断 role
        function inferRoleFromTag(el) {
            const tag = el.tagName.toLowerCase();
            const type = el.getAttribute('type');
            
            const roleMap = {
                'button': 'button',
                'a': 'link',
                'input': type === 'checkbox' ? 'checkbox' : 
                         type === 'radio' ? 'radio' : 
                         type === 'submit' ? 'button' : 'textbox',
                'select': 'combobox',
                'textarea': 'textbox'
            };
            
            return el.getAttribute('role') || roleMap[tag] || null;
        }
        
        // 辅助函数：转义字符串
        function escapeString(str) {
            if (!str) return '';
            return str.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'").replace(/\\n/g, '\\\\n');
        }
        
        // 辅助函数：检查元素是否可见
        function isElementVisible(el) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' && 
                   style.visibility !== 'hidden' && 
                   style.opacity !== '0' &&
                   rect.width > 0 && 
                   rect.height > 0;
        }
        
        // 辅助函数：提取元素属性
        function extractElementInfo(el) {
            const info = {
                ref: 'e' + refCounter++,
                tagName: el.tagName.toLowerCase(),
                xpath: getElementXPath(el),
                id: el.id || null,
                name: el.getAttribute('name'),
                className: el.className && typeof el.className === 'string' ? el.className : null,
                type: el.getAttribute('type'),
                role: el.getAttribute('role'),
                ariaLabel: el.getAttribute('aria-label'),
                ariaLabelledby: el.getAttribute('aria-labelledby'),
                placeholder: el.getAttribute('placeholder'),
                dataTestid: el.getAttribute('data-testid'),
                title: el.getAttribute('title'),
                alt: el.getAttribute('alt'),
                href: el.getAttribute('href'),
                value: el.value || el.getAttribute('value'),
                tabIndex: el.tabIndex,
                disabled: el.disabled,
                checked: el.checked,
                text: (el.innerText || el.textContent || '').substring(0, 100).trim(),
                hasOnClick: el.onclick !== null || el.hasAttribute('onclick'),
                cursorPointer: window.getComputedStyle(el).cursor === 'pointer',
                isInteractive: true,
                isVisible: isElementVisible(el),
                // 额外属性
                htmlFor: el.getAttribute('for'),  // label 的 for 属性
                form: el.getAttribute('form'),
                autocomplete: el.getAttribute('autocomplete'),
                required: el.required || el.hasAttribute('required'),
                readonly: el.readOnly || el.hasAttribute('readonly')
            };
            
            // 🚀 新增：生成选择器候选列表
            info.selectorCandidates = generatePlaywrightSelector(info, el);
            
            // 🚀 新增：最佳选择器
            if (info.selectorCandidates.length > 0) {
                info.bestSelector = info.selectorCandidates[0];
            }
            
            return info;
        }
        
        // 🎨 视觉高亮样式注入
        const HIGHLIGHT_COLORS = {
            button:   { outline: '2px solid #FF4444', bg: 'rgba(255,68,68,0.08)' },   // 红色 - 按钮
            link:     { outline: '2px solid #4488FF', bg: 'rgba(68,136,255,0.08)' },   // 蓝色 - 链接
            textbox:  { outline: '2px solid #44BB44', bg: 'rgba(68,187,68,0.08)' },    // 绿色 - 输入框
            combobox: { outline: '2px solid #FF8800', bg: 'rgba(255,136,0,0.08)' },    // 橙色 - 下拉框
            checkbox: { outline: '2px solid #AA44FF', bg: 'rgba(170,68,255,0.08)' },   // 紫色 - 复选框
            radio:    { outline: '2px solid #AA44FF', bg: 'rgba(170,68,255,0.08)' },   // 紫色 - 单选框
            default:  { outline: '2px solid #FF4444', bg: 'rgba(255,68,68,0.08)' }     // 默认红色
        };
        
        // 清除上一次的高亮（如果有）
        document.querySelectorAll('[data-kiro-highlight]').forEach(el => {
            el.style.outline = el.dataset.kiroOriginalOutline || '';
            el.style.backgroundColor = el.dataset.kiroOriginalBg || '';
            el.removeAttribute('data-kiro-highlight');
            el.removeAttribute('data-kiro-original-outline');
            el.removeAttribute('data-kiro-original-bg');
        });
        
        let highlightedCount = 0;
        let uniqueCount = 0;
        let nonUniqueCount = 0;
        const typeCounts = {};
        
        // 提取所有元素信息
        interactiveElements.forEach(el => {
            try {
                const info = extractElementInfo(el);
                results.push(info);
                
                // 🎨 视觉高亮：仅对可见元素添加
                if (info.isVisible) {
                    const role = info.role || inferRoleFromTag(el);
                    const colors = HIGHLIGHT_COLORS[role] || HIGHLIGHT_COLORS.default;
                    
                    // 保存原始样式
                    el.dataset.kiroOriginalOutline = el.style.outline || '';
                    el.dataset.kiroOriginalBg = el.style.backgroundColor || '';
                    el.dataset.kiroHighlight = role || 'interactive';
                    
                    // 应用高亮
                    el.style.outline = colors.outline;
                    el.style.backgroundColor = colors.bg;
                    
                    highlightedCount++;
                }
                
                // 📊 统计
                const elType = info.role || info.tagName;
                typeCounts[elType] = (typeCounts[elType] || 0) + 1;
                
                if (info.bestSelector) {
                    if (info.bestSelector.unique === true) uniqueCount++;
                    else if (info.bestSelector.unique === false) nonUniqueCount++;
                }
            } catch (e) {}
        });
        
        // 提取 label[for] 关联
        const labelForMap = {};
        document.querySelectorAll('label[for]').forEach(label => {
            const forId = label.getAttribute('for');
            const labelText = (label.innerText || label.textContent || '').trim();
            if (forId && labelText) {
                labelForMap[forId] = labelText;
            }
        });
        
        // 🚀 新增：提取最佳选择器映射（xpath → 最佳选择器）
        const bestSelectorMap = {};
        results.forEach(elem => {
            if (elem.xpath && elem.bestSelector) {
                bestSelectorMap[elem.xpath] = {
                    code: elem.bestSelector.code,
                    type: elem.bestSelector.type,
                    score: elem.bestSelector.score,
                    reason: elem.bestSelector.reason
                };
            }
        });
        
        // 🚀 新增：按选择器质量排序元素（分数低的在前）
        results.sort((a, b) => {
            const scoreA = a.bestSelector ? a.bestSelector.score : SCORE.CSS_FALLBACK;
            const scoreB = b.bestSelector ? b.bestSelector.score : SCORE.CSS_FALLBACK;
            return scoreA - scoreB;
        });
        
        // 📊 控制台日志输出（在浏览器 DevTools 中可见）
        const visibleTotal = results.filter(e => e.isVisible).length;
        console.log('%c[Kiro JS Injection] 🚀 检测完成', 'color: #FF4444; font-weight: bold; font-size: 14px;');
        console.log(`  📊 总计: ${results.length} 个可交互元素, ${visibleTotal} 个可见`);
        console.log(`  🎨 高亮: ${highlightedCount} 个元素已标记`);
        console.log(`  ✅ 唯一选择器: ${uniqueCount} 个, ❌ 非唯一: ${nonUniqueCount} 个`);
        console.log('  📋 元素类型分布:', typeCounts);
        
        // 输出 Top 5 最佳选择器
        const top5 = results.filter(r => r.bestSelector).slice(0, 5);
        if (top5.length > 0) {
            console.log('  🏆 Top 5 最佳选择器:');
            top5.forEach((r, i) => {
                const sel = r.bestSelector;
                const uniqueTag = sel.unique === true ? '✅' : sel.unique === false ? '❌' : '❓';
                console.log(`    ${i+1}. ${uniqueTag} [score=${sel.score}] ${sel.code} (${sel.reason})`);
            });
        }
        
        // 输出非唯一选择器警告
        const nonUniques = results.filter(r => r.bestSelector && r.bestSelector.unique === false);
        if (nonUniques.length > 0) {
            console.warn(`%c[Kiro] ⚠️ ${nonUniques.length} 个元素的选择器不唯一:`, 'color: #FF8800; font-weight: bold;');
            nonUniques.slice(0, 5).forEach(r => {
                console.warn(`    ${r.bestSelector.code} → ${r.bestSelector.matchCount} matches`);
            });
        }
        
        return {
            elements: results,
            labelForMap: labelForMap,
            bestSelectorMap: bestSelectorMap,
            totalCount: results.length,
            visibleCount: visibleTotal,
            highlightedCount: highlightedCount,
            uniqueCount: uniqueCount,
            nonUniqueCount: nonUniqueCount,
            typeCounts: typeCounts,
            timestamp: Date.now()
        };
    })();
    '''
    
    def get_js_detection_script(self) -> str:
        """
        获取 JS 注入检测脚本（动态注入评分常量，确保 JS/Python 一致）
        
        此脚本可在 Playwright 中通过 page.evaluate() 执行，
        返回页面上所有可交互元素的详细信息。
        
        Returns:
            JavaScript 代码字符串
        """
        # 动态注入评分常量，替换 JS 中的硬编码 SCORE 对象
        scores_js = "const SCORE = " + json.dumps(SELECTOR_SCORES) + ";"
        script = self.JS_INTERACTIVE_DETECTOR.replace(
            '// __SCORES_INJECTED_FROM_PYTHON__',
            scores_js
        )
        return script
    
    def process_js_detection_result(self, js_result: dict):
        """
        处理 JS 注入检测结果，更新内部缓存
        
        🚀 增强版本：充分利用 JS 检测的选择器推荐和评分
        
        Args:
            js_result: JS 检测返回的结果字典，包含：
                - elements: 元素列表
                - labelForMap: label[for] 关联映射
                - bestSelectorMap: xpath → 最佳选择器映射
                - totalCount: 总数
                - visibleCount: 可见元素数
                - timestamp: 时间戳
        """
        if not js_result:
            return
        
        elements = js_result.get('elements', [])
        label_for_map = js_result.get('labelForMap', {})
        best_selector_map = js_result.get('bestSelectorMap', {})
        
        # 更新 label[for] 缓存（比 HTML 解析更准确）
        if label_for_map:
            self._js_label_for_cache.update(label_for_map)
            logs.info(f"[SemanticSelectorMiddleware] JS 检测到 {len(label_for_map)} 个 label[for] 关联")
        
        # 🚀 新增：保存最佳选择器映射
        if best_selector_map:
            self._js_best_selector_map.update(best_selector_map)
            logs.info(f"[SemanticSelectorMiddleware] JS 检测到 {len(best_selector_map)} 个最佳选择器")
        
        # 更新元素缓存
        for elem in elements:
            xpath = elem.get('xpath')
            if xpath:
                self._xpath_to_js_attrs[xpath] = elem
        
        self._js_detected_elements = elements
        visible_count = js_result.get('visibleCount', len(elements))
        highlighted_count = js_result.get('highlightedCount', 0)
        unique_count = js_result.get('uniqueCount', 0)
        non_unique_count = js_result.get('nonUniqueCount', 0)
        type_counts = js_result.get('typeCounts', {})
        
        logs.info(f"[SemanticSelectorMiddleware] 🚀 JS 注入检测完成:")
        logs.info(f"  📊 总计: {len(elements)} 个可交互元素, {visible_count} 个可见")
        logs.info(f"  🎨 高亮: {highlighted_count} 个元素已在浏览器中标记")
        logs.info(f"  ✅ 唯一选择器: {unique_count} 个, ❌ 非唯一: {non_unique_count} 个")
        
        if type_counts:
            type_str = ', '.join(f"{k}={v}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))
            logs.info(f"  📋 元素类型分布: {type_str}")
        
        # 输出 Top 5 最佳选择器
        top_elements = [e for e in elements if e.get('bestSelector')][:5]
        if top_elements:
            logs.info(f"  🏆 Top 5 最佳选择器:")
            for i, elem in enumerate(top_elements):
                sel = elem['bestSelector']
                unique_tag = '✅' if sel.get('unique') is True else ('❌' if sel.get('unique') is False else '❓')
                logs.info(f"    {i+1}. {unique_tag} [score={sel.get('score', '?')}] {sel.get('code', '?')} ({sel.get('reason', '')})")
        
        # 非唯一选择器警告
        non_unique_elements = [e for e in elements if e.get('bestSelector', {}).get('unique') is False]
        if non_unique_elements:
            logs.warning(f"  ⚠️ {len(non_unique_elements)} 个元素的最佳选择器不唯一:")
            for elem in non_unique_elements[:5]:
                sel = elem['bestSelector']
                logs.warning(f"    {sel.get('code', '?')} → {sel.get('matchCount', '?')} matches")
        
        # 合并到现有元素缓存
        self._merge_js_detection_to_cache(elements)
    
    async def _auto_inject_js_detection(self, handler, original_request, original_tool_call_id: str):
        """
        🚀 P0-004: 自动执行 JS 注入检测
        
        在 browser_snapshot/browser_navigate 返回后，直接调用 browser_evaluate 工具
        执行 JS_INTERACTIVE_DETECTOR 脚本，获取页面所有可交互元素的完整属性。
        
        Args:
            handler: 中间件 handler（未使用，保留接口兼容）
            original_request: 原始请求（未使用）
            original_tool_call_id: 原始工具调用 ID
        """
        import json
        
        logs.info(f"[SemanticSelectorMiddleware] 🚀 自动 JS 注入检测开始...")
        
        try:
            # 从预缓存中获取 browser_evaluate 工具
            evaluate_tool = self._find_browser_evaluate_tool()
            if not evaluate_tool:
                logs.warning(f"[SemanticSelectorMiddleware] ⚠️ 未找到 browser_evaluate 工具，跳过自动注入")
                return
            
            js_script = self.get_js_detection_script()
            
            # 自动检测工具的参数名
            # Playwright MCP browser_evaluate 使用 'function' 参数
            param_name = self._detect_evaluate_param_name(evaluate_tool)
            logs.info(f"[SemanticSelectorMiddleware] 📋 browser_evaluate 参数名: {param_name}")
            
            # 🔑 关键：Playwright MCP 的 function 参数期望函数定义 () => { ... }
            # 而 JS_INTERACTIVE_DETECTOR 是 IIFE 格式 (() => { ... })()
            # 需要转换：去掉外层包裹的 ( 和末尾的 )()
            js_to_send = js_script.strip()
            # 匹配 IIFE 模式: (fn)() 或 (fn)();
            iife_match = re.match(r'^\((.+)\)\(\);?\s*$', js_to_send, re.DOTALL)
            if iife_match:
                js_to_send = iife_match.group(1).strip()
                logs.info(f"[SemanticSelectorMiddleware] 🔄 IIFE → 函数定义（去掉外层调用）")
            
            logs.debug(f"[SemanticSelectorMiddleware] JS 脚本前50字符: {js_to_send[:50]}...")
            
            # 直接调用工具（绕过中间件链，避免 tool 路由问题）
            tool_input = {param_name: js_to_send}
            js_raw_result = await evaluate_tool.ainvoke(tool_input)
            
            # 解析结果 — ainvoke 返回 list[dict] (MCP content blocks 格式)
            js_content = ""
            if isinstance(js_raw_result, list):
                # MCP 返回格式: [{'type': 'text', 'text': '### Result\n{...}'}]
                text_parts = []
                for block in js_raw_result:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                    elif isinstance(block, str):
                        text_parts.append(block)
                js_content = '\n'.join(text_parts)
            elif isinstance(js_raw_result, str):
                js_content = js_raw_result
            elif hasattr(js_raw_result, 'content'):
                js_content = js_raw_result.content if isinstance(js_raw_result.content, str) else str(js_raw_result.content)
            else:
                js_content = str(js_raw_result)
            
            # 清理 Playwright MCP 返回格式：去掉 "### Result\n" 前缀
            if '### Result' in js_content:
                js_content = js_content.split('### Result', 1)[-1].strip()
            else:
                js_content = js_content.strip()
            
            if js_content:
                try:
                    js_data = json.loads(js_content) if isinstance(js_content, str) else js_content
                    if isinstance(js_data, dict) and 'elements' in js_data:
                        self.process_js_detection_result(js_data)
                        total = js_data.get('totalCount', 0)
                        visible = js_data.get('visibleCount', 0)
                        logs.info(f"[SemanticSelectorMiddleware] ✅ 自动 JS 注入成功: {total} 元素, {visible} 可见")
                    else:
                        logs.warning(f"[SemanticSelectorMiddleware] ⚠️ JS 注入返回格式异常: {str(js_content)[:200]}")
                except json.JSONDecodeError as e:
                    # 可能有多段内容拼接，尝试用 JSONDecoder 只解析第一个对象
                    try:
                        decoder = json.JSONDecoder()
                        js_data, _ = decoder.raw_decode(js_content)
                        if isinstance(js_data, dict) and 'elements' in js_data:
                            self.process_js_detection_result(js_data)
                            total = js_data.get('totalCount', 0)
                            visible = js_data.get('visibleCount', 0)
                            logs.info(f"[SemanticSelectorMiddleware] ✅ 自动 JS 注入成功（raw_decode）: {total} 元素, {visible} 可见")
                        else:
                            logs.warning(f"[SemanticSelectorMiddleware] ⚠️ JS 注入返回格式异常: {str(js_content)[:200]}")
                    except json.JSONDecodeError:
                        logs.warning(f"[SemanticSelectorMiddleware] ⚠️ JS 注入结果 JSON 解析失败: {e}")
                        logs.warning(f"[SemanticSelectorMiddleware] 📦 内容前200字符: {str(js_content)[:200]}")
            else:
                logs.warning(f"[SemanticSelectorMiddleware] ⚠️ JS 注入无返回内容")
                
        except Exception as e:
            # 自动注入失败不应影响主流程
            logs.warning(f"[SemanticSelectorMiddleware] ⚠️ 自动 JS 注入失败（不影响主流程）: {e}")
            # 特定错误时禁用自动注入
            if "not found" in str(e).lower() or "not supported" in str(e).lower():
                logs.warning(f"[SemanticSelectorMiddleware] 🔇 browser_evaluate 不可用，禁用自动 JS 注入")
                self._js_auto_inject_enabled = False
    
    def _detect_evaluate_param_name(self, evaluate_tool) -> str:
        """
        自动检测 browser_evaluate 工具的参数名
        
        从工具的 args_schema 中读取 required 字段或第一个 string 类型参数。
        Playwright MCP @latest 版本使用 'function' 参数。
        
        Returns:
            检测到的参数名，默认 'function'
        """
        # 已缓存
        if self._evaluate_param_name:
            return self._evaluate_param_name
        
        try:
            schema = getattr(evaluate_tool, 'args_schema', None)
            if schema:
                schema_dict = None
                
                # Pydantic v1: .schema()
                if hasattr(schema, 'schema'):
                    schema_dict = schema.schema()
                # Pydantic v2: .model_json_schema()
                elif hasattr(schema, 'model_json_schema'):
                    schema_dict = schema.model_json_schema()
                
                if schema_dict:
                    properties = schema_dict.get('properties', {})
                    required = schema_dict.get('required', [])
                    logs.info(f"[SemanticSelectorMiddleware] browser_evaluate schema: properties={list(properties.keys())}, required={required}")
                    
                    # 优先使用 required 中的第一个 string 参数
                    for req_field in required:
                        prop = properties.get(req_field, {})
                        if prop.get('type') == 'string':
                            self._evaluate_param_name = req_field
                            logs.info(f"[SemanticSelectorMiddleware] 检测到必填参数: {req_field}")
                            return req_field
                    
                    # 回退：第一个 string 类型参数
                    for key, val in properties.items():
                        if val.get('type') == 'string':
                            self._evaluate_param_name = key
                            logs.info(f"[SemanticSelectorMiddleware] 检测到首个 string 参数: {key}")
                            return key
                
                # Pydantic v2 model_fields
                elif hasattr(schema, 'model_fields'):
                    fields = list(schema.model_fields.keys())
                    logs.info(f"[SemanticSelectorMiddleware] browser_evaluate model_fields: {fields}")
                    if fields:
                        self._evaluate_param_name = fields[0]
                        return fields[0]
                        
        except Exception as e:
            logs.debug(f"[SemanticSelectorMiddleware] schema 解析异常: {e}")
        
        # 默认使用 function（Playwright MCP @latest 的实际参数名）
        self._evaluate_param_name = 'function'
        return 'function'
    
    def _find_browser_evaluate_tool(self, request=None) -> any:
        """
        获取 browser_evaluate 工具实例
        
        优先使用 set_tools() 预缓存的工具实例（最可靠）。
        
        Returns:
            browser_evaluate 工具实例，未找到返回 None
        """
        # 已通过 set_tools() 缓存
        if self._browser_evaluate_tool is not None:
            return self._browser_evaluate_tool
        
        # 未缓存，说明 set_tools() 未被调用或工具列表中没有 browser_evaluate
        logs.warning(f"[SemanticSelectorMiddleware] ⚠️ browser_evaluate 工具未缓存，请确保 set_tools() 已被调用")
        return None
    
    def _merge_js_detection_to_cache(self, js_elements: List[dict]):
        """
        将 JS 检测结果合并到现有元素缓存
        
        🚀 增强版本：
        1. 通过 xpath 精确关联（新增）
        2. 保存 JS 推荐选择器和评分
        3. 保存可见性信息
        4. 利用 selectorCandidates 列表
        
        Args:
            js_elements: JS 检测返回的元素列表
        """
        if not js_elements or not self._element_cache:
            return
        
        matched_count = 0
        
        for js_elem in js_elements:
            js_id = js_elem.get('id')
            js_name = js_elem.get('name')
            js_testid = js_elem.get('dataTestid')
            js_text = js_elem.get('text', '').lower()[:50]
            js_role = js_elem.get('role')
            js_aria_label = js_elem.get('ariaLabel')
            js_xpath = js_elem.get('xpath')
            js_best_selector = js_elem.get('bestSelector')
            js_selector_candidates = js_elem.get('selectorCandidates', [])
            js_is_visible = js_elem.get('isVisible', True)
            js_cursor_pointer = js_elem.get('cursorPointer', False)
            
            # 尝试匹配现有缓存中的元素
            for ref, cached_elem in self._element_cache.items():
                matched = False
                match_reason = None
                
                # 🚀 新增：通过 xpath 精确匹配（最可靠）
                cached_xpath = cached_elem.get('_js_xpath')
                if js_xpath and cached_xpath and js_xpath == cached_xpath:
                    matched = True
                    match_reason = 'xpath'
                
                # 1. 通过 data-testid 匹配
                if not matched and js_testid and cached_elem.get('data-testid') == js_testid:
                    matched = True
                    match_reason = 'testid'
                
                # 2. 通过 id 匹配
                elif not matched and js_id and cached_elem.get('id') == js_id:
                    matched = True
                    match_reason = 'id'
                
                # 3. 通过 name 匹配
                elif not matched and js_name and cached_elem.get('name') == js_name:
                    matched = True
                    match_reason = 'name'
                
                # 4. 通过 aria-label 匹配
                elif not matched and js_aria_label and cached_elem.get('aria-label') == js_aria_label:
                    matched = True
                    match_reason = 'aria-label'
                
                # 5. 通过 role + text 匹配
                elif not matched and js_role and js_text and cached_elem.get('role') == js_role:
                    cached_text = (cached_elem.get('name') or cached_elem.get('text') or '').lower()[:50]
                    if js_text and cached_text and (js_text in cached_text or cached_text in js_text):
                        matched = True
                        match_reason = 'role+text'
                
                if matched:
                    # 补充缺失属性
                    updated = False
                    
                    if not cached_elem.get('data-testid') and js_testid:
                        cached_elem['data-testid'] = js_testid
                        updated = True
                    
                    if not cached_elem.get('aria-label') and js_aria_label:
                        cached_elem['aria-label'] = js_aria_label
                        updated = True
                    
                    if not cached_elem.get('name') and js_name:
                        cached_elem['name'] = js_name
                        updated = True
                    
                    if not cached_elem.get('placeholder') and js_elem.get('placeholder'):
                        cached_elem['placeholder'] = js_elem.get('placeholder')
                        updated = True
                    
                    # 🚀 新增：保存 aria-labelledby
                    js_aria_labelledby = js_elem.get('ariaLabelledby')
                    if js_aria_labelledby and not cached_elem.get('aria-labelledby'):
                        cached_elem['aria-labelledby'] = js_aria_labelledby
                        updated = True
                    
                    # 🚀 新增：保存 xpath（用于后续关联）
                    if not cached_elem.get('_js_xpath') and js_xpath:
                        cached_elem['_js_xpath'] = js_xpath
                        updated = True
                    
                    # 🚀 新增：保存 JS 推荐选择器
                    if js_best_selector:
                        cached_elem['_js_best_selector'] = js_best_selector.get('code')
                        cached_elem['_js_best_selector_type'] = js_best_selector.get('type')
                        cached_elem['_js_score'] = js_best_selector.get('score', 999999)
                        cached_elem['_js_selector_reason'] = js_best_selector.get('reason')
                        cached_elem['_js_unique'] = js_best_selector.get('unique')
                        cached_elem['_js_match_count'] = js_best_selector.get('matchCount')
                        updated = True
                    
                    # 🚀 新增：保存选择器候选列表
                    if js_selector_candidates:
                        cached_elem['_js_selector_candidates'] = js_selector_candidates
                        updated = True
                    
                    # 🚀 新增：保存可见性
                    cached_elem['_js_is_visible'] = js_is_visible
                    updated = True
                    
                    # 标记 JS 检测的额外属性
                    cached_elem['_js_detected'] = True
                    
                    if js_cursor_pointer and not cached_elem.get('clickable'):
                        cached_elem['clickable'] = True
                        cached_elem['_js_cursor_pointer'] = True
                        updated = True
                    
                    if updated:
                        matched_count += 1
                    
                    break
        
        # 更新 label[for] 关联
        self._update_labels_from_js_detection()
        
        logs.info(f"[SemanticSelectorMiddleware] JS 检测结果合并完成，更新 {matched_count} 个元素缓存")
    
    def _update_labels_from_js_detection(self):
        """
        使用 JS 检测的 label[for] 关联更新元素缓存
        
        为输入框元素添加隐式标签（来自 label[for] 关联）
        """
        if not self._js_label_for_cache or not self._element_cache:
            return
        
        updated_count = 0
        
        for ref, cached_elem in self._element_cache.items():
            # 只处理表单元素
            if cached_elem.get('type') not in ['textbox', 'combobox', 'checkbox', 'radio']:
                if cached_elem.get('role') not in ['textbox', 'combobox', 'checkbox', 'radio']:
                    continue
            
            # 如果已有隐式标签，跳过
            if cached_elem.get('implicit_label'):
                continue
            
            # 尝试通过 id 关联 label
            elem_id = cached_elem.get('id') or cached_elem.get('name')
            
            if elem_id:
                # 直接匹配
                label = self._js_label_for_cache.get(elem_id)
                if label:
                    cached_elem['implicit_label'] = label
                    cached_elem['_label_source'] = 'js_label_for'
                    updated_count += 1
                    logs.debug(f"[SemanticSelectorMiddleware] JS label[for] 关联: {elem_id} -> '{label}'")
            
            # 如果没有 id，尝试通过 JS 检测的元素属性关联
            js_xpath = cached_elem.get('_js_xpath')
            if js_xpath and js_xpath in self._xpath_to_js_attrs:
                js_attrs = self._xpath_to_js_attrs[js_xpath]
                js_id = js_attrs.get('id')
                if js_id and js_id in self._js_label_for_cache:
                    label = self._js_label_for_cache[js_id]
                    cached_elem['implicit_label'] = label
                    cached_elem['_label_source'] = 'js_label_for_by_xpath'
                    updated_count += 1
        
        if updated_count > 0:
            logs.info(f"[SemanticSelectorMiddleware] 通过 JS label[for] 关联更新 {updated_count} 个元素标签")
    
    def get_js_label_for_input(self, input_id: str) -> Optional[str]:
        """
        获取输入框关联的 label 文本
        
        优先使用 JS 检测结果（更准确），其次使用 HTML 解析结果。
        
        Args:
            input_id: 输入框的 id 属性
            
        Returns:
            label 文本，或 None
        """
        # 优先使用 JS 检测结果
        if input_id in self._js_label_for_cache:
            return self._js_label_for_cache[input_id]
        
        # 其次使用 HTML 解析结果
        return self._label_for_cache.get(input_id)
    
    def _is_dynamic_id(self, id_value: str) -> bool:
        """
        判断 ID 是否是动态生成的（不稳定）
        
        动态 ID 的特征：
        - 包含随机字符串：abc123xyz, x7f9k2
        - 包含数字序列：:r1:, :r2a:, r-1-2-3
        - 包含 UUID 或时间戳：8f14e45f, 1712345678
        - 以数字开头：123input
        
        静态 ID 的特征：
        - 语义化：username, password, submit-btn
        - 驼峰命名：inputUserName, btnSubmit
        - 短横线命名：user-name, submit-button
        
        Args:
            id_value: ID 值
            
        Returns:
            是否是动态 ID（True 表示不稳定，应该避免使用）
        """
        if not id_value:
            return True
        
        # 排除明显的语义化 ID
        semantic_keywords = [
            'user', 'pass', 'email', 'name', 'submit', 'login', 'logout',
            'button', 'btn', 'input', 'form', 'search', 'menu', 'nav',
            'header', 'footer', 'main', 'content', 'sidebar', 'modal',
            'dialog', 'alert', 'error', 'success', 'warning', 'info',
            'username', 'password', 'confirm', 'cancel', 'save', 'delete',
            'edit', 'add', 'remove', 'update', 'create', 'select', 'checkbox',
            'radio', 'text', 'textarea', 'label', 'title', 'description',
        ]
        
        id_lower = id_value.lower()
        for keyword in semantic_keywords:
            if keyword in id_lower:
                return False
        
        # 检查是否包含动态特征
        # 1. React/Aria 动态 ID：:r1:, :r2a:
        if re.match(r'^:r\d+[a-z]?:$', id_value):
            return True
        
        # 2. 随机字符串：8个以上连续的字母数字混合，无语义
        if re.match(r'^[a-z0-9]{8,}$', id_value, re.IGNORECASE):
            # 检查是否全是随机字符（没有连续的元音或辅音）
            vowels = set('aeiou')
            consonants = set('bcdfghjklmnpqrstvwxyz')
            vowel_count = sum(1 for c in id_value.lower() if c in vowels)
            consonant_count = sum(1 for c in id_value.lower() if c in consonants)
            
            # 如果元音和辅音比例接近 1:2（随机字符串的特征）
            if vowel_count > 0 and consonant_count > 0:
                ratio = vowel_count / consonant_count
                if 0.3 < ratio < 0.7:  # 随机字符串的比例范围
                    return True
        
        # 3. 包含长数字序列（可能是时间戳或随机数）
        if re.search(r'\d{6,}', id_value):
            return True
        
        # 4. UUID 格式
        if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', id_value, re.IGNORECASE):
            return True
        
        # 5. 以数字开头
        if id_value[0].isdigit():
            return True
        
        return False
    
    def _is_guid_like(self, id_value: str) -> bool:
        """
        使用 Codegen 算法判断 ID 是否像 GUID/动态生成
        
        Codegen 原版算法（移植自 selectorGenerator.ts）：
        - 检测字符类型转换次数（lower -> upper -> digit -> other）
        - 转换次数越多，越可能是随机字符串
        
        例如：
        - "username" -> 转换次数少 -> 静态 ID -> False
        - "abc123xyz" -> 转换次数多 -> 动态 ID -> True
        - "x7f9k2m" -> 转换次数多 -> 动态 ID -> True
        
        Args:
            id_value: ID 值
            
        Returns:
            True 表示像 GUID/动态 ID（应该避免使用）
        """
        if not id_value:
            return True
        
        last_character_type = None  # 'lower' | 'upper' | 'digit' | 'other'
        transition_count = 0
        
        for c in id_value:
            if c == '-' or c == '_':
                continue
            
            # 判断字符类型
            if 'a' <= c <= 'z':
                character_type = 'lower'
            elif 'A' <= c <= 'Z':
                character_type = 'upper'
            elif '0' <= c <= '9':
                character_type = 'digit'
            else:
                character_type = 'other'
            
            # Codegen 特殊处理：lower 跟在 upper 后不计数
            # 这是处理驼峰命名的情况（如 inputUserName）
            if character_type == 'lower' and last_character_type == 'upper':
                last_character_type = character_type
                continue
            
            # 计算类型转换次数
            if last_character_type and last_character_type != character_type:
                transition_count += 1
            
            last_character_type = character_type
        
        # Codegen 判断：转换次数 >= 长度/4 则认为是 GUID
        return transition_count >= len(id_value) / 4
    
    def _apply_score_penalty_for_length(self, candidates: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        """
        应用长度惩罚（Codegen 风格）
        
        对于分数在惩罚区间 (50-300) 的选择器，按长度增加分数：
        - 每增加 10 个字符，分数增加 0-10 分
        
        Args:
            candidates: 候选选择器列表 [(选择器, 分数), ...]
            
        Returns:
            应用惩罚后的候选列表
        """
        result = []
        for selector, score in candidates:
            # 只对惩罚区间内的选择器应用惩罚
            if K_BEGIN_PENALIZED_SCORE < score < K_END_PENALIZED_SCORE:
                # 计算长度惩罚
                length_penalty = min(K_TEXT_SCORE_RANGE, len(selector) // 10)
                score += length_penalty
            result.append((selector, score))
        return result
    
    def has_label_for_association(self, input_identifier: str) -> Tuple[bool, str]:
        """
        检查 input 是否有 label for 关联
        
        Args:
            input_identifier: input 的 id 或 name
            
        Returns:
            (是否有关联, label 文本)
        """
        if input_identifier in self._label_for_cache:
            return True, self._label_for_cache[input_identifier]
        return False, ""
    
    def _cache_element(self, ref: str, element_description: str, tool_args: dict):
        """
        缓存元素语义信息
        
        Args:
            ref: 元素引用
            element_description: 元素描述
            tool_args: 工具参数
        """
        if not ref:
            return
        
        # 从快照中获取语义信息
        semantic_info = self.get_semantic_info(ref)
        
        # 如果快照中没有，使用参数中的描述
        if not semantic_info:
            semantic_info = {
                'ref': ref,
                'description': element_description,
            }
        else:
            semantic_info['description'] = element_description
        
        # 缓存元素信息
        self._element_cache[ref] = semantic_info
        
        # 同时缓存快照上下文（用于后续 AI 优化）
        if self._current_snapshot:
            snapshot_context = self._build_snapshot_context_for_ai(ref)
            if snapshot_context:
                self._snapshot_context_cache[ref] = snapshot_context
        
        logs.debug(f"[SemanticSelectorMiddleware] 缓存元素: ref={ref}, desc={element_description}")
    
    def _try_recover_with_similar_element(self, tool_name: str, tool_args: dict, handler, request) -> Optional[Any]:
        """
        尝试使用相似元素恢复操作
        
        当 ref 失效时，尝试在快照中找到语义相似的元素，并使用新 ref 重试。
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            handler: 工具执行器
            request: 原始请求
            
        Returns:
            重试结果，或 None（无法恢复）
        """
        element_description = tool_args.get('element', '')
        
        if not element_description or not self._all_elements:
            return None
        
        # 搜索相似元素
        similar_elements = self._find_similar_elements(element_description)
        
        if not similar_elements:
            logs.warning(f"[SemanticSelectorMiddleware] 未找到相似元素: {element_description}")
            return None
        
        # 取最佳匹配
        best_match = similar_elements[0]
        new_ref = best_match.get('ref')
        match_score = best_match.get('match_score', 0)
        match_reason = best_match.get('match_reason', '')
        
        logs.info(f"[SemanticSelectorMiddleware] 找到相似元素:")
        logs.info(f"  - 原描述: {element_description}")
        logs.info(f"  - 新 ref: {new_ref}")
        logs.info(f"  - 匹配分数: {match_score:.2f}")
        logs.info(f"  - 匹配原因: {match_reason}")
        
        # 构造新的请求
        new_args = tool_args.copy()
        new_args['ref'] = new_ref
        
        # 更新请求
        new_request = self._create_new_request(request, new_args)
        
        if new_request is None:
            logs.warning("[SemanticSelectorMiddleware] 无法创建新请求")
            return None
        
        # 重试操作
        logs.info(f"[SemanticSelectorMiddleware] 使用新 ref={new_ref} 重试操作...")
        try:
            result = handler(new_request)
            logs.info(f"[SemanticSelectorMiddleware] 重试成功!")
            return result
        except Exception as e:
            logs.warning(f"[SemanticSelectorMiddleware] 重试失败: {e}")
            return None
    
    def _create_new_request(self, original_request, new_args: dict):
        """
        创建带有新参数的请求对象
        
        Args:
            original_request: 原始请求
            new_args: 新的参数
            
        Returns:
            新的请求对象
        """
        try:
            # 尝试创建新请求
            if hasattr(original_request, 'tool_call'):
                new_tool_call = original_request.tool_call.copy()
                new_tool_call['args'] = new_args
                
                # 创建新的请求对象
                class NewRequest:
                    def __init__(self, tool_call):
                        self.tool_call = tool_call
                
                return NewRequest(new_tool_call)
            
            return None
        except Exception as e:
            logs.error(f"[SemanticSelectorMiddleware] 创建新请求失败: {e}")
            return None
    
    async def awrap_tool_call(self, request, handler):
        """
        异步拦截工具执行，实时生成语义化选择器
        
        新流程（实时 AI 优化）：
        1. 检测到 ref 参数时，立即调用 AI 生成语义化选择器
        2. 将语义化代码存入缓存，供 CodeCollector 使用
        3. 继续用 ref 执行（运行时仍用 ref）
        4. 脚本中记录语义化代码
        
        优势：
        - 快照数据新鲜，AI 生成更准确
        - 无需后处理，简化流程
        - 一次性投资，后续执行无 AI 成本
        """
        tool_name, tool_args, tool_call_id = self._extract_tool_call_info(request)
        
        # 入口日志（诊断用）
        logs.info(f"[SemanticSelectorMiddleware] awrap_tool_call 被调用: {tool_name}, tool_call_id={tool_call_id}")
        
        # 增加操作计数
        if tool_name.startswith('browser_') and tool_name != 'browser_snapshot':
            self._operation_count += 1
            self._snapshot_age += 1
        
        # 🤖 实时 AI 优化：在执行前生成语义化选择器
        ai_semantic_code = None
        if tool_name in ['browser_click', 'browser_type', 'browser_hover', 'browser_select_option']:
            ref = tool_args.get('ref')
            logs.info(f"[SemanticSelectorMiddleware] 检测到浏览器操作: {tool_name}, ref={ref}, _all_elements数量={len(self._all_elements)}")
            if ref and self._all_elements:
                action = 'click' if tool_name == 'browser_click' else \
                         'fill' if tool_name == 'browser_type' else \
                         'hover' if tool_name == 'browser_hover' else 'select'
                value = tool_args.get('text') or tool_args.get('value')
                
                # 实时调用 AI 生成语义化选择器
                ai_semantic_code = self._generate_semantic_selector_realtime(ref, action, value)
                if ai_semantic_code:
                    logs.info(f"[SemanticSelectorMiddleware] 🤖 AI 实时生成: {ai_semantic_code}")
                    # 存入缓存，供 CodeCollector 使用
                    self._ai_generated_code[ref] = ai_semantic_code
            elif ref and not self._all_elements:
                logs.warning(f"[SemanticSelectorMiddleware] ⚠️ _all_elements 为空，跳过 AI 生成")
        
        # 🔧 jQuery 语法转换：修复 browser_evaluate 中的 jQuery 选择器
        if tool_name == 'browser_evaluate':
            original_args = tool_args
            converted_args = self._transform_browser_evaluate_args(tool_args)
            
            if converted_args != original_args:
                logs.info(f"[SemanticSelectorMiddleware] 🔄 已转换 browser_evaluate 参数")
                # 尝试修改 request 中的参数
                tool_call = getattr(request, 'tool_call', None)
                if tool_call and isinstance(tool_call, dict):
                    tool_call['args'] = converted_args
                    tool_args = converted_args  # 更新本地变量
        
        try:
            # 执行工具调用
            result = await handler(request)
            
            # 更新快照：browser_navigate 和 browser_snapshot 都会返回快照信息
            if tool_name in ['browser_navigate', 'browser_snapshot']:
                content = self._extract_content(result)
                logs.info(f"[SemanticSelectorMiddleware] {tool_name} 返回，content长度={len(content) if content else 0}")
                if content:
                    # 🆕 尝试从快照中提取原始 HTML（用于判断 label for 关联）
                    raw_html = self._extract_raw_html_from_snapshot(content)
                    self.update_snapshot(content, raw_html)
                    
                    # 🚀 P0-004: 自动 JS 注入检测（替代被动提示）
                    # 在快照更新后，自动执行 JS 检测脚本，获取所有可交互元素的完整属性
                    if self._js_auto_inject_enabled:
                        current_url = tool_args.get('url', '') or tool_name
                        # 仅在 URL 变化或首次时注入（避免同一页面重复注入）
                        # browser_snapshot 总是重新注入（页面可能已变化）
                        should_inject = (tool_name == 'browser_snapshot') or (current_url != self._js_auto_injected_url)
                        if should_inject:
                            await self._auto_inject_js_detection(handler, request, tool_call_id)
                            self._js_auto_injected_url = current_url
                        else:
                            logs.debug(f"[SemanticSelectorMiddleware] 跳过自动 JS 注入（URL 未变化）")
                    
                    # 如果没有原始 HTML 且自动注入未启用，追加提示让 AI 获取
                    if tool_name == 'browser_navigate' and not raw_html and not self._raw_html_cache and not self._js_auto_inject_enabled:
                        result = self._append_html_fetch_hint(result, tool_call_id)
            
            # 如果是需要语义信息的工作，缓存元素信息
            if tool_name in ['browser_click', 'browser_type', 'browser_hover', 'browser_select_option']:
                ref = tool_args.get('ref')
                element = tool_args.get('element', '')
                
                # 缓存元素信息（用于恢复机制）
                if ref and element:
                    self._cache_element(ref, element, tool_args)
            
            return result
            
        except ToolException as e:
            error_msg = str(e)
            
            # 检测 ref 失效错误
            if "not found in the current page snapshot" in error_msg or \
               "Element reference is stale" in error_msg:
                
                ref = tool_args.get('ref', 'unknown')
                element = tool_args.get('element', '')
                
                logs.warning(f"[SemanticSelectorMiddleware] Ref 失效: ref={ref}, element={element}")
                
                # 增强恢复：尝试多种方式获取元素描述
                element_description = self._get_element_description_for_recovery(ref, element, tool_args)
                
                # 尝试自动恢复
                if self._all_elements and element_description:
                    logs.info(f"[SemanticSelectorMiddleware] 尝试自动恢复，搜索相似元素: '{element_description}'")
                    recovered_result = await self._try_recover_with_similar_element_async(
                        tool_name, tool_args, handler, request, element_description
                    )
                    if recovered_result is not None:
                        return recovered_result
                
                # 🔧 关键修复：使用正确的 tool_call_id 返回 ToolMessage
                # 原来：tool_call_id='recovery_' + ref（错误！）
                # 现在：使用原始请求中的 tool_call_id
                logs.warning(f"[SemanticSelectorMiddleware] 自动恢复失败，返回友好提示（tool_call_id={tool_call_id}）")
                return self._create_friendly_error_result(ref, element_description, tool_name, tool_call_id)
            
            # 其他错误直接抛出
            raise
    
    def _get_element_description_for_recovery(self, ref: str, element: str, tool_args: dict) -> str:
        """
        获取用于恢复的元素描述（多策略）
        
        优先级：
        1. element 参数（如果有效）
        2. 缓存中的 implicit_label
        3. 缓存中的 name/text
        4. 工具参数中的其他线索（如 text 参数）
        """
        # 策略 1：检查 element 参数是否有效
        if element and element not in ['未知元素', 'unknown', '', ' ']:
            return element
        
        # 策略 2：从缓存中获取 implicit_label
        if ref in self._element_cache:
            cached_info = self._element_cache[ref]
            implicit_label = cached_info.get('implicit_label', '')
            if implicit_label:
                logs.info(f"[SemanticSelectorMiddleware] 从缓存获取 implicit_label: '{implicit_label}'")
                return implicit_label
            
            # 策略 3：从缓存中获取 name/text
            name = cached_info.get('name', '')
            text = cached_info.get('text', '')
            if name or text:
                return name or text
        
        # 策略 4：从工具参数中获取线索
        fill_text = tool_args.get('text', '')
        if fill_text:
            # 尝试推断：如果是密码，可能是密码输入框
            if 'password' in fill_text.lower() or '@' in fill_text:
                return 'Password'
            # 如果是邮箱格式，可能是邮箱输入框
            if '@' in fill_text and '.' in fill_text:
                return 'Email'
            # 如果是用户名格式
            if fill_text.replace('.', '').replace('_', '').isalnum():
                return 'Username'
        
        return ''
    
    def _create_friendly_error_result(self, ref: str, element_description: str, tool_name: str, tool_call_id: str = '') -> ToolMessage:
        """
        创建友好的错误结果（不崩溃，返回可处理的提示）
        
        🔧 关键修复：tool_call_id 必须使用原始请求中的 ID，不能自己生成！
        否则会导致 API 报错：'An assistant message with tool_calls must be followed by tool messages'
        
        Args:
            ref: 元素引用
            element_description: 元素描述
            tool_name: 工具名称
            tool_call_id: 原始请求中的 tool_call_id（必须正确！）
            
        Returns:
            ToolMessage 对象
        """
        from langchain_core.messages import ToolMessage
        
        # 构建友好的错误信息
        error_msg = f"""## ⚠️ 元素定位失败

**问题**：无法在页面快照中找到元素 `{ref}`

**可能原因**：
1. 页面发生了变化（导航、刷新、动态更新）
2. 元素引用已过期

**解决方案**：
1. 请调用 `browser_snapshot` 获取最新快照
2. 然后重新定位元素并执行操作

**提示**：获取新快照后，页面元素的 ref 会发生变化。
"""
        
        # 🔧 关键：使用原始的 tool_call_id
        # 如果 tool_call_id 为空，生成一个基于时间戳的唯一 ID（最后的回退）
        if not tool_call_id:
            import uuid
            tool_call_id = f"fallback_{uuid.uuid4().hex[:8]}"
            logs.warning(f"[SemanticSelectorMiddleware] ⚠️ tool_call_id 为空，使用回退 ID: {tool_call_id}")
        
        return ToolMessage(
            content=error_msg,
            name=tool_name,
            tool_call_id=tool_call_id,  # 使用正确的 tool_call_id
            status='error',
        )
    
    async def _try_recover_with_similar_element_async(self, tool_name: str, tool_args: dict, handler, request, element_description: str = None) -> Optional[Any]:
        """
        异步版本的恢复方法
        
        增强功能：
        - 支持传入自定义的 element_description
        - 支持使用 implicit_label 进行匹配
        """
        # 使用传入的描述或从参数获取
        if not element_description:
            element_description = tool_args.get('element', '')
        
        if not element_description or not self._all_elements:
            return None
        
        # 搜索相似元素
        similar_elements = self._find_similar_elements(element_description)
        
        if not similar_elements:
            logs.warning(f"[SemanticSelectorMiddleware] 未找到相似元素: {element_description}")
            return None
        
        # 显示前3个匹配结果
        logs.info(f"[SemanticSelectorMiddleware] 找到 {len(similar_elements)} 个相似元素:")
        for i, elem in enumerate(similar_elements[:3]):
            logs.info(f"  {i+1}. ref={elem.get('ref')}, "
                     f"name={elem.get('name', '')}, "
                     f"text={elem.get('text', '')}, "
                     f"implicit_label={elem.get('implicit_label', '')}, "
                     f"score={elem.get('match_score', 0):.2f}, "
                     f"reason={elem.get('match_reason', '')}")
        
        # 取最佳匹配
        best_match = similar_elements[0]
        new_ref = best_match.get('ref')
        
        # 构造新的请求
        new_args = tool_args.copy()
        new_args['ref'] = new_ref
        
        new_request = self._create_new_request(request, new_args)
        
        if new_request is None:
            logs.warning("[SemanticSelectorMiddleware] 无法创建新请求")
            return None
        
        # 重试操作
        logs.info(f"[SemanticSelectorMiddleware] 使用新 ref={new_ref} 重试操作...")
        try:
            result = await handler(new_request)
            logs.info(f"[SemanticSelectorMiddleware] ✅ 自动恢复成功!")
            
            # 更新缓存
            self._cache_element(new_ref, element_description, new_args)
            
            return result
        except Exception as e:
            logs.warning(f"[SemanticSelectorMiddleware] 重试失败: {e}")
            return None
    
    def _generate_recovery_message(self, ref: str, element: str, tool_name: str) -> str:
        """
        生成详细的恢复指导消息
        """
        # 检查是否有相似元素可以建议
        similar_elements = self._find_similar_elements(element) if element else []
        
        suggestions = ""
        if similar_elements:
            suggestions = "\n\n**可能的替代元素**：\n"
            for i, elem in enumerate(similar_elements[:3]):
                suggestions += f"{i+1}. ref=`{elem.get('ref')}` "
                if elem.get('name'):
                    suggestions += f"name=\"{elem.get('name')}\" "
                if elem.get('text'):
                    suggestions += f"text=\"{elem.get('text')}\" "
                suggestions += f"(相似度: {elem.get('match_score', 0):.0%})\n"
        
        recovery_message = f"""### 错误：页面快照已过期

**原因**：元素引用 `{ref}` ({element}) 在当前页面快照中不存在。
这通常是因为页面发生了变化（导航、刷新、动态更新等）。

**当前状态**：
- 快照年龄: {self._snapshot_age} 次操作
- 快照元素数: {len(self._all_elements)}
{suggestions}
**恢复步骤**（请按顺序执行）：
1. 调用 `browser_snapshot` 获取最新的页面快照
2. 从新快照中找到目标元素 "{element}"
3. 使用新快照中的 ref 重新执行操作

**重要提示**：
- 不要重试当前操作，先获取新快照
- 新快照会包含最新的元素引用
- 获取快照后，页面元素的 ref 会发生变化

**建议**：在进行复杂操作前，定期调用 `browser_snapshot` 更新快照。

请立即调用 `browser_snapshot` 工具获取新快照。"""
        
        return recovery_message
    
    def _extract_tool_call_info(self, request) -> tuple:
        """
        从请求中提取工具调用信息
        
        Returns:
            (tool_name, tool_args, tool_call_id) 三元组
        """
        tool_call = getattr(request, 'tool_call', None)
        if tool_call:
            tool_name = tool_call.get('name', 'unknown')
            tool_args = tool_call.get('args', {})
            if not tool_args:
                tool_args = tool_call.get('arguments', {})
            # 获取 tool_call_id（关键：用于 ToolMessage 响应）
            tool_call_id = tool_call.get('id', '')
            return tool_name, tool_args, tool_call_id
        return 'unknown', {}, ''
    
    def _convert_jquery_to_vanilla_js(self, js_code: str) -> tuple[str, bool]:
        """
        将 jQuery 选择器语法转换为标准 JavaScript.
        
        支持的转换：
        1. :contains("text") -> 遍历 + textContent.includes()
        2. :has(selector:contains("text")) -> 嵌套处理
        
        Args:
            js_code: 原始 JavaScript 代码
            
        Returns:
            (转换后的代码, 是否进行了转换)
        """
        import re
        
        original_code = js_code
        converted = js_code
        
        # 检测是否包含 jQuery 语法
        jquery_patterns = [
            r':contains\s*\(',      # :contains()
            r'\.eq\s*\(\d+\)',      # .eq(n)
            r'\.first\s*\(\)',      # .first()
            r'\.last\s*\(\)',       # .last()
            r'\.children\s*\(\)',   # .children()
            r'\.parent\s*\(\)',     # .parent()
        ]
        
        has_jquery = any(re.search(p, converted) for p in jquery_patterns)
        
        if not has_jquery:
            return js_code, False
        
        logs.info(f"[SemanticSelectorMiddleware] 🔍 检测到 jQuery 语法，尝试转换...")
        
        # 模式1: 复杂的 :has(...:contains("text"))
        # 匹配 document.querySelector('li.el-select-dropdown__item:has(span:contains("Box"))')
        # 或 querySelector('...')
        complex_pattern = r"(?:document\.)?querySelector\(['\"]([^'\"]*?):has\(([^)]*?):contains\(['\"]([^'\"]*?)['\"]\)[^)]*\)['\"]\)"
        
        def replace_complex_contains(match):
            base_selector = match.group(1)  # li.el-select-dropdown__item
            inner_selector = match.group(2)  # span
            text = match.group(3)  # Box
            
            # 生成转换后的代码（直接替换整个 querySelector 调用）
            return f"""[...document.querySelectorAll('{base_selector}')].find(el => el.querySelector('{inner_selector}') && el.textContent.includes('{text}'))"""
        
        converted = re.sub(complex_pattern, replace_complex_contains, converted)
        
        # 模式2: 简单的 :contains("text")
        # 匹配 document.querySelector('li.item:contains("Box")')
        simple_contains = r"(?:document\.)?querySelector\(['\"]([^'\"]*?):contains\(['\"]([^'\"]*?)['\"]\)['\"]\)"
        
        def replace_simple_contains(match):
            selector = match.group(1)
            text = match.group(2)
            # 转换为：先选择再过滤
            base_selector = selector.split(':has')[0].strip() if ':has' in selector else selector
            return f"""[...document.querySelectorAll('{base_selector}')].find(el => el.textContent.includes('{text}'))"""
        
        # 只有在复杂模式没有匹配时才尝试简单模式
        if converted == original_code:
            converted = re.sub(simple_contains, replace_simple_contains, converted)
        
        if converted != original_code:
            logs.info(f"[SemanticSelectorMiddleware] ✅ jQuery 语法已转换:")
            logs.info(f"   原始: {original_code[:150]}...")
            logs.info(f"   转换: {converted[:150]}...")
            return converted, True
        else:
            logs.warning(f"[SemanticSelectorMiddleware] ⚠️ 无法自动转换 jQuery 语法")
            return js_code, False
    
    def _transform_browser_evaluate_args(self, tool_args: dict) -> dict:
        """
        转换 browser_evaluate 的参数，修复 jQuery 语法.
        
        Args:
            tool_args: 原始工具参数
            
        Returns:
            转换后的工具参数
        """
        import copy
        new_args = copy.deepcopy(tool_args)
        
        # 获取 function 或 script 参数
        function_code = new_args.get('function', '') or new_args.get('script', '')
        
        if not function_code:
            return tool_args
        
        # 检测并转换 jQuery 语法
        converted_code, was_converted = self._convert_jquery_to_vanilla_js(function_code)
        
        if was_converted:
            # 更新参数
            if 'function' in new_args:
                new_args['function'] = converted_code
            if 'script' in new_args:
                new_args['script'] = converted_code
            return new_args
        
        return tool_args
    
    def _extract_content(self, result) -> Optional[str]:
        """从工具结果中提取内容"""
        from langchain_core.messages import ToolMessage
        
        if isinstance(result, ToolMessage):
            content = result.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        return item.get('text', '')
        return None
    
    def _extract_raw_html_from_snapshot(self, content: str) -> Optional[str]:
        """
        从快照内容中提取原始 HTML
        
        Playwright MCP 返回的快照主要是 YAML 格式，通常不包含原始 HTML。
        
        策略：
        1. 检查是否包含 HTML 标签
        2. 从代码块中提取 HTML
        3. 返回空字符串（表示没有原始 HTML）
        
        注意：要获取原始 HTML，需要调用 browser_evaluate:
        await page.evaluate(() => document.documentElement.outerHTML)
        
        Args:
            content: 快照内容
            
        Returns:
            原始 HTML（如果有），否则返回空字符串
        """
        if not content:
            return ""
        
        # 尝试提取 HTML 内容
        # 格式1: 直接包含 HTML 标签
        if '<html' in content.lower() or '<body' in content.lower():
            # 提取 HTML 部分
            match = re.search(r'(<html[^>]*>.*?</html>)', content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)
            
            match = re.search(r'(<body[^>]*>.*?</body>)', content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)
        
        # 格式2: 包含在代码块中
        match = re.search(r'```html\s*(.+?)\s*```', content, re.DOTALL)
        if match:
            return match.group(1)
        
        # 返回空字符串（表示没有原始 HTML）
        return ""
    
    def _append_html_fetch_hint(self, result, tool_call_id: str):
        """
        在 browser_navigate 结果中追加获取 HTML 的提示
        
        当没有原始 HTML 时，追加一个提示让 AI 调用 browser_evaluate 获取。
        
        Args:
            result: 原始工具结果
            tool_call_id: 工具调用 ID
            
        Returns:
            追加提示后的结果
        """
        from langchain_core.messages import ToolMessage
        
        # 构建提示信息
        hint = """

---

💡 **系统提示：建议获取页面 HTML**

为了生成更精确、更稳定的选择器，建议调用以下命令获取页面的原始 HTML：

```
browser_evaluate
script: "document.documentElement.outerHTML"
```

**为什么要获取 HTML？**
- 原始 HTML 包含元素的 `id`、`name`、`data-testid` 等稳定属性
- 可以识别 `<label for="xxx">` 关联，生成可靠的 `getByLabel` 选择器
- 避免使用不稳定的临时引用（如 `[ref="e7"]`）

**建议**：在进行任何元素操作前，先获取 HTML 以确保选择器的稳定性。
"""
        
        # 提取原始内容
        original_content = self._extract_content(result)
        if original_content:
            new_content = original_content + hint
            
            # 返回新的 ToolMessage
            return ToolMessage(
                content=new_content,
                name='browser_navigate',
                tool_call_id=tool_call_id,
                status='success',
            )
        
        return result
        """
        使用 AI 优化选择器（同步版本，供脚本保存时调用）
        
        相比规则系统，AI 能更好理解：
        - 页面结构和语义
        - 哪个属性最稳定
        - 复杂的关联关系（如 label 不在元素上）
        
        Args:
            ref: 元素引用
            action: 操作类型（click, fill, hover, select）
            value: 填充的值（对于 fill 操作）
            
        Returns:
            优化后的选择器代码，失败返回 None
        """
        # 从缓存获取元素信息
        element_info = self._element_cache.get(ref)
        if not element_info:
            logs.warning(f"[SemanticSelectorMiddleware] ref={ref} 不在元素缓存中，无法 AI 优化")
            return None
        
        # 优先使用缓存的快照上下文（录制时保存的），其次使用实时快照
        snapshot_context = self._snapshot_context_cache.get(ref)
        if not snapshot_context:
            # 尝试从当前快照构建
            snapshot_context = self._build_snapshot_context_for_ai(ref)
        
        if not snapshot_context:
            logs.warning(f"[SemanticSelectorMiddleware] ref={ref} 无快照上下文，无法 AI 优化")
            return None
        
        try:
            from llms import get_default_model
            
            # 构建 prompt
            prompt = self._build_ai_prompt(element_info, action, value, snapshot_context)
            
            # 调用 LLM
            logs.info(f"[SemanticSelectorMiddleware] 🤖 调用 AI 优化选择器: ref={ref}, action={action}")
            llm = get_default_model()
            response = llm.invoke(prompt)
            
            # 解析响应
            ai_response = response.content if hasattr(response, 'content') else str(response)
            selector = self._parse_ai_response(ai_response, action, value)
            
            if selector:
                logs.info(f"[SemanticSelectorMiddleware] ✅ AI 优化成功: {selector}")
                return selector
            else:
                logs.warning(f"[SemanticSelectorMiddleware] AI 响应解析失败: {ai_response[:200]}")
                return None
                
        except Exception as e:
            logs.error(f"[SemanticSelectorMiddleware] AI 优化失败: {e}")
            return None
    
    # ========================================================================
    # 🚀 浏览器端选择器生成（移植 Codegen 核心能力）
    # ========================================================================
    
    # 浏览器端选择器生成脚本（嵌入 Python 字符串）
    BROWSER_SELECTOR_SCRIPT = """
(function() {
  // ========== Codegen 分数常量 ==========
  const K_TEST_ID_SCORE = 1;
  const K_OTHER_TEST_ID_SCORE = 2;
  const K_ROLE_WITH_NAME_SCORE = 100;
  const K_PLACEHOLDER_SCORE = 120;
  const K_LABEL_SCORE = 140;
  const K_ALT_TEXT_SCORE = 160;
  const K_TEXT_SCORE = 180;
  const K_TITLE_SCORE = 200;
  const K_TEXT_SCORE_REGEX = 250;
  const K_CSS_ID_SCORE = 500;
  const K_ROLE_WITHOUT_NAME_SCORE = 510;
  const K_CSS_INPUT_TYPE_NAME_SCORE = 520;
  const K_CSS_TAG_NAME_SCORE = 530;
  const K_NTH_SCORE = 10000;
  const K_CSS_FALLBACK_SCORE = 10000000;
  
  const K_EXACT_PENALTY = 10;
  
  // ========== GUID 检测（移植自 Codegen）==========
  function isGuidLike(id) {
    if (!id) return true;
    let lastCharacterType = undefined;
    let transitionCount = 0;
    for (let i = 0; i < id.length; ++i) {
      const c = id[i];
      if (c === '-' || c === '_') continue;
      let characterType;
      if (c >= 'a' && c <= 'z') characterType = 'lower';
      else if (c >= 'A' && c <= 'Z') characterType = 'upper';
      else if (c >= '0' && c <= '9') characterType = 'digit';
      else characterType = 'other';
      
      if (characterType === 'lower' && lastCharacterType === 'upper') {
        lastCharacterType = characterType;
        continue;
      }
      if (lastCharacterType && lastCharacterType !== characterType)
        ++transitionCount;
      lastCharacterType = characterType;
    }
    return transitionCount >= id.length / 4;
  }
  
  // ========== 获取 ARIA 角色 ==========
  function getAriaRole(element) {
    const explicitRole = element.getAttribute('role');
    if (explicitRole) return explicitRole;
    
    // 隐式角色映射
    const tagName = element.tagName.toLowerCase();
    const type = element.getAttribute('type')?.toLowerCase();
    
    const implicitRoles = {
      'button': 'button',
      'a': element.hasAttribute('href') ? 'link' : null,
      'input': type === 'text' || !type ? 'textbox' : 
               type === 'password' ? 'textbox' :
               type === 'checkbox' ? 'checkbox' :
               type === 'radio' ? 'radio' :
               type === 'submit' ? 'button' :
               type === 'button' ? 'button' : null,
      'select': 'combobox',
      'textarea': 'textbox',
      'img': 'img',
      'h1': 'heading', 'h2': 'heading', 'h3': 'heading', 
      'h4': 'heading', 'h5': 'heading', 'h6': 'heading',
      'ul': 'list', 'ol': 'list', 'li': 'listitem',
      'nav': 'navigation',
      'main': 'main',
      'header': 'banner',
      'footer': 'contentinfo',
      'form': 'form',
      'table': 'table',
      'tr': 'row',
      'td': 'cell', 'th': 'columnheader',
      'dialog': 'dialog',
    };
    
    return implicitRoles[tagName] || null;
  }
  
  // ========== 获取可访问名称 ==========
  function getAccessibleName(element) {
    // 1. aria-label
    if (element.getAttribute('aria-label')) {
      return element.getAttribute('aria-label').trim();
    }
    
    // 2. aria-labelledby
    const labelledBy = element.getAttribute('aria-labelledby');
    if (labelledBy) {
      const labelElement = document.getElementById(labelledBy);
      if (labelElement) return labelElement.textContent.trim();
    }
    
    // 3. label for 关联
    if (element.id) {
      const label = document.querySelector(`label[for="${element.id}"]`);
      if (label) return label.textContent.trim();
    }
    
    // 4. 关联的 label 元素（包裹）
    if (element.tagName === 'INPUT' || element.tagName === 'SELECT' || element.tagName === 'TEXTAREA') {
      const parentLabel = element.closest('label');
      if (parentLabel) {
        const text = parentLabel.textContent.replace(element.value || '', '').trim();
        if (text) return text;
      }
    }
    
    // 5. placeholder
    if (element.getAttribute('placeholder')) {
      return element.getAttribute('placeholder').trim();
    }
    
    // 6. title
    if (element.getAttribute('title')) {
      return element.getAttribute('title').trim();
    }
    
    // 7. alt (for images)
    if (element.getAttribute('alt')) {
      return element.getAttribute('alt').trim();
    }
    
    // 8. 文本内容
    const text = element.textContent?.trim();
    if (text && text.length < 100) {
      return text;
    }
    
    // 9. value (for buttons/inputs)
    if (element.value && element.tagName === 'INPUT' && 
        ['button', 'submit', 'reset'].includes(element.type)) {
      return element.value.trim();
    }
    
    return null;
  }
  
  // ========== 文本变体生成 ==========
  function suitableTextAlternatives(text) {
    if (!text) return [];
    
    const result = [];
    const maxLength = 80;
    
    // 去掉开头的数字
    const leadingMatch = text.match(/^([\\d.,]+)[^.,\\w]/);
    if (leadingMatch) {
      const alt = text.substring(leadingMatch[1].length).trim();
      if (alt && alt.length <= maxLength) {
        result.push({ text: alt, scoreBonus: alt.length <= 30 ? 2 : 1 });
      }
    }
    
    // 去掉结尾的数字
    const trailingMatch = text.match(/[^.,\\w]([\\d.,]+)$/);
    if (trailingMatch) {
      const alt = text.substring(0, text.length - trailingMatch[1].length).trim();
      if (alt && alt.length <= maxLength) {
        result.push({ text: alt, scoreBonus: alt.length <= 30 ? 2 : 1 });
      }
    }
    
    // 完整文本
    if (text.length <= 30) {
      result.push({ text: text, scoreBonus: 0 });
    } else {
      // 截断版本
      if (text.length <= maxLength) {
        result.push({ text: text, scoreBonus: 0 });
      }
      result.push({ text: text.substring(0, 30), scoreBonus: 1 });
    }
    
    return result.filter(r => r.text);
  }
  
  // ========== 生成选择器 ==========
  function generateSelector(element) {
    const candidates = [];
    
    // 1. data-testid（最优）
    const testId = element.getAttribute('data-testid');
    if (testId) {
      const count = document.querySelectorAll(`[data-testid="${testId}"]`).length;
      candidates.push({
        engine: 'getByTestId',
        selector: `getByTestId('${testId}')`,
        score: count === 1 ? K_TEST_ID_SCORE : K_TEST_ID_SCORE + K_NTH_SCORE,
        unique: count === 1,
        matchCount: count
      });
    }
    
    // 2. 其他 data-test* 属性
    for (const attr of ['data-test-id', 'data-test']) {
      const value = element.getAttribute(attr);
      if (value) {
        const count = document.querySelectorAll(`[${attr}="${value}"]`).length;
        candidates.push({
          engine: 'css',
          selector: `[${attr}="${value}"]`,
          score: count === 1 ? K_OTHER_TEST_ID_SCORE : K_OTHER_TEST_ID_SCORE + K_NTH_SCORE,
          unique: count === 1,
          matchCount: count
        });
      }
    }
    
    // 3. role + name
    const role = getAriaRole(element);
    const name = getAccessibleName(element);
    if (role && name) {
      const alternatives = suitableTextAlternatives(name);
      for (const alt of alternatives) {
        const score = K_ROLE_WITH_NAME_SCORE - alt.scoreBonus * 5;
        // 验证唯一性
        const roleElements = [...document.querySelectorAll(`[role="${role}"], ${role}`)];
        const matching = roleElements.filter(el => {
          const elName = getAccessibleName(el);
          return elName && elName.includes(alt.text);
        });
        candidates.push({
          engine: 'getByRole',
          selector: `getByRole('${role}', { name: '${alt.text.replace(/'/g, "\\\\'")}' })`,
          score: matching.length === 1 ? score : score + K_NTH_SCORE,
          unique: matching.length === 1,
          matchCount: matching.length
        });
      }
    }
    
    // 4. placeholder
    const placeholder = element.getAttribute('placeholder');
    if (placeholder) {
      const alternatives = suitableTextAlternatives(placeholder);
      for (const alt of alternatives) {
        const score = K_PLACEHOLDER_SCORE - alt.scoreBonus * 5;
        const count = document.querySelectorAll(`[placeholder*="${alt.text}"]`).length;
        candidates.push({
          engine: 'getByPlaceholder',
          selector: `getByPlaceholder('${alt.text.replace(/'/g, "\\\\'")}')`,
          score: count === 1 ? score : score + K_NTH_SCORE,
          unique: count === 1,
          matchCount: count
        });
      }
    }
    
    // 5. label
    if (name && !element.getAttribute('aria-label')) {
      const count = document.querySelectorAll(`label[for="${element.id}"]`).length || 
                    (element.closest('label') ? 1 : 0);
      if (count > 0) {
        candidates.push({
          engine: 'getByLabel',
          selector: `getByLabel('${name.replace(/'/g, "\\\\'")}')`,
          score: count === 1 ? K_LABEL_SCORE : K_LABEL_SCORE + K_NTH_SCORE,
          unique: count === 1,
          matchCount: count
        });
      }
    }
    
    // 6. ID（检查是否动态）
    const id = element.getAttribute('id');
    if (id && !isGuidLike(id)) {
      const count = document.querySelectorAll(`#${CSS.escape(id)}`).length;
      candidates.push({
        engine: 'css',
        selector: `#${id}`,
        score: count === 1 ? K_CSS_ID_SCORE : K_CSS_ID_SCORE + K_NTH_SCORE,
        unique: count === 1,
        matchCount: count
      });
    }
    
    // 7. name 属性
    const nameAttr = element.getAttribute('name');
    if (nameAttr) {
      const count = document.querySelectorAll(`[name="${nameAttr}"]`).length;
      candidates.push({
        engine: 'css',
        selector: `[name="${nameAttr}"]`,
        score: count === 1 ? K_CSS_INPUT_TYPE_NAME_SCORE : K_CSS_INPUT_TYPE_NAME_SCORE + K_NTH_SCORE,
        unique: count === 1,
        matchCount: count
      });
    }
    
    // 8. type 属性
    const type = element.getAttribute('type');
    if (type && ['password', 'email', 'text', 'submit', 'button'].includes(type)) {
      const count = document.querySelectorAll(`input[type="${type}"]`).length;
      candidates.push({
        engine: 'css',
        selector: `input[type="${type}"]`,
        score: count === 1 ? K_CSS_INPUT_TYPE_NAME_SCORE : K_CSS_INPUT_TYPE_NAME_SCORE + K_NTH_SCORE,
        unique: count === 1,
        matchCount: count
      });
    }
    
    // 9. 遍历父元素链
    let parent = element.parentElement;
    let depth = 0;
    const parentPath = [];
    while (parent && parent !== document.body && depth < 5) {
      parentPath.push({
        tag: parent.tagName.toLowerCase(),
        id: parent.id,
        className: parent.className?.toString?.()?.split(' ')[0],
        role: getAriaRole(parent)
      });
      parent = parent.parentElement;
      depth++;
    }
    
    // 按分数排序
    candidates.sort((a, b) => a.score - b.score);
    
    return {
      candidates: candidates.slice(0, 10),
      parentPath: parentPath,
      elementInfo: {
        tag: element.tagName.toLowerCase(),
        id: element.id,
        name: nameAttr,
        className: element.className?.toString?.(),
        role: role,
        ariaLabel: element.getAttribute('aria-label'),
        placeholder: placeholder,
        textContent: element.textContent?.substring(0, 100)
      }
    };
  }
  
  // 执行生成
  const element = arguments[0];
  if (!element) return { error: 'Element is null' };
  return generateSelector(element);
})();
"""
    
    def _generate_selector_in_browser(self, ref: str) -> Optional[Dict]:
        """
        在浏览器端生成选择器（通过 browser_evaluate 执行）
        
        优势：
        1. 实时验证选择器唯一性
        2. 遍历父元素链
        3. 获取计算后的 ARIA 信息
        
        Args:
            ref: 元素引用（如 e45）
            
        Returns:
            {
              'candidates': [
                {
                  'engine': 'getByTestId',
                  'selector': "getByTestId('submit')",
                  'score': 1,
                  'unique': True,
                  'matchCount': 1
                },
                ...
              ],
              'parentPath': [...],
              'elementInfo': {...}
            }
        """
        logs.info(f"[BrowserSelector] 🚀 开始浏览器端选择器生成, ref={ref}")
        
        # 从快照获取元素信息，构造定位方式
        element_info = self.get_semantic_info(ref)
        if not element_info:
            logs.warning(f"[BrowserSelector] ❌ ref={ref} 不在快照中，无法进行浏览器端生成")
            return None
        
        logs.debug(f"[BrowserSelector] 📋 元素信息: role={element_info.get('role')}, "
                   f"name={element_info.get('name')}, type={element_info.get('type')}")
        
        # 获取元素的原始 HTML 属性
        html_attrs = self.get_html_attrs_for_ref(ref)
        if html_attrs:
            logs.debug(f"[BrowserSelector] 📄 HTML 属性: {list(html_attrs.keys())}")
        else:
            logs.debug(f"[BrowserSelector] ⚠️ 无 HTML 属性映射")
        
        # 构造查找元素的条件
        conditions = []
        
        # 1. 通过 data-testid 查找
        testid = element_info.get('data-testid') or (html_attrs.get('data-testid') if html_attrs else None)
        if testid:
            conditions.append(f'[data-testid="{testid}"]')
            logs.debug(f"[BrowserSelector] ✅ 添加条件: [data-testid=\"{testid}\"]")
        
        # 2. 通过 id 查找
        elem_id = (html_attrs.get('id') if html_attrs else None) or element_info.get('id')
        if elem_id and not self._is_guid_like(elem_id):
            conditions.append(f'#{elem_id}')
            logs.debug(f"[BrowserSelector] ✅ 添加条件: #{elem_id}")
        elif elem_id:
            logs.debug(f"[BrowserSelector] ⏭️ 跳过动态 ID: {elem_id}")
        
        # 3. 通过 name 查找
        name_attr = (html_attrs.get('name') if html_attrs else None)
        if name_attr:
            conditions.append(f'[name="{name_attr}"]')
            logs.debug(f"[BrowserSelector] ✅ 添加条件: [name=\"{name_attr}\"]")
        
        # 4. 通过 role + text 查找（最后手段）
        role = element_info.get('role') or element_info.get('type')
        text = element_info.get('name') or element_info.get('text')
        if role and text:
            conditions.append(f'[role="{role}"]')
            logs.debug(f"[BrowserSelector] ✅ 添加条件: [role=\"{role}\"]")
        
        if not conditions:
            logs.warning(f"[BrowserSelector] ❌ 无法构造查找条件 for ref={ref}")
            return None
        
        logs.info(f"[BrowserSelector] 📋 构造了 {len(conditions)} 个查找条件: {conditions}")
        
        # 返回需要的信息（供外部调用 browser_evaluate）
        result = {
            'ref': ref,
            'conditions': conditions,
            'script': self.BROWSER_SELECTOR_SCRIPT,
            'element_info': element_info
        }
        
        logs.info(f"[BrowserSelector] ✅ 浏览器端生成参数准备完成")
        return result
    
    def _merge_browser_candidates(
        self, 
        browser_result: Dict, 
        local_candidates: List[Tuple[str, int]], 
        action: str, 
        value: str = None
    ) -> List[Tuple[str, int, str, bool]]:
        """
        合并浏览器端和本地候选选择器
        
        Args:
            browser_result: 浏览器端返回的结果
            local_candidates: 本地生成的候选 [(selector, score), ...]
            action: 操作类型
            value: 填充值
            
        Returns:
            [(selector, score, source, unique), ...] 按分数升序排序
        """
        logs.info(f"[MergeCandidates] 🔄 开始合并候选选择器")
        logs.debug(f"[MergeCandidates] 📥 浏览器端候选数: {len(browser_result.get('candidates', [])) if browser_result else 0}")
        logs.debug(f"[MergeCandidates] 📥 本地候选数: {len(local_candidates)}")
        
        all_candidates = []
        seen_selectors = set()
        
        def escape(s):
            return s.replace("'", "\\'") if s else s
        
        safe_value = escape(value) if value else ''
        
        # 1. 处理浏览器端候选（优先）
        browser_count = 0
        if browser_result and 'candidates' in browser_result:
            for c in browser_result['candidates']:
                selector = c['selector']
                score = c['score']
                unique = c.get('unique', False)
                
                # 生成完整的操作代码
                if action == 'click':
                    full_selector = f"await page.{selector}.click();"
                elif action == 'fill':
                    full_selector = f"await page.{selector}.fill('{safe_value}');"
                elif action == 'hover':
                    full_selector = f"await page.{selector}.hover();"
                else:
                    full_selector = f"await page.{selector};"
                
                if selector not in seen_selectors:
                    seen_selectors.add(selector)
                    all_candidates.append((full_selector, score, 'browser', unique))
                    browser_count += 1
                    logs.debug(f"[MergeCandidates] ✅ 浏览器端: {selector} (分数:{score}, 唯一:{unique})")
        
        logs.info(f"[MergeCandidates] 📊 浏览器端添加 {browser_count} 个候选")
        
        # 2. 处理本地候选（兜底）
        local_count = 0
        for selector, score in local_candidates:
            # 提取选择器部分（去除 await page. 和操作部分）
            selector_match = re.search(r'page\.(getBy\w+|locator)\(([^)]+)\)', selector)
            if selector_match:
                selector_key = selector_match.group(0)
            else:
                selector_key = selector
            
            if selector_key not in seen_selectors:
                seen_selectors.add(selector_key)
                all_candidates.append((selector, score, 'local', None))
                local_count += 1
                logs.debug(f"[MergeCandidates] ✅ 本地: {selector[:50]}... (分数:{score})")
        
        logs.info(f"[MergeCandidates] 📊 本地添加 {local_count} 个候选")
        
        # 按分数升序排序
        all_candidates.sort(key=lambda x: x[1])
        
        # 显示排序后的前5个
        logs.info(f"[MergeCandidates] 📋 合并后共 {len(all_candidates)} 个候选，前5个:")
        for i, (sel, score, src, unique) in enumerate(all_candidates[:5]):
            unique_mark = "✓唯一" if unique else ("✗重复" if unique is False else "")
            logs.info(f"  {i+1}. [{score}] {sel[:50]}... ({src}) {unique_mark}")
        
        return all_candidates
    
    def _generate_semantic_selector_realtime(
        self, 
        ref: str, 
        action: str, 
        value: str = None, 
        max_retries: int = 2,
        browser_result: Dict = None
    ) -> Optional[str]:
        """
        实时生成语义化选择器（在操作执行前调用）
        
        新流程（浏览器端优先 + 规则兜底 + AI 选择）：
        1. 如果有浏览器端结果，优先使用（包含唯一性验证）
        2. 规则系统生成本地候选选择器（兜底）
        3. 合并候选列表
        4. AI 从候选中选择最佳选择器
        5. 最终验证：确保无 ref 标签
        
        优势：
        - 浏览器端实时验证唯一性（接近 Codegen 能力）
        - 规则系统保证候选都是有效的语法
        - AI 只需要做"选择题"而不是"填空题"
        - 双重验证确保输出质量
        
        Args:
            ref: 元素引用
            action: 操作类型（click, fill, hover, select）
            value: 填充的值（对于 fill 操作）
            max_retries: 最大重试次数（默认 2 次）
            browser_result: 浏览器端选择器生成结果（可选）
            
        Returns:
            语义化选择器代码，失败返回 None
        """
        # 🚀 入口日志
        logs.info(f"[RealtimeSelector] 🚀 开始生成选择器: ref={ref}, action={action}, "
                  f"has_browser_result={browser_result is not None}")
        
        # 从快照获取元素信息
        element_info = self.get_semantic_info(ref)
        if not element_info:
            logs.warning(f"[RealtimeSelector] ❌ ref={ref} 不在快照中，跳过生成")
            return None
        
        logs.debug(f"[RealtimeSelector] 📋 元素信息: role={element_info.get('role')}, "
                   f"name={element_info.get('name')}, type={element_info.get('type')}")
        
        # 构建快照上下文
        snapshot_context = self._build_snapshot_context_for_ai(ref)
        if not snapshot_context:
            logs.warning(f"[RealtimeSelector] ❌ ref={ref} 无快照上下文，跳过生成")
            return None
        
        # 🚀 新流程 Step 1: 规则系统生成多个候选选择器
        logs.info(f"[RealtimeSelector] 📝 Step 1: 生成本地候选选择器...")
        local_candidates = self._generate_all_candidate_selectors(element_info, action, value)
        logs.info(f"[RealtimeSelector] 📊 本地生成 {len(local_candidates)} 个候选")
        
        # 🚀 新流程 Step 2: 合并浏览器端和本地候选
        logs.info(f"[RealtimeSelector] 📝 Step 2: 合并候选...")
        if browser_result:
            candidates = self._merge_browser_candidates(browser_result, local_candidates, action, value)
            logs.info(f"[RealtimeSelector] 📋 合并后 {len(candidates)} 个候选选择器（浏览器端 + 本地）:")
        else:
            # 转换本地候选格式
            candidates = [(s, score, 'local', None) for s, score in local_candidates]
            logs.info(f"[RealtimeSelector] 📋 本地生成 {len(candidates)} 个候选选择器（无浏览器端结果）:")
        
        if not candidates:
            logs.warning(f"[RealtimeSelector] ❌ 未生成任何候选选择器")
            self._selector_stats['ref'] += 1
            return None
        
        for i, (selector, score, source, unique) in enumerate(candidates[:10]):
            unique_mark = "✓唯一" if unique else ("✗重复" if unique is False else "")
            logs.info(f"  {i+1}. [{score}] {selector[:60]}... ({source}) {unique_mark}")
        
        # 🚀 P1-003: 短路优化 — 高质量候选直接使用，不调用 AI
        # 分数 <= 200（getByTestId/getByRole+name/getByPlaceholder/getByLabel/getByText/title 级别）
        best_candidate_score = candidates[0][1]
        best_candidate_selector = candidates[0][0]
        best_candidate_unique = candidates[0][3]
        
        # 条件：分数足够低 + 不包含 ref + 唯一性验证通过（或未验证）
        if (best_candidate_score <= 200 
            and not self._contains_ref_selector(best_candidate_selector)
            and best_candidate_unique is not False):  # None（未验证）或 True 都可以
            logs.info(f"[RealtimeSelector] ⚡ 短路：最佳候选分数={best_candidate_score}，直接使用（跳过 AI）")
            self._selector_stats['semantic'] += 1
            return best_candidate_selector
        
        # 🚀 新流程 Step 3: AI 从候选中选择最佳
        logs.info(f"[RealtimeSelector] 📝 Step 3: AI 选择最佳选择器（最佳候选分数={best_candidate_score}）...")
        best_selector = self._ai_select_best_selector(
            candidates, element_info, action, value, snapshot_context, browser_result
        )
        
        if best_selector:
            # 🚀 新流程 Step 4: 最终验证 - 确保无 ref 标签
            logs.info(f"[RealtimeSelector] 📝 Step 4: 最终验证...")
            if self._contains_ref_selector(best_selector):
                logs.error(f"[RealtimeSelector] 🚨 最终选择器仍包含 ref，拒绝使用: {best_selector}")
                self._selector_stats['ref'] += 1
                return None
            
            logs.info(f"[RealtimeSelector] ✅ 最终选择: {best_selector}")
            self._selector_stats['semantic'] += 1
            return best_selector
        
        # AI 选择失败，返回规则系统的最佳候选
        logs.warning(f"[RealtimeSelector] ⚠️ AI 选择失败，使用回退方案")
        if candidates:
            best_fallback = candidates[0][0]
            # 再次验证
            if self._contains_ref_selector(best_fallback):
                logs.error(f"[RealtimeSelector] 🚨 回退选择器包含 ref，拒绝使用: {best_fallback}")
                self._selector_stats['ref'] += 1
                return None
            
            logs.info(f"[RealtimeSelector] 🔄 使用规则最佳: {best_fallback}")
            self._selector_stats['semantic'] += 1
            return best_fallback
        
        logs.error(f"[RealtimeSelector] ❌ 无可用候选选择器")
        self._selector_stats['ref'] += 1
        return None
    
    def _generate_all_candidate_selectors(self, element_info: dict, action: str, value: str = None) -> List[Tuple[str, int]]:
        """
        使用规则系统生成所有可能的候选选择器
        
        按优先级生成，返回 [(选择器代码, 分数), ...]
        
        🚀 使用 Codegen 风格的分数体系：分数越低越好！
        - 分数范围：1（最优）到 10000000（最差）
        - 分数越低代表选择器越稳定、越可靠
        
        🚀 新增：优先使用原始 HTML 中提取的属性
        🚨 严格管理 getByLabel：
        - 只有当 DOM 中存在 <label for="xxx"> 关联时，才生成 getByLabel 候选
        - 快照中的 implicit_label 只是显示文本，不代表 HTML 有语义关联
        
        Args:
            element_info: 元素信息
            action: 操作类型
            value: 填充值
            
        Returns:
            候选选择器列表（按分数升序，分数越低越好）
        """
        candidates = []
        
        def escape(s):
            return s.replace("'", "\\'") if s else s
        
        role = element_info.get('role')
        name = element_info.get('name')
        text = element_info.get('text')
        elem_type = element_info.get('type')
        implicit_label = element_info.get('implicit_label')
        placeholder = element_info.get('placeholder')
        aria_label = element_info.get('aria-label')
        data_testid = element_info.get('data-testid')
        element_ref = element_info.get('ref', '')
        
        safe_value = escape(value) if value else ''
        
        # 🚀 新增：获取 HTML 属性（如果有原始 HTML）
        html_attrs = self.get_html_attrs_for_ref(element_ref) if element_ref else None
        
        if html_attrs:
            logs.info(f"[SemanticSelectorMiddleware] 🎯 找到 HTML 属性映射 for ref={element_ref}: {list(html_attrs.keys())}")
        
        # ========== 🚀 注入 JS 端候选选择器（带唯一性验证结果）==========
        js_candidates = element_info.get('_js_selector_candidates', [])
        if js_candidates:
            js_injected = 0
            for jc in js_candidates:
                jc_code = jc.get('code', '')
                jc_score = jc.get('score', K_CSS_FALLBACK_SCORE)
                jc_unique = jc.get('unique')
                jc_match_count = jc.get('matchCount')
                
                if not jc_code:
                    continue
                
                # 非唯一选择器已在 JS 端被加了 5000+ 分，这里直接使用 JS 端的分数
                # 构建完整操作代码
                if action == 'click':
                    full_code = f"await {jc_code}.click();"
                elif action == 'fill':
                    full_code = f"await {jc_code}.fill('{safe_value}');"
                elif action == 'hover':
                    full_code = f"await {jc_code}.hover();"
                else:
                    full_code = f"await {jc_code};"
                
                candidates.append((full_code, jc_score))
                js_injected += 1
            
            if js_injected > 0:
                logs.info(f"[SemanticSelectorMiddleware] 🚀 注入 {js_injected} 个 JS 端候选（含唯一性验证）")
        
        # ========== 优先使用 HTML 属性（Codegen 分数体系）==========
        if html_attrs:
            # 1️⃣ data-testid 选择器（测试专用，分数=1，最优）
            html_testid = html_attrs.get('data-testid') or html_attrs.get('data-test-id') or html_attrs.get('data-test')
            if html_testid:
                if action == 'click':
                    candidates.append((f"await page.getByTestId('{html_testid}').click();", K_TEST_ID_SCORE))
                elif action == 'fill':
                    candidates.append((f"await page.getByTestId('{html_testid}').fill('{safe_value}');", K_TEST_ID_SCORE))
                logs.info(f"[SemanticSelectorMiddleware] ✅ 使用 data-testid 选择器 (score={K_TEST_ID_SCORE}): {html_testid}")
            
            # 2️⃣ ID 选择器（需检查是否动态生成，分数=500）
            html_id = html_attrs.get('id')
            if html_id:
                # 使用 Codegen 的 GUID 检测算法
                if not self._is_guid_like(html_id):
                    if action == 'click':
                        candidates.append((f"await page.locator('#{html_id}').click();", K_CSS_ID_SCORE))
                    elif action == 'fill':
                        candidates.append((f"await page.locator('#{html_id}').fill('{safe_value}');", K_CSS_ID_SCORE))
                    logs.info(f"[SemanticSelectorMiddleware] ✅ 使用 ID 选择器 (score={K_CSS_ID_SCORE}): #{html_id}")
            
            # 3️⃣ name 属性选择器（表单元素常用，分数=520）
            html_name = html_attrs.get('name')
            if html_name:
                if action == 'click':
                    candidates.append((f"await page.locator('[name=\"{html_name}\"]').click();", K_CSS_INPUT_TYPE_NAME_SCORE))
                elif action == 'fill':
                    candidates.append((f"await page.locator('[name=\"{html_name}\"]').fill('{safe_value}');", K_CSS_INPUT_TYPE_NAME_SCORE))
                logs.info(f"[SemanticSelectorMiddleware] ✅ 使用 name 选择器 (score={K_CSS_INPUT_TYPE_NAME_SCORE}): [name=\"{html_name}\"]")
            
            # 4️⃣ type 属性选择器（分数=520+1）- 仅 password 类型可直接使用（唯一性高）
            html_type = html_attrs.get('type')
            if html_type and action == 'fill':
                if html_type == 'password':
                    # password 类型通常页面唯一，可以直接使用
                    candidates.append((f"await page.locator('input[type=\"password\"]').fill('{safe_value}');", K_CSS_INPUT_TYPE_NAME_SCORE + 1))
                    logs.info(f"[SemanticSelectorMiddleware] ✅ 使用 type 选择器: input[type=\"password\"]")
                # 其他 type（text/email 等）不生成 .first() 候选，避免错误定位
                # 这些场景应由 getByLabel/getByPlaceholder 等语义选择器覆盖
        
        # ========== 快照属性（备选逻辑）==========
        
        # 1️⃣ getByRole + name（语义化选择器，分数=100）
        if role and (name or text):
            safe_name = escape(name or text)
            if role == 'button':
                if action == 'click':
                    candidates.append((f"await page.getByRole('button', {{ name: '{safe_name}' }}).click();", K_ROLE_WITH_NAME_SCORE))
            elif role == 'link':
                if action == 'click':
                    candidates.append((f"await page.getByRole('link', {{ name: '{safe_name}' }}).click();", K_ROLE_WITH_NAME_SCORE))
        
        # 2️⃣ getByTestId（快照中的 data-testid，分数=1）
        if data_testid:
            safe_testid = escape(data_testid)
            if action == 'click':
                candidates.append((f"await page.getByTestId('{safe_testid}').click();", K_TEST_ID_SCORE))
            elif action == 'fill':
                candidates.append((f"await page.getByTestId('{safe_testid}').fill('{safe_value}');", K_TEST_ID_SCORE))
        
        # 3️⃣ CSS type 属性选择器（分数=520）
        if action == 'fill':
            # 密码框（通常页面唯一，可直接使用）
            if implicit_label and 'password' in implicit_label.lower():
                candidates.append((f"await page.locator('input[type=\"password\"]').fill('{safe_value}');", K_CSS_INPUT_TYPE_NAME_SCORE))
            # 用户名/邮箱框 - 使用 getByLabel 替代 .first()
            elif implicit_label and ('user' in implicit_label.lower() or 'name' in implicit_label.lower() or '邮箱' in implicit_label or 'email' in implicit_label.lower()):
                safe_label = escape(implicit_label)
                candidates.append((f"await page.getByLabel('{safe_label}').fill('{safe_value}');", K_LABEL_SCORE))
            # 通用文本框 - 使用 implicit_label 或 placeholder 替代 .first()
            elif elem_type == 'textbox' or role == 'textbox':
                if implicit_label:
                    safe_label = escape(implicit_label)
                    candidates.append((f"await page.getByLabel('{safe_label}').fill('{safe_value}');", K_LABEL_SCORE))
                elif placeholder:
                    safe_ph = escape(placeholder)
                    candidates.append((f"await page.getByPlaceholder('{safe_ph}').fill('{safe_value}');", K_PLACEHOLDER_SCORE))
        
        # 4️⃣ getByLabel（分数=140，严格管理）
        if elem_type in ['textbox', 'combobox', 'checkbox', 'radio'] or role in ['textbox', 'combobox', 'checkbox', 'radio']:
            # 首先检查是否有 aria-label（HTML 属性，可靠）
            if aria_label:
                safe_aria = escape(aria_label)
                if action == 'fill':
                    candidates.append((f"await page.getByLabel('{safe_aria}').fill('{safe_value}');", K_LABEL_SCORE))
                elif action == 'click':
                    candidates.append((f"await page.getByLabel('{safe_aria}').click();", K_LABEL_SCORE))
            
            # 然后检查原始 DOM 中是否有 label for 关联
            elif implicit_label and self._label_for_cache:
                for input_id, label_text in self._label_for_cache.items():
                    if (implicit_label.lower() in label_text.lower() or 
                        label_text.lower() in implicit_label.lower()):
                        safe_label = escape(label_text)
                        if action == 'fill':
                            candidates.append((f"await page.getByLabel('{safe_label}').fill('{safe_value}');", K_LABEL_SCORE))
                            logs.info(f"[SemanticSelectorMiddleware] ✅ getByLabel 有 DOM 关联: label for='{input_id}' -> '{label_text}'")
                        elif action == 'click':
                            candidates.append((f"await page.getByLabel('{safe_label}').click();", K_LABEL_SCORE))
                        break
            
            # 如果没有 DOM 关联，记录警告
            elif implicit_label and not self._label_for_cache and not aria_label:
                logs.debug(f"[SemanticSelectorMiddleware] ⚠️ implicit_label='{implicit_label}' 但无 DOM label for 关联，跳过 getByLabel")
        
        # 5️⃣ getByPlaceholder（分数=120）
        if placeholder and action == 'fill':
            safe_placeholder = escape(placeholder)
            candidates.append((f"await page.getByPlaceholder('{safe_placeholder}').fill('{safe_value}');", K_PLACEHOLDER_SCORE))
        
        # 6️⃣ getByText（分数=180）
        # 🚀 增强判断：是否需要精确匹配
        # - 纯数字（如页码 "2"）- 必须精确匹配，避免匹配到 "22", "20/page"
        # - 短文本（< 3字符）- 建议精确匹配
        # - 分页场景 - 精确匹配页码
        if (name or text) and action in ['click', 'fill']:
            raw_text = name or text
            safe_text = escape(raw_text)
            
            # 判断是否需要精确匹配
            is_numeric = raw_text.isdigit() or bool(re.match(r'^\d+$', raw_text))
            is_short = len(raw_text) < 3
            raw_line_lower = element_info.get('raw_line', '').lower()
            is_pagination_context = 'pagination' in raw_line_lower or 'page' in raw_line_lower
            
            # 🚀 新增：分页场景优先使用 aria-label
            if is_pagination_context and is_numeric:
                # 分页元素通常有 aria-label="page 2" 属性
                if action == 'click':
                    candidates.append((f"await page.locator('[aria-label=\"page {safe_text}\"]').click();", K_TEST_ID_SCORE))
                    logs.info(f"[SemanticSelectorMiddleware] ✅ 使用 aria-label 选择器: [aria-label=\"page {safe_text}\"]")
                # 同时也添加正则精确匹配作为备选
                candidates.append((f"await page.getByText(/^{safe_text}$/).click();", K_TEXT_SCORE))
                logs.info(f"[SemanticSelectorMiddleware] ✅ 使用精确匹配 getByText(/^{safe_text}$/) - 避免部分匹配")
            elif is_numeric or is_short:
                # 🔢 精确匹配：使用正则表达式，避免部分匹配
                # 例如：getByText('2') 会匹配 "2", "22", "20/page"
                # 改用 getByText(/^2$/) 只匹配精确的 "2"
                if action == 'click':
                    candidates.append((f"await page.getByText(/^{safe_text}$/).click();", K_TEXT_SCORE))
                else:
                    candidates.append((f"await page.getByText(/^{safe_text}$/).fill('{safe_value}');", K_TEXT_SCORE))
                logs.info(f"[SemanticSelectorMiddleware] ✅ 使用精确匹配 getByText(/^{safe_text}$/) - 避免部分匹配")
            else:
                # 使用 exact: true 精确匹配，替代 .first() 避免错误定位
                if action == 'click':
                    candidates.append((f"await page.getByText('{safe_text}', {{ exact: true }}).click();", K_TEXT_SCORE))
                else:
                    candidates.append((f"await page.getByText('{safe_text}', {{ exact: true }}).fill('{safe_value}');", K_TEXT_SCORE))
        
        # 🚀 6.5️⃣ 组合选择器：role + has-text（Codegen 风格）
        # 当有 role 但没有精确 name 时，使用组合选择器
        if role and text and len(text) <= 80:
            safe_text = escape(text)
            # 使用正则精确匹配
            if action == 'click':
                # role + has-text 组合
                candidates.append((f"await page.getByRole('{role}').filter({{ hasText: /^{safe_text}$/ }}).click();", K_TEXT_SCORE_REGEX))
            elif action == 'fill':
                candidates.append((f"await page.getByRole('{role}').filter({{ hasText: /^{safe_text}$/ }}).fill('{safe_value}');", K_TEXT_SCORE_REGEX))
        
        # 7️⃣ role 无 name（分数=510）- 不生成 .first()，改用 TODO 标记
        # 无 name 的 role 选择器在多元素页面必定定位错误，跳过此候选
        
        # 🚀 7.5️⃣ generic_clickable 类型（自定义下拉框等，分数=520）
        # 这种元素通常是自定义组件，没有标准 role，需要通过隐式标签定位
        if role == 'generic_clickable' and action == 'click':
            # 优先使用隐式标签（从兄弟元素获取的标签）
            if implicit_label:
                safe_label = escape(implicit_label)
                # 方案1: 通过 form item 定位
                candidates.append((f"await page.locator('.el-form-item').filter({{ hasText: '{safe_label}' }}).locator('[cursor=pointer], .el-select, [role=\"combobox\"]').first().click();", K_CSS_INPUT_TYPE_NAME_SCORE))
                # 方案2: 通过文本定位父元素后找可点击元素
                candidates.append((f"await page.locator('.el-form-item').filter({{ hasText: '{safe_label}' }}).locator('[cursor=pointer]').first().click();", K_CSS_INPUT_TYPE_NAME_SCORE + 1))
                # 方案3: 使用 JavaScript 执行点击（终极备用）
                candidates.append((f"await page.evaluate(() => {{ const items = document.querySelectorAll('.el-form-item'); for (const item of items) {{ if (item.textContent.includes('{safe_label}')) {{ const clickable = item.querySelector('[cursor=pointer], .el-select'); if (clickable) {{ clickable.click(); break; }} }} }} }});", K_CSS_FALLBACK_SCORE))
                logs.info(f"[SemanticSelectorMiddleware] ✅ 生成 generic_clickable 选择器 for '{safe_label}'")
        
        # 8️⃣ 位置选择器 - 不再生成 .nth() 盲猜候选
        # 无上下文的 .nth(1) 在不同页面几乎必定定位错误，跳过
        
        # 9️⃣ CSS 回退选择器 - 使用 TODO 标记替代 .first() 盲猜
        if not candidates and elem_type in ['textbox', 'combobox', 'checkbox', 'radio']:
            if action == 'fill':
                desc = implicit_label or name or text or elem_type
                candidates.append((f"// ⚠️ TODO: 需要手动确认选择器 - 元素描述: {desc}\nawait page.getByRole('{role or elem_type}').fill('{safe_value}');", K_CSS_FALLBACK_SCORE))
        
        # 🚀 应用长度惩罚（Codegen 风格）
        candidates = self._apply_score_penalty_for_length(candidates)
        
        # 去重并按分数升序排序（分数越低越好）
        seen = set()
        unique_candidates = []
        for selector, score in candidates:
            if selector not in seen:
                seen.add(selector)
                unique_candidates.append((selector, score))
        
        unique_candidates.sort(key=lambda x: x[1])  # 升序排序
        return unique_candidates
    
    def _ai_select_best_selector(
        self, 
        candidates: List[Tuple], 
        element_info: dict, 
        action: str, 
        value: str, 
        snapshot_context: str,
        browser_result: Dict = None
    ) -> Optional[str]:
        """
        让 AI 从候选选择器中选择最佳的一个
        
        🚀 使用 Codegen 分数体系：分数越低越好！
        - 分数 1-10: 最优质选择器（data-testid, testId）
        - 分数 100-200: 语义化选择器（role, label, placeholder）
        - 分数 500-530: CSS 选择器（id, name, type）
        - 分数 10000+: 位置选择器（nth, first）- 应避免
        
        Args:
            candidates: 候选选择器列表，格式：
                        [(选择器, 分数, 来源, 是否唯一), ...] 或
                        [(选择器, 分数), ...]（兼容旧格式）
            element_info: 元素信息
            action: 操作类型
            value: 填充值
            snapshot_context: 快照上下文
            browser_result: 浏览器端结果（可选）
            
        Returns:
            最佳选择器代码，失败返回 None
        """
        if not candidates:
            return None
        
        try:
            from llms import get_default_model
            
            # 构建候选列表字符串（支持新旧格式）
            candidates_str_lines = []
            for i, item in enumerate(candidates):
                if len(item) >= 4:
                    selector, score, source, unique = item[:4]
                    unique_mark = "✅已验证唯一" if unique else ("⚠️可能重复" if unique is False else "")
                    source_mark = f"[{source}]" if source else ""
                    quality_mark = "⭐推荐" if score < 200 else ("⚠️较不稳定" if score > 500 else "")
                    candidates_str_lines.append(
                        f"{i+1}. {selector} (分数: {score}) {source_mark} {unique_mark} {quality_mark}"
                    )
                else:
                    selector, score = item[:2]
                    quality_mark = "⭐推荐" if score < 200 else ("⚠️较不稳定" if score > 500 else "")
                    candidates_str_lines.append(
                        f"{i+1}. {selector} (分数: {score}) {quality_mark}"
                    )
            
            candidates_str = "\n".join(candidates_str_lines)
            
            # 构建 Prompt
            prompt = f"""你是一个 Playwright 自动化测试专家。请从以下候选选择器中选择**最可靠**的一个。

## 🎯 目标元素信息
- 元素类型: {element_info.get('type', 'unknown')}
- 角色: {element_info.get('role', 'unknown')}
- 名称: {element_info.get('name', '')}
- 隐式标签: {element_info.get('implicit_label', '')}
- 操作: {action}
- 填充值: {value or 'N/A'}

## 📄 页面快照（局部）
```
{snapshot_context[:500]}
```

## 📋 候选选择器（按分数升序，分数越低越好）
{candidates_str}

## 📖 分数解读（Codegen 标准）
- **分数 1-10**: 最优质 ⭐（data-testid, testId）
- **分数 100-200**: 语义化 ✅（role, label, placeholder, text）
- **分数 500-530**: CSS 选择器 ⚠️（id, name, type）- 可能不稳定
- **分数 10000+**: 位置选择器 ❌（nth, first）- 应尽量避免

## ⚠️ 选择规则
1. **优先选择低分数选择器**（分数越低越稳定）
2. **优先选择已验证唯一的选择器**（✅已验证唯一）
3. **语义化选择器优先**（getByRole, getByLabel, getByTestId）
4. **避免位置选择器**（.first(), .nth()）除非没有其他选择

## 🚨 绝对禁止
- 绝对不要修改选择器内容
- 绝对不要返回带有 [ref="xxx"] 的选择器
- 只能从上面的候选中选择一个

## 输出格式
返回 JSON，包含选择的序号（1-{len(candidates)}）：
```json
{{"choice": 1, "reason": "选择理由"}}
```"""

            # 调用 LLM
            logs.info(f"[SemanticSelectorMiddleware] 🤖 AI 选择最佳选择器...")
            llm = get_default_model()
            response = llm.invoke(prompt)
            
            # 解析响应
            ai_response = response.content if hasattr(response, 'content') else str(response)
            logs.debug(f"[SemanticSelectorMiddleware] AI 选择响应: {ai_response[:200]}")
            
            # 提取选择
            import json
            
            # 尝试解析 JSON
            try:
                # 去除 markdown 代码块
                ai_response = ai_response.strip()
                if ai_response.startswith('```'):
                    ai_response = ai_response.split('\n', 1)[1]
                if ai_response.endswith('```'):
                    ai_response = ai_response.rsplit('\n', 1)[0]
                
                data = json.loads(ai_response)
                choice = data.get('choice', 1)
                reason = data.get('reason', '')
                
                # 验证选择范围
                if 1 <= choice <= len(candidates):
                    selected_selector = candidates[choice - 1][0]
                    selected_score = candidates[choice - 1][1]
                    logs.info(f"[SemanticSelectorMiddleware] ✅ AI 选择: #{choice} (分数={selected_score}) - {reason}")
                    return selected_selector
                else:
                    logs.warning(f"[SemanticSelectorMiddleware] AI 选择超出范围: {choice}")
                    
            except json.JSONDecodeError:
                # 尝试正则提取数字
                match = re.search(r'"choice"\s*:\s*(\d+)', ai_response)
                if match:
                    choice = int(match.group(1))
                    if 1 <= choice <= len(candidates):
                        return candidates[choice - 1][0]
            
            return None
            
        except Exception as e:
            logs.error(f"[SemanticSelectorMiddleware] AI 选择失败: {e}")
            return None
    
    def _contains_ref_selector(self, selector: str) -> bool:
        """
        检查选择器是否包含 ref 标签
        
        Args:
            selector: 选择器代码
            
        Returns:
            是否包含 ref
        """
        ref_patterns = [
            r'\[ref\s*=\s*["\'][^"\']*["\']\]',
            r'\[ref\s*=\s*\w+\]',
        ]
        for pattern in ref_patterns:
            if re.search(pattern, selector):
                return True
        return False
    
    def _generate_selector_by_rules(self, element_info: dict, action: str, value: str = None) -> Optional[str]:
        """
        使用规则系统生成选择器（当 AI 失败时的回退方案）
        
        规则优先级：
        1. getByRole + name（按钮、链接）
        2. getByLabel（表单元素）
        3. CSS 属性选择器（type, name, id）
        4. 位置选择器（first, nth）
        
        Args:
            element_info: 元素信息
            action: 操作类型
            value: 填充值
            
        Returns:
            选择器代码
        """
        def escape(s):
            return s.replace("'", "\\'") if s else s
        
        role = element_info.get('role')
        name = element_info.get('name')
        text = element_info.get('text')
        elem_type = element_info.get('type')
        implicit_label = element_info.get('implicit_label')
        placeholder = element_info.get('placeholder')
        
        # 规则1：按钮使用 getByRole
        if role == 'button' and (name or text):
            safe_name = escape(name or text)
            return f"await page.getByRole('button', {{ name: '{safe_name}' }}).click();"
        
        # 规则2：链接使用 getByRole
        if role == 'link' and (name or text):
            safe_name = escape(name or text)
            return f"await page.getByRole('link', {{ name: '{safe_name}' }}).click();"
        
        # 规则3：表单元素优先使用 getByLabel
        if elem_type in ['textbox', 'combobox', 'checkbox', 'radio'] or role in ['textbox', 'combobox', 'checkbox', 'radio']:
            label_text = implicit_label or name or text
            if label_text:
                safe_label = escape(label_text)
                if action == 'fill':
                    safe_value = escape(value) if value else ''
                    return f"await page.getByLabel('{safe_label}').fill('{safe_value}');"
                elif action == 'click':
                    return f"await page.getByLabel('{safe_label}').click();"
        
        # 规则4：textbox 使用 type 属性
        if elem_type == 'textbox' or role == 'textbox':
            if action == 'fill':
                safe_value = escape(value) if value else ''
                # 判断是否是密码（通过上下文）
                if implicit_label and 'password' in implicit_label.lower():
                    return f"await page.locator('input[type=\"password\"]').fill('{safe_value}');"
                # 非密码场景不使用 .first()，让后续规则（placeholder/getByText）处理
                # 跳过此规则
        
        # 规则5：使用 placeholder
        if placeholder and action == 'fill':
            safe_placeholder = escape(placeholder)
            safe_value = escape(value) if value else ''
            return f"await page.getByPlaceholder('{safe_placeholder}').fill('{safe_value}');"
        
        # 规则6：文本内容使用 getByText
        # 🚀 改进：使用 exact: true 精确匹配，替代 .first()
        if (name or text) and action == 'click':
            safe_text = escape(name or text)
            return f"await page.getByText('{safe_text}', {{ exact: true }}).click();"
        
        return None
    
    def _evaluate_selector_quality(self, selector: str) -> float:
        """
        评估选择器质量（0-1 分）
        
        基于 Codegen 分数体系归一化，确保与候选排序一致。
        使用对数缩放处理分数跨度（1 ~ 10000000）。
        
        Args:
            selector: 选择器代码
            
        Returns:
            质量分数（0-1）
        """
        import math
        
        # 检查是否包含无效选择器
        if '[ref=' in selector or '[ref="' in selector or "[ref='" in selector:
            return 0.0
        
        # 检查是否包含 jQuery 语法
        jquery_patterns = [':contains', ':eq(', ':first', ':last', ':button', ':checkbox', ':radio']
        for pattern in jquery_patterns:
            if pattern in selector:
                return 0.0
        
        # 识别选择器类型并映射到 Codegen 分数
        codegen_score = K_CSS_FALLBACK_SCORE  # 默认最差
        
        if 'getByTestId' in selector:
            codegen_score = K_TEST_ID_SCORE
        elif 'getByRole' in selector and 'name:' in selector:
            codegen_score = K_ROLE_WITH_NAME_SCORE
        elif 'getByLabel' in selector:
            codegen_score = K_LABEL_SCORE
        elif 'getByPlaceholder' in selector:
            codegen_score = K_PLACEHOLDER_SCORE
        elif 'getByText' in selector:
            codegen_score = K_TEXT_SCORE
        elif "type=\"password\"" in selector or "type='password'" in selector:
            codegen_score = K_CSS_INPUT_TYPE_NAME_SCORE
        elif "type=\"text\"" in selector or "type='text'" in selector:
            codegen_score = K_CSS_INPUT_TYPE_NAME_SCORE
        elif '.first()' in selector or '.nth(' in selector:
            codegen_score = K_NTH_SCORE
        elif 'locator(' in selector:
            # 区分 CSS ID vs 一般 CSS 选择器
            if "#" in selector:
                codegen_score = K_CSS_ID_SCORE
            elif '[name=' in selector:
                codegen_score = K_CSS_NAME_SCORE
            else:
                codegen_score = K_CSS_TAG_NAME_SCORE
        elif 'evaluate' in selector:
            codegen_score = K_CSS_FALLBACK_SCORE
        
        # 归一化到 0-1（使用对数缩放，因为分数跨度很大）
        max_log = math.log(K_CSS_FALLBACK_SCORE + 1)  # log(10000001) ≈ 16.1
        score_log = math.log(codegen_score + 1)
        quality = 1.0 - (score_log / max_log)
        
        return max(0.0, min(1.0, round(quality, 3)))
    
    def get_ai_generated_code(self, ref: str) -> Optional[str]:
        """
        获取 AI 实时生成的语义化代码（供 CodeCollector 调用）
        
        Args:
            ref: 元素引用
            
        Returns:
            AI 生成的语义化代码，不存在返回 None
        """
        return self._ai_generated_code.get(ref)
    
    def _build_snapshot_context_for_ai(self, target_ref: str, context_lines: int = 30) -> str:
        """
        为 AI 构建快照上下文（只包含目标元素附近的内容）
        
        优化：增加上下文行数，确保能看到完整的表单结构
        
        Args:
            target_ref: 目标元素 ref
            context_lines: 上下文行数（默认30行，确保能看到完整表单）
            
        Returns:
            快照片段
        """
        if not self._current_snapshot:
            return ""
        
        lines = self._current_snapshot.split('\n')
        target_line_idx = None
        
        # 找到目标元素的行号
        for i, line in enumerate(lines):
            if f"[ref={target_ref}]" in line:
                target_line_idx = i
                break
        
        if target_line_idx is None:
            # 没找到，返回整个快照（如果不太大）
            if len(lines) <= 100:
                return self._current_snapshot
            return ""
        
        # 取上下文（确保能看到前面的 label 元素）
        start = max(0, target_line_idx - context_lines)
        end = min(len(lines), target_line_idx + context_lines + 1)
        
        return '\n'.join(lines[start:end])
    
    def _build_ai_prompt(self, element_info: dict, action: str, value: str, snapshot_context: str) -> str:
        """
        构建 AI Prompt（优化版 - 考虑快照文本与 HTML 语义的差异）
        
        关键认知：
        - 快照中显示的 "Username:" 可能只是显示文本（generic 元素）
        - 不代表 HTML 中有 <label for="..."> 关联
        - getByLabel 只有在 HTML 有语义化 label 时才能工作
        
        Args:
            element_info: 元素信息
            action: 操作类型
            value: 填充值
            snapshot_context: 快照上下文
            
        Returns:
            完整的 prompt
        """
        # 操作描述
        action_desc = {
            'click': '点击',
            'fill': f'输入文本 "{value}"',
            'hover': '悬停',
            'select': f'选择选项 "{value}"'
        }.get(action, action)
        
        # 获取目标元素的 ref
        target_ref = element_info.get('ref', 'unknown')
        implicit_label = element_info.get('implicit_label', '')
        
        prompt = f"""你是一个 Playwright 自动化测试专家。请为指定元素生成**最可靠**的选择器。

## 🎯 目标元素
- **ref: {target_ref}** ← 这是你要定位的元素（注意：ref 只是快照中的临时标识，不能用于选择器！）
- 元素类型: {element_info.get('type', 'unknown')}
- 角色: {element_info.get('role', 'unknown')}
- 操作: {action_desc}

## 📄 页面快照
```
{snapshot_context}
```

## 🚨🚨🚨 绝对禁止的选择器（极其严重！）

### ❌ ref= 选择器 - 每次页面刷新都会变化，绝对不能用！
```javascript
// ❌ 错误示例（绝对禁止！）
page.locator('[ref="e7"]')       // ref 是临时引用，下次刷新就变了！
page.locator('[ref="e123"]')     // 完全不可靠！
page.locator('[ref=e7]')         // 错误！

// ✅ 正确做法：使用语义化选择器
page.getByRole('textbox', {{ name: 'Username' }})  // 用户名输入框
page.getByLabel('Username')                  // 如果有 label 关联
page.getByPlaceholder('Enter username')      // 如果有 placeholder
```

**为什么 ref= 不能用？**
- ref 是 Playwright 快照中的临时元素标识
- 每次页面导航、刷新、DOM 变化，ref 都会重新生成
- e7 这次是用户名输入框，下次可能是其他元素

## 🚫 禁止使用 jQuery 语法

**以下语法在 Playwright 中无效，绝对不要使用：**

| ❌ jQuery 语法 | ✅ Playwright 替代方案 |
|---------------|---------------------|
| `div:contains("text")` | `page.locator('div').filter({{ hasText: 'text' }})` 或 `page.getByText('text')` |
| `:eq(0)` | `.first()` 或 `.nth(0)` |
| `:eq(n)` | `.nth(n)` |
| `:first` | `.first()` |
| `:last` | `.last()` |
| `:button` | `page.getByRole('button')` |
| `:checkbox` | `page.getByRole('checkbox')` |
| `:radio` | `page.getByRole('radio')` |
| `:checked` | `page.locator('[checked]')` |
| `:selected` | `page.getByRole('option', {{ selected: true }})` |
| `:visible` | `page.locator(':visible')`（Playwright 原生支持） |
| `:hidden` | `page.locator(':hidden')`（Playwright 原生支持） |
| `:disabled` | `page.locator('[disabled]')` |
| `:enabled` | `page.locator(':not([disabled])')` |

## ⚠️ 关键认知

**快照文本 ≠ HTML 语义 label**

快照中显示的 `generic [ref=e6]: "Username:"` 只是**显示文本**，不代表：
- HTML 中有 `<label for="inputUserName">Username:</label>`
- `getByLabel('Username')` 一定能找到元素

**实际情况可能是**：
```html
<div>Username:</div>  <!-- 只是显示文本，没有 for 属性 -->
<input id="inputUserName" type="text">  <!-- 没有被 label 关联 -->
```

## ⚡ 选择器优先级（按可靠性排序）

### 1️⃣ 最可靠：语义化选择器
```javascript
page.getByRole('button', {{ name: 'Sign in' }})  // 登录按钮
page.getByLabel('Username')                 // 如果有 label 关联
page.getByPlaceholder('Enter email')        // 占位符
page.getByText('Welcome', {{ exact: true }})     // 文本内容（精确匹配）
page.getByTestId('submit-btn')              // data-testid
```

### 2️⃣ 较可靠：CSS 属性选择器
```javascript
page.locator('#inputUserName')              // ID 选择器
page.locator('[name="username"]')           // name 属性
page.locator('input[type="password"]')      // 密码输入框（通常唯一）
page.locator('[data-testid="submit-btn"]')  // data-testid
```

### 3️⃣ 最后手段：组合选择器
```javascript
page.getByRole('textbox').filter({{ hasText: /.*/ }}).first()  // 带过滤的 first
page.locator('.el-form-item').filter({{ hasText: 'Username' }}).locator('input').first()  // 作用域内 first
page.locator('input[type="password"]')      // 密码输入框
```

## 📋 推断规则（按顺序执行）

### 规则1：表单元素优先使用 getByLabel 或 getByPlaceholder
```javascript
// 用户名输入框
page.getByLabel('Username')
// 或
page.getByPlaceholder('Enter username')

// 密码输入框（使用 password 类型，非常可靠）
page.locator('input[type="password"]')

// 按钮
page.getByRole('button', {{ name: 'Sign in' }})
```

### 规则2：文本内容使用 getByText（精确匹配）或 filter
```javascript
page.getByText('Welcome to BillAndPay', {{ exact: true }})
page.locator('div').filter({{ hasText: 'Welcome' }})
```

### 规则3：多个同类元素时使用 label/placeholder/filter 区分
```javascript
page.getByLabel('Username')             // 通过 label 区分
page.getByPlaceholder('Enter email')    // 通过 placeholder 区分
page.locator('.el-form-item').filter({{ hasText: 'Username' }}).locator('input')  // 通过父元素文本区分
```

## 📋 完整示例

**快照：**
```
- generic [ref=e6]: "Username:"
- textbox [ref=e7]           ← 目标：用户名输入框
- generic [ref=e8]: "Password:"
- textbox [ref=e9]           ← 目标：密码输入框
- button "Sign in" [ref=e12]
- generic [ref=e20]: "Welcome to BillAndPay"
```

**正确输出：**
```json
// 对于 textbox [ref=e7]（用户名输入框）
{{"selector": "page.getByLabel('Username')", "reason": "用户名输入框，使用 label 关联定位最可靠"}}

// 对于 textbox [ref=e9]（密码输入框）  
{{"selector": "page.locator('input[type=\"password\"]')", "reason": "密码输入框，使用 password 类型定位最可靠"}}

// 对于 button [ref=e12]
{{"selector": "page.getByRole('button', {{ name: 'Sign in' }})", "reason": "按钮有明确的 name，getByRole 可靠"}}

// 对于包含 "Welcome to BillAndPay" 的元素
{{"selector": "page.getByText('Welcome to BillAndPay', {{ exact: true }})", "reason": "使用 getByText 精确匹配文本内容"}}
```

## 输出格式（严格 JSON，无注释）
```json
{{
  "selector": "page.getByLabel('Username')",
  "confidence": 0.95,
  "reason": "用户名输入框，使用 label 关联定位"
}}
```

只返回 JSON，不要其他内容。**记住：绝对不要使用 [ref="xxx"] 选择器！**"""
        
        return prompt
    
    def _validate_selector(self, selector: str) -> tuple:
        """
        验证选择器是否有效（不包含 jQuery 等不支持的语法，不包含不稳定的 ref）
        
        Args:
            selector: 选择器字符串
            
        Returns:
            (is_valid, converted_selector) 元组
            - is_valid: 是否有效
            - converted_selector: 转换后的选择器（如果可以转换）
        """
        # 🚨 最严重：ref= 选择器（临时引用，极其不稳定，必须拒绝）
        ref_patterns = [
            (r'\[ref\s*=\s*["\'][^"\']*["\']\]', 'ref attribute (temporary reference)'),
            (r'\[ref\s*=\s*\w+\]', 'ref attribute (temporary reference)'),
        ]
        
        for pattern, name in ref_patterns:
            if re.search(pattern, selector):
                logs.error(f"[SemanticSelectorMiddleware] 🚨 检测到极其不稳定的选择器: {name}")
                logs.error(f"  原始选择器: {selector}")
                logs.error(f"  ❌ ref 是页面快照中的临时引用，每次页面刷新都会变化，绝对不能用于脚本！")
                logs.error(f"  正确做法：使用 getByRole、getByLabel、getByText 或 CSS 属性选择器")
                return False, None
        
        # jQuery 不支持的语法模式列表
        invalid_patterns = [
            # jQuery 伪类
            (r':contains\([^)]*\)', 'jQuery :contains()'),
            (r':has\([^)]*\)', 'jQuery :has()'),
            (r':eq\(\d+\)', 'jQuery :eq()'),
            (r':gt\(\d+\)', 'jQuery :gt()'),
            (r':lt\(\d+\)', 'jQuery :lt()'),
            (r':first(?![a-zA-Z])', 'jQuery :first'),
            (r':last(?![a-zA-Z])', 'jQuery :last'),
            (r':even(?![a-zA-Z])', 'jQuery :even'),
            (r':odd(?![a-zA-Z])', 'jQuery :odd'),
            (r':not\([^)]*\)', 'jQuery :not()'),  # jQuery 的 :not 与 CSS 不同
            (r':visible(?![a-zA-Z])', 'jQuery :visible'),
            (r':hidden(?![a-zA-Z])', 'jQuery :hidden'),
            (r':parent(?![a-zA-Z])', 'jQuery :parent'),
            (r':input(?![a-zA-Z])', 'jQuery :input'),
            (r':button(?![a-zA-Z])', 'jQuery :button'),
            (r':checkbox(?![a-zA-Z])', 'jQuery :checkbox'),
            (r':radio(?![a-zA-Z])', 'jQuery :radio'),
            (r':selected(?![a-zA-Z])', 'jQuery :selected'),
            (r':checked(?![a-zA-Z])', 'jQuery :checked'),
            (r':disabled(?![a-zA-Z])', 'jQuery :disabled'),
            (r':enabled(?![a-zA-Z])', 'jQuery :enabled'),
            # 其他不支持的语法
            (r'\$\([^)]+\)', 'jQuery $() syntax'),
        ]
        
        for pattern, name in invalid_patterns:
            if re.search(pattern, selector):
                logs.warning(f"[SemanticSelectorMiddleware] ⚠️ 检测到无效选择器语法: {name}")
                logs.warning(f"  原始选择器: {selector}")
                
                # 尝试转换
                converted = self._convert_jquery_to_playwright(selector)
                if converted:
                    logs.info(f"  转换后: {converted}")
                    return True, converted
                else:
                    logs.warning(f"  无法转换，返回 None")
                    return False, None
        
        return True, selector
    
    def _convert_jquery_to_playwright(self, selector: str) -> Optional[str]:
        """
        将 jQuery 语法转换为 Playwright 支持的语法
        
        Args:
            selector: 原始选择器
            
        Returns:
            转换后的选择器，或 None（无法转换）
        """
        original = selector
        
        # 1. 转换 :contains("text") → getByText('text') 或 locator('text=...')
        contains_match = re.search(r"([a-zA-Z]*)\s*:contains\(['\"]([^'\"]*)['\"]\)", selector)
        if contains_match:
            element = contains_match.group(1) or ''  # 元素类型（如 div）
            text = contains_match.group(2)
            
            # 如果有元素类型，使用 locator().filter()
            if element:
                return f"page.locator('{element}').filter({{ hasText: '{text}' }})"
            else:
                return f"page.getByText('{text}')"
        
        # 2. 转换 :eq(n) → .nth(n)
        eq_match = re.search(r':eq\((\d+)\)', selector)
        if eq_match:
            index = eq_match.group(1)
            selector = re.sub(r':eq\(\d+\)', f'.nth({index})', selector)
            return selector
        
        # 3. 转换 :first → .first()
        if re.search(r':first(?![a-zA-Z])', selector):
            selector = re.sub(r':first(?![a-zA-Z])', '.first()', selector)
            return selector
        
        # 4. 转换 :last → .last()
        if re.search(r':last(?![a-zA-Z])', selector):
            selector = re.sub(r':last(?![a-zA-Z])', '.last()', selector)
            return selector
        
        # 5. 转换 :button → getByRole('button')
        if re.search(r':button(?![a-zA-Z])', selector):
            return "page.getByRole('button')"
        
        # 6. 转换 :checkbox → getByRole('checkbox')
        if re.search(r':checkbox(?![a-zA-Z])', selector):
            return "page.getByRole('checkbox')"
        
        # 7. 转换 :radio → getByRole('radio')
        if re.search(r':radio(?![a-zA-Z])', selector):
            return "page.getByRole('radio')"
        
        # 8. 转换 :checked → locator('[checked]') 或 getByRole('checkbox', { checked: true })
        if re.search(r':checked(?![a-zA-Z])', selector):
            return "page.locator('[checked]')"
        
        # 9. 转换 :selected → getByRole('option', { selected: true })
        if re.search(r':selected(?![a-zA-Z])', selector):
            return "page.getByRole('option', { selected: true })"
        
        # 10. 转换 :disabled → getByRole('*', { disabled: true })
        if re.search(r':disabled(?![a-zA-Z])', selector):
            return "page.locator('[disabled]')"
        
        # 11. 转换 :enabled → getByRole('*', { enabled: true })
        if re.search(r':enabled(?![a-zA-Z])', selector):
            return "page.locator(':not([disabled])')"
        
        # 无法转换
        logs.warning(f"[SemanticSelectorMiddleware] 无法转换 jQuery 选择器: {original}")
        return None

    def _parse_ai_response(self, response: str, action: str, value: str = None) -> Optional[str]:
        """
        解析 AI 响应，提取选择器代码
        
        增强功能：
        - 验证选择器语法
        - 自动转换 jQuery 语法为 Playwright 语法
        
        Args:
            response: AI 响应文本
            action: 操作类型
            value: 填充值
            
        Returns:
            完整的 Playwright 代码
        """
        import json
        
        # 尝试提取 JSON
        try:
            # 去除可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith('```'):
                response = response.split('\n', 1)[1]  # 去除第一行
            if response.endswith('```'):
                response = response.rsplit('\n', 1)[0]  # 去除最后一行
            
            # 解析 JSON
            data = json.loads(response)
            selector = data.get('selector', '')
            
            if not selector:
                return None
            
            # 🔧 关键修复：验证选择器语法
            is_valid, converted_selector = self._validate_selector(selector)
            if not is_valid:
                logs.warning(f"[SemanticSelectorMiddleware] AI 生成了无效选择器，已忽略: {selector}")
                return None
            
            selector = converted_selector
            
            # 构建完整代码
            def escape(s):
                return s.replace("'", "\\'") if s else s
            
            if action == 'click':
                return f"await {selector}.click();"
            elif action == 'fill':
                safe_value = escape(value) if value else ''
                return f"await {selector}.fill('{safe_value}');"
            elif action == 'hover':
                return f"await {selector}.hover();"
            elif action == 'select':
                safe_value = escape(value) if value else ''
                return f"await {selector}.selectOption('{safe_value}');"
            
            return None
            
        except json.JSONDecodeError:
            # 尝试正则提取
            import re
            selector_match = re.search(r'"selector"\s*:\s*"([^"]+)"', response)
            if selector_match:
                selector = selector_match.group(1)
                
                # 🔧 关键修复：验证选择器语法
                is_valid, converted_selector = self._validate_selector(selector)
                if not is_valid:
                    logs.warning(f"[SemanticSelectorMiddleware] AI 生成了无效选择器，已忽略: {selector}")
                    return None
                
                selector = converted_selector
                
                if action == 'click':
                    return f"await {selector}.click();"
                elif action == 'fill':
                    safe_value = value.replace("'", "\\'") if value else ''
                    return f"await {selector}.fill('{safe_value}');"
                elif action == 'hover':
                    return f"await {selector}.hover();"
            return None


# 全局实例，供 CodeCollectorMiddleware 使用
_semantic_selector_instance: Optional[SemanticSelectorMiddleware] = None


def get_semantic_selector() -> SemanticSelectorMiddleware:
    """获取语义选择器单例"""
    global _semantic_selector_instance
    if _semantic_selector_instance is None:
        _semantic_selector_instance = SemanticSelectorMiddleware()
    return _semantic_selector_instance


def reset_semantic_selector():
    """重置语义选择器状态"""
    global _semantic_selector_instance
    if _semantic_selector_instance:
        _semantic_selector_instance.reset()