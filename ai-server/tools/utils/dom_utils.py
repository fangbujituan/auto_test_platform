"""
工具函数模块
提供通用的工具函数，如 DOM 清理等
"""

import re
from bs4 import BeautifulSoup

from tools.debug.readlog import logs


# 交互元素类型（Playwright YAML 快照中的元素类型）
# 这些元素需要保留，其他元素可以考虑移除
INTERACTIVE_ELEMENT_TYPES = {
    # 表单元素
    'button', 'textbox', 'checkbox', 'radio', 'combobox', 'listbox',
    'slider', 'spinbutton', 'searchbox', 'textarea', 'input',
    # 导航元素
    'link', 'navigation', 'menuitem', 'menu', 'menubar',
    # 操作元素
    'tab', 'treeitem', 'tree', 'gridcell', 'option',
    # 其他交互
    'alertdialog', 'dialog', 'tooltip', 'alert',
}

# 语义容器元素（需要保留，但可以精简）
SEMANTIC_CONTAINER_TYPES = {
    'generic', 'region', 'article', 'main', 'banner', 'contentinfo',
    'form', 'group', 'list', 'listitem', 'table', 'row', 'cell',
}

# 无用属性列表（移除以减少 token，不影响元素识别）
USELESS_ATTRIBUTES = [
    r'\[orientation[^\]]*\]',      # [orientation], [orientation=vertical]
    r'\[implicit[^\]]*\]',         # [implicit], [implicit=true]
    r'\[expanded[^\]]*\]',         # [expanded], [expanded=false]
    r'\[level[^\]]*\]',            # [level], [level=1]
    r'\[modal[^\]]*\]',            # [modal], [modal=false]
    r'\[multiline[^\]]*\]',        # [multiline]
    r'\[multiselectable[^\]]*\]',  # [multiselectable]
    r'\[readonly[^\]]*\]',         # [readonly]
    r'\[required[^\]]*\]',         # [required]
    r'\[invalid[^\]]*\]',          # [invalid]
    r'\[valuetext[^\]]*\]',        # [valuetext="..."]
    r'\[haspopup[^\]]*\]',         # [haspopup]
    r'\[controls[^\]]*\]',         # [controls]
    r'\[describedby[^\]]*\]',      # [describedby]
    r'\[labelledby[^\]]*\]',       # [labelledby]
    r'\[owns[^\]]*\]',             # [owns]
    r'\[activedescendant[^\]]*\]', # [activedescendant]
    # 新增：更多无用属性
    r'\[selected[^\]]*\]',         # [selected], [selected=false]
    r'\[checked[^\]]*\]',          # [checked], [checked=false]
    r'\[pressed[^\]]*\]',          # [pressed], [pressed=false]
    r'\[disabled[^\]]*\]',         # [disabled]（保留，但可以移除 [disabled=false]
    r'\[busy[^\]]*\]',             # [busy]
    r'\[live[^\]]*\]',             # [live]
    r'\[atomic[^\]]*\]',           # [atomic]
    r'\[relevant[^\]]*\]',         # [relevant]
    r'\[dropeffect[^\]]*\]',       # [dropeffect]
    r'\[grabbed[^\]]*\]',          # [grabbed]
]


# 重复行截断配置
REPEATED_ROW_MAX_KEEP = 2       # 保留前 N 行重复结构
REPEATED_ROW_MIN_REPEAT = 5     # 至少连续 N 行相同结构才触发截断
REPEATED_ROW_TYPES = {'row', 'listitem', 'option', 'treeitem', 'gridcell'}  # 可能重复的元素类型


def _get_structure_signature(line: str) -> str:
    """
    提取行的"结构签名"：缩进级别 + 元素类型，忽略文本内容和 ref 值。
    
    相同结构签名意味着行的 DOM 结构相同，只是数据不同。
    
    例如:
        '    - row [ref=e45]:' → '4:row'
        '    - row [ref=e99]:' → '4:row'  (相同签名)
        '      - cell [ref=e46]: "Apple"' → '6:cell'
        '      - cell [ref=e100]: "Banana"' → '6:cell'  (相同签名)
    
    Args:
        line: 快照行内容
        
    Returns:
        结构签名字符串，无法解析时返回空字符串
    """
    type_match = re.match(r'^(\s*)-\s+(\w+)', line)
    if not type_match:
        return ''
    indent = len(type_match.group(1))
    elem_type = type_match.group(2)
    return f'{indent}:{elem_type}'


def _detect_and_truncate_repeated_rows(
    lines: list,
    max_keep: int = REPEATED_ROW_MAX_KEEP,
    min_repeat: int = REPEATED_ROW_MIN_REPEAT,
) -> tuple:
    """
    检测快照中连续重复的列表/表格行并截断。
    
    算法：
    1. 扫描所有行，提取结构签名
    2. 找到连续 N 行（N >= min_repeat）具有相同签名且为可重复类型的区间
    3. 一个"重复组"包含父行及其所有子行（通过缩进判断）
    4. 只保留前 max_keep 组 + 最后 1 组 + 摘要注释
    
    Args:
        lines: 快照行列表
        max_keep: 保留的最大重复组数（默认 5）
        min_repeat: 触发截断的最小重复组数（默认 8）
        
    Returns:
        (truncated_lines, stats) 其中 stats = {'truncated_groups': int, 'total_groups': int, 'saved_lines': int}
    """
    if not lines:
        return lines, {'truncated_groups': 0, 'total_groups': 0, 'saved_lines': 0}
    
    # Step 1: 识别所有"组"——每个组是一个父行 + 其所有子行
    # 一个组的起始行是可重复类型（row, listitem 等），子行是缩进更深的行
    groups = []  # [(start_idx, end_idx, signature), ...]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        sig = _get_structure_signature(line)
        
        if sig:
            indent_str, elem_type = sig.split(':', 1)
            parent_indent = int(indent_str)
            
            if elem_type in REPEATED_ROW_TYPES:
                # 找到这个组的结束位置（所有缩进更深的子行）
                group_end = i + 1
                while group_end < len(lines):
                    next_line = lines[group_end]
                    if not next_line.strip():
                        group_end += 1
                        continue
                    next_match = re.match(r'^(\s*)', next_line)
                    next_indent = len(next_match.group(1)) if next_match else 0
                    if next_indent <= parent_indent:
                        break
                    group_end += 1
                
                groups.append((i, group_end, sig))
                i = group_end
                continue
        
        i += 1
    
    if not groups:
        return lines, {'truncated_groups': 0, 'total_groups': 0, 'saved_lines': 0}
    
    # Step 2: 找到连续相同签名的组序列
    # 例如: [row, row, row, row, row, ...] 是一个连续序列
    # 组之间不能有其他非空内容行（否则不算连续）
    sequences = []  # [(start_group_idx, end_group_idx, signature), ...]
    seq_start = 0
    
    for g in range(1, len(groups)):
        is_same_sig = groups[g][2] == groups[seq_start][2]
        # 检查两个组之间是否有非空的"间隔行"（不属于前一个组的行）
        is_adjacent = groups[g][0] == groups[g - 1][1]  # 当前组起始 == 前一组结束
        
        if not is_same_sig or not is_adjacent:
            if g - seq_start >= min_repeat:
                sequences.append((seq_start, g, groups[seq_start][2]))
            seq_start = g
    
    # 处理最后一个序列
    if len(groups) - seq_start >= min_repeat:
        sequences.append((seq_start, len(groups), groups[seq_start][2]))
    
    if not sequences:
        return lines, {'truncated_groups': 0, 'total_groups': 0, 'saved_lines': 0}
    
    # Step 3: 构建截断后的行列表
    # 标记哪些行范围需要被截断
    truncate_ranges = []  # [(line_start, line_end, total_groups, signature), ...]
    
    for seq_start_g, seq_end_g, sig in sequences:
        total_groups = seq_end_g - seq_start_g
        if total_groups <= max_keep + 1:
            continue  # 不够多，不截断
        
        # 保留前 max_keep 组，截断中间，保留最后 1 组
        keep_end_group = seq_start_g + max_keep
        last_group = seq_end_g - 1
        
        # 截断范围：从第 max_keep+1 组的起始行到倒数第 2 组的结束行
        trunc_line_start = groups[keep_end_group][0]
        trunc_line_end = groups[last_group][0]  # 最后一组的起始行（不截断最后一组）
        
        truncate_ranges.append((trunc_line_start, trunc_line_end, total_groups, sig))
    
    if not truncate_ranges:
        return lines, {'truncated_groups': 0, 'total_groups': 0, 'saved_lines': 0}
    
    # Step 4: 构建结果
    result_lines = []
    total_truncated_groups = 0
    total_saved_lines = 0
    prev_end = 0
    
    for trunc_start, trunc_end, total_groups, sig in sorted(truncate_ranges):
        # 添加截断范围之前的行
        result_lines.extend(lines[prev_end:trunc_start])
        
        # 添加摘要注释
        truncated_count = total_groups - max_keep - 1
        indent_str = sig.split(':')[0]
        indent = ' ' * int(indent_str)
        elem_type = sig.split(':')[1]
        result_lines.append(
            f'{indent}# ... 省略 {truncated_count} 个相同结构的 {elem_type} '
            f'（共 {total_groups} 个，已保留前 {max_keep} 个和最后 1 个）'
        )
        
        total_truncated_groups += truncated_count
        total_saved_lines += (trunc_end - trunc_start)
        prev_end = trunc_end
    
    # 添加最后一段
    result_lines.extend(lines[prev_end:])
    
    stats = {
        'truncated_groups': total_truncated_groups,
        'total_groups': sum(s[2] for s in truncate_ranges),
        'saved_lines': total_saved_lines,
    }
    
    logs.info(
        f"[repeated_row_truncation] 截断 {len(truncate_ranges)} 个重复区间，"
        f"省略 {total_truncated_groups} 个重复组，减少 {total_saved_lines} 行"
    )
    
    return result_lines, stats


def _remove_useless_attributes(line: str) -> str:
    """
    移除行中的无用属性
    
    Args:
        line: 快照行内容
        
    Returns:
        清理后的行内容
    """
    for pattern in USELESS_ATTRIBUTES:
        line = re.sub(pattern, '', line)
    # 清理多余的空格
    line = re.sub(r'\s+', ' ', line)
    line = re.sub(r'\s*\]', ']', line)
    line = re.sub(r'\[\s*', '[', line)
    return line.strip()


def _is_empty_generic(line: str) -> bool:
    """
    判断是否是空的 generic 容器（无 ref、无文本、无交互属性）
    
    空容器的特征：
    - 只有 generic 类型
    - 没有 [ref=ex]
    - 没有 [cursor=pointer]
    - 没有文本内容
    - 结尾是冒号（只有子元素，无自身内容）
    
    Args:
        line: 快照行内容
        
    Returns:
        是否是空容器
    """
    # 必须是 generic 类型
    if 'generic' not in line:
        return False
    
    # 如果有 ref，不是空容器
    if re.search(r'\[ref=e\d+\]', line):
        return False
    
    # 如果有 cursor=pointer，不是空容器
    if 'cursor=pointer' in line or 'cursor= pointer' in line:
        return False
    
    # 提取冒号后的文本内容
    colon_match = re.search(r'\]:\s*(.+)$', line)
    if colon_match and colon_match.group(1).strip():
        return False
    
    return True


def _should_filter_element(line: str) -> bool:
    """
    判断元素是否应该被过滤（非交互元素且无重要信息）

    过滤规则：
    1. 没有 [ref=ex] 的元素 → 过滤（无法定位）
    2. 有 [ref=ex] 但元素类型无意义 → 保留（可定位）
    3. 有 cursor=pointer → 保留（可点击）
    4. 有文本内容 → 保留（有语义）

    保留的元素类型（有 ref 且是交互类型）：
    - 表单：button, textbox, checkbox, radio, combobox, listbox...
    - 导航：link, menuitem, menu, tab...
    - 容器：generic（如果有关键信息）

    过滤的元素类型：
    - 无 ref 的 generic
    - 纯文本节点
    - 无意义的装饰元素

    Args:
        line: 快照行内容

    Returns:
        是否应该过滤（True = 过滤掉，False = 保留）
    """
    # 提取元素类型（行首的 - type）
    type_match = re.match(r'\s*-\s+(\w+)', line)
    if not type_match:
        return False  # 无法识别，保留

    element_type = type_match.group(1)

    # 检查是否有 ref
    has_ref = bool(re.search(r'\[ref=e\d+\]', line))

    # 检查是否有 cursor=pointer
    has_cursor = 'cursor=pointer' in line or 'cursor= pointer' in line

    # 检查是否有文本内容
    has_text = bool(re.search(r'\]:\s*[^:\s]', line))

    # 规则1：没有 ref 的元素，检查是否需要保留
    if not has_ref:
        # 无 ref 但有 cursor=pointer，保留（可能需要语义化选择器）
        if has_cursor:
            return False
        # 无 ref 的 generic，过滤
        if element_type == 'generic':
            return True
        # 其他无 ref 元素，保留（可能是页面结构信息）
        return False

    # 规则2：有 ref 的元素，检查元素类型
    # 交互元素类型，始终保留
    if element_type in INTERACTIVE_ELEMENT_TYPES:
        return False

    # 有 ref 且有 cursor=pointer，保留
    if has_cursor:
        return False

    # 有 ref 且有文本内容，保留
    if has_text:
        return False

    # 有 ref 的 generic，保留（可能包含重要子元素）
    if element_type == 'generic':
        return False

    # 其他语义容器，保留
    if element_type in SEMANTIC_CONTAINER_TYPES:
        return False

    # 未知元素类型但有 ref，保守保留
    return False


def clean_playwright_snapshot(content: str, filter_non_interactive: bool = True) -> str:
    """
    清理 Playwright MCP 返回的 YAML 格式 Snapshot，减少 token 消耗。

    分层清理策略：
    1. 移除 "### Ran Playwright code" 代码块
    2. 移除 "### Events" 控制台日志
    3. 筛选交互元素（可选：filter_non_interactive=True 时过滤非交互元素）
    4. 移除无用属性（orientation, implicit, expanded, level 等）
    5. 移除空的 generic 容器层（无 ref、无交互）
    6. 压缩空行

    保留（Playwright MCP 操作必需）：
    - 页面 URL 和标题
    - 元素类型（button, textbox, link, generic 等）
    - 元素引用 [ref=ex]（Playwright 定位元素必需）
    - 元素文本内容
    - 表单元素的值
    - [cursor=pointer]（识别可点击元素）

    Args:
        content: Playwright MCP 返回的原始内容
        filter_non_interactive: 是否过滤非交互元素（默认 True）

    Returns:
        清理后的内容
    """
    if not content or not isinstance(content, str):
        return content

    try:
        result = content
        original_length = len(content)

        # 1. 移除 "### Ran Playwright code" 代码块
        result = re.sub(
            r'### Ran Playwright code\s*```js.*?```\s*',
            '',
            result,
            flags=re.DOTALL
        )

        # 2. 移除 "### Events" 部分（包括其后的所有内容直到下一个 ### 或结尾）
        result = re.sub(
            r'### Events\s*\n.*?(?=###|$)',
            '',
            result,
            flags=re.DOTALL
        )

        # 3. 移除激活状态 [active]
        result = re.sub(r'\s*\[active\]', '', result)

        # 4. 移除 /url: 链接信息（整行）
        result = re.sub(r'\s*-\s*/url:.*?\n', '\n', result)

        # 5. 逐行处理：筛选交互元素 + 移除无用属性
        lines = result.split('\n')
        
        # 5a. 🔥 重复行截断（在属性清理之前执行，因为需要原始缩进信息）
        truncated_lines, trunc_stats = _detect_and_truncate_repeated_rows(lines)
        if trunc_stats['truncated_groups'] > 0:
            lines = truncated_lines
            logs.info(
                f"[clean_playwright_snapshot] 重复行截断: "
                f"省略 {trunc_stats['truncated_groups']}/{trunc_stats['total_groups']} 个重复组，"
                f"减少 {trunc_stats['saved_lines']} 行"
            )
        
        # 5b. 逐行清理属性 + 筛选非交互元素
        cleaned_lines = []
        skip_indent = -1  # 跳过该缩进级别的子元素

        for i, line in enumerate(lines):
            # 计算当前行缩进
            current_indent = len(line) - len(line.lstrip())
            
            # 如果在跳过范围内，继续跳过
            if skip_indent >= 0 and current_indent > skip_indent:
                continue
            
            # 重置跳过标记
            skip_indent = -1
            
            # 跳过摘要注释行（重复行截断生成的）
            if line.lstrip().startswith('#'):
                cleaned_lines.append(line.lstrip())
                continue
            
            # 移除无用属性
            cleaned_line = _remove_useless_attributes(line)
            
            # 方案3：筛选交互元素
            if filter_non_interactive and _should_filter_element(cleaned_line):
                # 标记跳过其子元素
                skip_indent = current_indent
                continue
            
            cleaned_lines.append(cleaned_line)
        
        result = '\n'.join(cleaned_lines)

        # 6. 移除空的 generic 容器层（多轮处理，逐层移除）
        max_iterations = 5  # 防止无限循环
        for _ in range(max_iterations):
            lines = result.split('\n')
            filtered_lines = []
            skip_next_indent = -1
            
            for i, line in enumerate(lines):
                current_indent = len(line) - len(line.lstrip())
                
                if skip_next_indent >= 0 and current_indent > skip_next_indent:
                    continue
                
                skip_next_indent = -1
                
                if _is_empty_generic(line):
                    skip_next_indent = current_indent
                    continue
                
                filtered_lines.append(line)
            
            new_result = '\n'.join(filtered_lines)
            if new_result == result:
                break
            result = new_result

        # 7. 压缩多余空行（超过2个连续空行变为1个）
        result = re.sub(r'\n{3,}', '\n\n', result)

        # 8. 清理行尾空白
        result = re.sub(r'[ \t]+\n', '\n', result)

        # 日志记录清理效果
        cleaned_length = len(result.strip())
        reduction = (original_length - cleaned_length) / original_length * 100 if original_length > 0 else 0
        logs.info(f"[clean_playwright_snapshot] 清理完成: {original_length} -> {cleaned_length} chars ({reduction:.1f}% reduction)")

        return result.strip()

    except Exception as e:
        logs.warning(f"Playwright snapshot cleaning failed: {e}")
        return content


def clean_dom_html(html_content: str) -> str:
    """
    清理 HTML DOM，移除无用的标签和属性，减少 token 消耗。

    保留：
    - HTML 结构标签（div, span, a, button, input, form 等）
    - 关键属性（id, name, type, placeholder, value, href, src）
    - ARIA 属性（aria-label, aria-hidden 等）
    - data-* 属性
    - 文本内容

    移除：
    - <script>, <style>, <link>, <meta> 标签
    - 所有 style 属性
    - class 属性
    - 事件属性（onclick, onload 等）
    - 注释

    Args:
        html_content: 原始 HTML 内容

    Returns:
        清理后的 HTML 内容
    """
    if not html_content or not isinstance(html_content, str):
        return html_content

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # 移除特定标签
        for tag in soup(['script', 'style', 'link', 'meta', 'noscript']):
            tag.decompose()

        # 移除注释
        for comment in soup.find_all(string=lambda text: isinstance(text, type(soup.comment))):
            comment.extract()

        # 移除不需要的属性
        for tag in soup.find_all(True):
            # 保留的属性
            keep_attrs = set()
            
            # 保留 id, name, type 等关键属性
            for attr in ['id', 'name', 'type', 'placeholder', 'value', 'href', 'src', 'alt', 'title']:
                if tag.get(attr):
                    keep_attrs.add(attr)
            
            # 保留 ARIA 属性
            for attr in tag.attrs:
                if attr.startswith('aria-'):
                    keep_attrs.add(attr)
            
            # 保留 data-* 属性
            for attr in tag.attrs:
                if attr.startswith('data-'):
                    keep_attrs.add(attr)
            
            # 移除其他属性（包括 class, style, onclick 等）
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in keep_attrs}

        return str(soup)
    except Exception as e:
        # 如果解析失败，返回原始内容
        logs.warning(f"DOM cleaning failed: {e}")
        return html_content


# 选择器相关的关键属性（用于激进清理）
SELECTOR_RELEVANT_ATTRS = {
    # ID 和标识属性
    'id', 'name', 'data-testid',
    # 表单属性
    'type', 'placeholder', 'value', 'for', 'required', 'disabled', 'readonly',
    # 链接和资源
    'href', 'src', 'alt', 'title',
    # ARIA 属性（选择器常用）
    'role', 'aria-label', 'aria-labelledby', 'aria-describedby', 'aria-hidden',
    # 可交互性
    'tabindex', 'contenteditable',
    # 其他有用属性
    'target', 'rel', 'autocomplete', 'autofocus',
}

# 交互相关标签（优先保留）
INTERACTIVE_TAGS = {
    'button', 'a', 'input', 'select', 'textarea', 'form', 'option', 'optgroup',
    'label', 'fieldset', 'legend', 'checkbox', 'radio',
}

# 语义容器标签（精简保留）
SEMANTIC_TAGS = {
    'div', 'span', 'section', 'nav', 'header', 'footer', 'main', 'article',
    'aside', 'details', 'summary', 'dialog', 'menu', 'menuitem',
}

# 完全移除的标签（与选择器无关）
REMOVE_TAGS = {
    'script', 'style', 'link', 'meta', 'noscript', 'svg', 'path', 'g', 'rect',
    'circle', 'ellipse', 'line', 'polygon', 'polyline', 'defs', 'use', 'symbol',
    'iframe', 'canvas', 'video', 'audio', 'source', 'track', 'embed', 'object',
    'param', 'picture', 'portal', 'slot', 'template', 'math', 'mrow', 'mi', 'mo',
}


def clean_dom_html_for_selectors(html_content: str, max_text_length: int = 100) -> str:
    """
    激进清理 HTML DOM，只保留选择器生成相关的信息。

    与 clean_dom_html 的区别：
    - 更激进的标签过滤：移除所有非交互/非语义标签
    - 更严格的属性过滤：只保留选择器相关的属性
    - 文本精简：移除空白、截断超长文本
    - 动态 ID 检测：移除看起来像动态生成的 ID

    保留：
    - 交互元素：button, a, input, select, textarea, form, label 等
    - 语义容器：div, span, section, nav, header, footer 等
    - 关键属性：id, name, data-testid, type, placeholder, for, role, aria-* 等
    - 精简后的文本内容

    移除：
    - 无关标签：script, style, svg, iframe, canvas 等
    - 无用属性：class, style, 事件属性, 动态 ID
    - 纯空白文本节点
    - 注释

    Args:
        html_content: 原始 HTML 内容
        max_text_length: 单个文本节点的最大长度（超过则截断）

    Returns:
        清理后的精简 HTML 内容
    """
    if not html_content or not isinstance(html_content, str):
        return html_content

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. 移除无关标签（完全删除，不保留内容）
        for tag_name in REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 2. 移除注释
        for comment in soup.find_all(string=lambda text: isinstance(text, type(soup.comment))):
            comment.extract()

        # 3. 清理每个标签的属性和文本
        for tag in soup.find_all(True):
            # 3.1 过滤属性
            keep_attrs = {}
            for attr, value in tag.attrs.items():
                attr_lower = attr.lower()
                
                # 只保留选择器相关属性
                if attr_lower in SELECTOR_RELEVANT_ATTRS or attr_lower.startswith('data-'):
                    # 特殊处理：检测动态 ID
                    if attr_lower == 'id' and _is_dynamic_html_id(str(value)):
                        logs.debug(f"[DOMCleaner] 跳过动态 ID: {value}")
                        continue
                    
                    # 保留属性
                    if isinstance(value, list):
                        value = ' '.join(value)
                    keep_attrs[attr_lower] = value
            
            tag.attrs = keep_attrs

            # 3.2 精简文本内容
            for child in tag.children:
                if isinstance(child, str):
                    text = child.strip()
                    if not text:
                        # 移除纯空白文本节点
                        child.replace_with('')
                    elif len(text) > max_text_length:
                        # 截断超长文本
                        truncated = text[:max_text_length] + '...'
                        child.replace_with(truncated)

        # 4. 移除空标签（无属性、无文本、非交互元素）
        _remove_empty_tags(soup)

        # 5. 格式化输出（紧凑格式）
        result = _compact_html_output(soup)
        
        logs.info(f"[DOMCleaner] HTML 激进清理: {len(html_content)} -> {len(result)} chars ({100*(1-len(result)/len(html_content)):.1f}% reduction)")
        
        return result

    except Exception as e:
        logs.warning(f"[DOMCleaner] HTML 激进清理失败: {e}")
        return html_content


def _is_dynamic_html_id(id_value: str) -> bool:
    """
    判断 HTML ID 是否是动态生成的（不稳定，不应作为选择器）

    动态 ID 特征：
    - React/Aria: :r1:, :r2a:
    - 随机字符串: abc123xyz, x7f9k2m
    - 时间戳: 1712345678
    - UUID 片段: 8f14e45f
    - 数字开头: 123abc
    """
    if not id_value:
        return True

    id_lower = id_value.lower()

    # 语义化关键词（保留）
    semantic_keywords = [
        'user', 'pass', 'email', 'name', 'submit', 'login', 'logout', 'btn',
        'button', 'input', 'form', 'search', 'menu', 'nav', 'header', 'footer',
        'main', 'content', 'sidebar', 'modal', 'dialog', 'alert', 'error',
        'username', 'password', 'confirm', 'cancel', 'save', 'delete', 'edit',
        'add', 'remove', 'update', 'create', 'select', 'checkbox', 'radio',
        'text', 'textarea', 'label', 'title', 'description', 'wrapper',
        'container', 'section', 'item', 'list', 'table', 'row', 'cell',
    ]
    for keyword in semantic_keywords:
        if keyword in id_lower:
            return False

    # React/Aria 动态 ID: :r1:, :r2a:
    if re.match(r'^:r\d+[a-z]?:$', id_value):
        return True

    # 纯数字（可能是 ID 或时间戳）
    if re.match(r'^\d+$', id_value):
        return True

    # 长随机字符串（8+ 字符，无语义）
    if re.match(r'^[a-z0-9]{8,}$', id_lower):
        # 检查元音/辅音比例（随机字符串特征）
        vowels = sum(1 for c in id_lower if c in 'aeiou')
        consonants = sum(1 for c in id_lower if c in 'bcdfghjklmnpqrstvwxyz')
        if vowels > 0 and consonants > 0:
            ratio = vowels / consonants
            if 0.3 < ratio < 0.7:
                return True

    # 包含长数字序列（时间戳/随机数）
    if re.search(r'\d{6,}', id_value):
        return True

    return False


def _remove_empty_tags(soup: BeautifulSoup, max_iterations: int = 10):
    """
    移除空标签（无属性、无文本、非交互元素）

    多轮迭代，逐层移除空的包装标签
    """
    for _ in range(max_iterations):
        removed = False
        for tag in soup.find_all(True):
            # 跳过交互元素（即使为空也保留）
            if tag.name in INTERACTIVE_TAGS:
                continue

            # 检查是否有内容
            has_text = bool(tag.get_text(strip=True))
            has_attrs = bool(tag.attrs)
            has_children = len(tag.find_all(True, recursive=False)) > 0

            # 如果无文本、无属性、无子元素，移除
            if not has_text and not has_attrs and not has_children:
                tag.decompose()
                removed = True

        if not removed:
            break


def _compact_html_output(soup: BeautifulSoup) -> str:
    """
    生成紧凑的 HTML 输出（减少空白）
    """
    # 获取格式化后的 HTML
    html = str(soup)

    # 压缩多余空白
    html = re.sub(r'>\s+<', '><', html)  # 标签间空白
    html = re.sub(r'\s+', ' ', html)  # 多个空格变一个
    html = re.sub(r'>\s{2,}', '>', html)  # 标签内多余空格
    html = re.sub(r'\s{2,}<', '<', html)  # 标签前多余空格

    return html.strip()