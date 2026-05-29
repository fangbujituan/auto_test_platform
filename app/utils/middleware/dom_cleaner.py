"""
DOM 清理中间件模块
重写 AgentMiddleware.awrap_tool_call 方法，自动清理 DOM 数据以减少 token 消耗

整合自 ai-server/tools/middleware/dom_cleaner.py
"""

import re

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.utils.debug.readlog import logs
from app.utils.dom_utils import clean_dom_html, clean_dom_html_for_selectors, clean_playwright_snapshot


class DOMCleanerMiddleware(AgentMiddleware):
    """
    DOM 清理中间件，重写 awrap_tool_call 方法拦截工具输出，
    自动清理 DOM 数据以减少 token 消耗。

    支持两种格式：
    1. HTML 格式 - 使用 clean_dom_html 清理
    2. Playwright Snapshot YAML 格式 - 使用 clean_playwright_snapshot 清理

    🆕 原始 HTML 传递：
    在清理前，将原始 HTML 传递给 SemanticSelectorMiddleware，
    用于判断 label for 关联。
    """

    @property
    def name(self) -> str:
        """中间件名称"""
        return "dom_cleaner"

    def __init__(self):
        """初始化中间件，添加调试日志"""
        super().__init__()
        logs.info("[DOMCleanerMiddleware] 初始化完成")

    def _extract_raw_html(self, content: str) -> str:
        """
        从内容中提取原始 HTML

        Args:
            content: 原始内容

        Returns:
            提取的原始 HTML（如果没有则返回空字符串）
        """
        if not content:
            return ""

        # 尝试提取 HTML 内容
        # 格式0: browser_evaluate 返回的格式 ### Result\n"<html>..."
        # 注意：HTML 可能被引号包裹，需要提取
        if '### Result' in content:
            match = re.search(r'### Result\s*["\']?(<html[^>]*>.*?</html>)["\']?', content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)

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

        # 格式3: 从页面内容中提取（Playwright MCP 返回的格式）
        # 尝试提取 ### Page 后的内容
        match = re.search(r'### Page.*?\n(.+?)(?=###|$)', content, re.DOTALL)
        if match:
            page_content = match.group(1)
            # 检查是否包含 HTML 标签
            if '<' in page_content and '>' in page_content:
                return page_content

        return ""

    def _extract_raw_content(self, result) -> str:
        """
        从工具结果中提取原始内容（在清理前）

        Args:
            result: 工具返回结果

        Returns:
            原始内容字符串
        """
        if isinstance(result, ToolMessage):
            content = result.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        return item.get('text', '')
        elif isinstance(result, str):
            return result
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and item.get('type') == 'text':
                    return item.get('text', '')
        return ""

    def _pass_raw_html_to_semantic_selector(self, tool_name: str, raw_html: str):
        """
        将原始 HTML 传递给 SemanticSelectorMiddleware（经过激进清理）

        流程：
        1. 使用 clean_dom_html_for_selectors 激进清理 HTML
        2. 只保留选择器相关的信息（id, name, data-testid, aria-*, for 等）
        3. 传递给 SemanticSelectorMiddleware 用于选择器生成

        Args:
            tool_name: 工具名称
            raw_html: 原始 HTML 内容
        """
        if not raw_html:
            return

        try:
            # 🚀 激进清理：只保留选择器相关的信息
            cleaned_html = clean_dom_html_for_selectors(raw_html)

            # 使用全局单例获取 SemanticSelectorMiddleware
            # 注意：此方法在整合环境中可能需要调整
            try:
                from app.utils.middleware.semantic_selector import get_semantic_selector
                semantic_selector = get_semantic_selector()
                if semantic_selector:
                    # 更新原始 HTML 缓存并解析 label for 关联
                    semantic_selector._raw_html_cache = cleaned_html
                    semantic_selector._parse_label_for_associations(cleaned_html)
                    logs.info(f"[DOMCleanerMiddleware] 已将清理后的 HTML 传递给 SemanticSelectorMiddleware")
                    logs.info(f"  - 原始: {len(raw_html)} chars")
                    logs.info(f"  - 清理后: {len(cleaned_html)} chars")
            except ImportError:
                logs.debug("[DOMCleanerMiddleware] SemanticSelectorMiddleware 暂未整合，跳过 HTML 传递")
        except Exception as e:
            logs.warning(f"[DOMCleanerMiddleware] 传递 HTML 失败: {e}")

    def _contains_html(self, content: str) -> bool:
        """判断内容是否包含 HTML 标签"""
        if not isinstance(content, str):
            return False
        return bool(re.search(r'<[^>]+>', content))

    def _contains_playwright_snapshot(self, content: str) -> bool:
        """判断内容是否是 Playwright Snapshot 格式"""
        if not isinstance(content, str):
            return False
        # 检测 Playwright MCP 返回的特征标记
        patterns = [
            r'### Ran Playwright code',
            r'### Page',
            r'### Snapshot',
            r'### Events',
            r'\[ref=e\d+\]',
        ]
        return any(re.search(pattern, content) for pattern in patterns)

    # 分级清理阈值
    SNAPSHOT_TIER1_THRESHOLD = 20000   # 中度清理：只保留有 ref 的元素及其直接父级
    SNAPSHOT_TIER2_THRESHOLD = 40000   # 重度清理：只保留交互元素
    SNAPSHOT_SUMMARY_THRESHOLD = 60000 # 摘要兜底（极端情况）

    def _clean_content(self, content: str) -> str:
        """
        清理内容，自动检测格式并使用对应的清理方法

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        if not isinstance(content, str):
            return content

        # 🚨 优先检测 browser_evaluate 返回的 HTML 格式：### Result\n"<html>..."
        # 这种格式包含大量 HTML，不传给 AI，只返回摘要
        if '### Result' in content and '<html' in content.lower():
            # HTML 已经在 _pass_raw_html_to_semantic_selector 中传递给 SemanticSelector
            # 这里不返回 HTML，而是返回简短摘要以节省 token
            html_size = len(content)
            logs.info(f"[DOMCleanerMiddleware] browser_evaluate 返回 HTML ({html_size} chars)，不传给 AI，返回摘要")
            return f"### Result\n✅ HTML 已获取并分析（{html_size} 字符），选择器相关信息已提取。"

        # 🚨 检测 browser_wait_for 等返回的大结果（包含 ### Result 但不是 HTML）
        # 如果内容过大，也返回摘要
        if '### Result' in content and len(content) > 10000:
            result_size = len(content)
            logs.info(f"[DOMCleanerMiddleware] 工具返回大结果 ({result_size} chars)，返回摘要")
            # 提取关键信息
            result_match = re.search(r'### Result\s*(.+?)(?=###|$)', content, re.DOTALL)
            result_text = result_match.group(1).strip()[:200] if result_match else "操作完成"
            return f"### Result\n{result_text}\n✅ 结果已处理（{result_size} 字符）。"

        # 判断内容类型并清理
        if self._contains_playwright_snapshot(content):
            # Playwright Snapshot YAML 格式
            cleaned = clean_playwright_snapshot(content)

            # 🚨 分级清理机制（替代原来的直接摘要退化）
            if len(cleaned) > self.SNAPSHOT_TIER1_THRESHOLD:
                # 中度清理：只保留有 [ref=] 的元素行及其直接父级行
                cleaned = self._tier1_clean(cleaned)
                logs.info(f"[DOMCleanerMiddleware] Tier1 清理后: {len(cleaned)} chars")

            if len(cleaned) > self.SNAPSHOT_TIER2_THRESHOLD:
                # 重度清理：只保留交互元素（button, link, textbox 等）
                cleaned = self._tier2_clean(cleaned)
                logs.info(f"[DOMCleanerMiddleware] Tier2 清理后: {len(cleaned)} chars")

            if len(cleaned) > self.SNAPSHOT_SUMMARY_THRESHOLD:
                logs.info(f"[DOMCleanerMiddleware] browser_snapshot 分级清理后仍过大 ({len(cleaned)} chars)，生成摘要")
                return self._generate_snapshot_summary(content, cleaned)

            return cleaned
        elif self._contains_html(content):
            # HTML 格式 - 使用激进清理（只保留选择器相关的信息）
            return clean_dom_html_for_selectors(content)
        else:
            # 未知格式，不做处理
            return content

    def _generate_snapshot_summary(self, original: str, cleaned: str) -> str:
        """
        为过大的 snapshot 生成摘要

        提取关键信息：
        - 页面 URL 和标题
        - 交互元素列表（button, link, input 等）
        - 元素总数

        Args:
            original: 原始内容
            cleaned: 清理后的内容

        Returns:
            摘要内容
        """
        import re

        summary_parts = []

        # 提取页面信息
        url_match = re.search(r'Page URL:\s*(.+)', original)
        title_match = re.search(r'Page Title:\s*(.+)', original)
        console_match = re.search(r'Console:\s*(\d+ errors?, \d+ warnings?)', original)

        if url_match:
            summary_parts.append(f"- Page URL: {url_match.group(1).strip()}")
        if title_match:
            summary_parts.append(f"- Page Title: {title_match.group(1).strip()}")
        if console_match:
            summary_parts.append(f"- Console: {console_match.group(1)}")

        # 统计交互元素
        interactive_elements = []
        element_counts = {}

        # 交互元素类型
        interactive_types = [
            'button', 'link', 'textbox', 'checkbox', 'radio',
            'combobox', 'listbox', 'menuitem', 'tab', 'searchbox'
        ]

        for elem_type in interactive_types:
            # 匹配格式: - button "文本" [ref=ex] 或 - link "文本" [ref=ex]
            pattern = rf'-\s+{elem_type}\s+"([^"]*)"\s*\[ref=e(\d+)\]'
            matches = re.findall(pattern, cleaned)
            if matches:
                element_counts[elem_type] = len(matches)
                # 保留前3个元素的详细信息
                for text, ref in matches[:3]:
                    interactive_elements.append(f"  - {elem_type}: \"{text}\" [ref=e{ref}]")

        # 添加元素统计
        if element_counts:
            counts_str = ", ".join(f"{t}: {c}" for t, c in element_counts.items())
            summary_parts.append(f"- 交互元素: {counts_str}")

        # 添加关键交互元素（最多10个）
        if interactive_elements:
            summary_parts.append("- 关键元素:")
            summary_parts.extend(interactive_elements[:10])

        # 统计总元素数
        total_elements = len(re.findall(r'\[ref=e\d+\]', cleaned))
        summary_parts.append(f"- 元素总数: {total_elements}")

        summary = "### Snapshot Summary\n" + "\n".join(summary_parts)
        summary += f"\n\n✅ 页面快照已获取并精简（原始 {len(original)} 字符，清理后 {len(cleaned)} 字符）。"

        return summary

    def _tier1_clean(self, snapshot: str) -> str:
        """
        中度清理：只保留有 [ref=] 的元素行及其直接父级行
        移除纯结构行（没有 ref 且不是交互元素父级的行）
        """
        lines = snapshot.split('\n')
        keep_lines = []
        ref_pattern = re.compile(r'\[ref=e\d+\]')

        # 先标记哪些行有 ref
        has_ref = [bool(ref_pattern.search(line)) for line in lines]

        for i, line in enumerate(lines):
            # 保留有 ref 的行
            if has_ref[i]:
                keep_lines.append(line)
                continue

            # 保留页面头部信息（Page URL, Page Title 等）
            stripped = line.strip()
            if stripped.startswith('- Page ') or stripped.startswith('- Console') or stripped.startswith('- document'):
                keep_lines.append(line)
                continue

            # 保留是下一个 ref 行的直接父级（缩进更少的行）
            line_indent = len(line) - len(line.lstrip())
            # 检查后续行中是否有缩进更深的 ref 行
            is_parent = False
            for j in range(i + 1, min(i + 20, len(lines))):
                next_indent = len(lines[j]) - len(lines[j].lstrip())
                if next_indent <= line_indent:
                    break  # 同级或更高级，不是子元素
                if has_ref[j]:
                    is_parent = True
                    break

            if is_parent:
                keep_lines.append(line)

        result = '\n'.join(keep_lines)
        logs.debug(f"[DOMCleanerMiddleware] Tier1: {len(lines)} 行 → {len(keep_lines)} 行")
        return result

    def _tier2_clean(self, snapshot: str) -> str:
        """
        重度清理：只保留交互元素行（button, link, textbox, checkbox, radio, combobox 等）
        """
        interactive_types = {
            'button', 'link', 'textbox', 'checkbox', 'radio',
            'combobox', 'listbox', 'menuitem', 'tab', 'searchbox',
            'switch', 'slider', 'spinbutton', 'option'
        }
        interactive_pattern = re.compile(
            r'-\s+(' + '|'.join(interactive_types) + r')\s'
        )

        lines = snapshot.split('\n')
        keep_lines = []

        for line in lines:
            stripped = line.strip()
            # 保留页面头部信息
            if stripped.startswith('- Page ') or stripped.startswith('- Console') or stripped.startswith('- document'):
                keep_lines.append(line)
                continue
            # 保留交互元素行
            if interactive_pattern.search(stripped):
                keep_lines.append(line)
                continue
            # 保留截断注释行
            if '省略' in stripped or 'truncated' in stripped.lower():
                keep_lines.append(line)

        result = '\n'.join(keep_lines)
        logs.debug(f"[DOMCleanerMiddleware] Tier2: {len(lines)} 行 → {len(keep_lines)} 行")
        return result

    def _clean_result(self, result):
        """
        递归清理结果数据

        Args:
            result: 工具返回结果

        Returns:
            清理后的结果
        """
        # 如果结果是 ToolMessage，清理其 content
        if isinstance(result, ToolMessage):
            original_content = result.content
            logs.info(f"[DOMCleanerMiddleware._clean_result] ToolMessage.content 类型: {type(original_content).__name__}")

            # 处理不同类型的 content
            if isinstance(original_content, str):
                cleaned_content = self._clean_content(original_content)
                original_length = len(original_content)
                cleaned_length = len(cleaned_content)
                logs.info(f"[DOMCleanerMiddleware._clean_result] 原始长度: {original_length}, 清理后长度: {cleaned_length}")

                if original_length > 0 and original_length != cleaned_length:
                    reduction = (original_length - cleaned_length) / original_length * 100
                    logs.info(f"[DOMCleanerMiddleware] DOM cleaned: {reduction:.1f}% reduction ({original_length} -> {cleaned_length} chars)")

            elif isinstance(original_content, list):
                # Playwright MCP 返回的 content 可能是列表
                logs.info(f"[DOMCleanerMiddleware._clean_result] content 是列表，长度: {len(original_content)}")
                cleaned_content = []
                for item in original_content:
                    if isinstance(item, dict) and 'text' in item:
                        # 格式: [{'type': 'text', 'text': '...'}]
                        original_text = item['text']
                        cleaned_text = self._clean_content(original_text)
                        original_length = len(original_text)
                        cleaned_length = len(cleaned_text)
                        logs.info(f"[DOMCleanerMiddleware._clean_result] 列表项 - 原始: {original_length}, 清理后: {cleaned_length}")
                        if original_length > 0 and original_length != cleaned_length:
                            reduction = (original_length - cleaned_length) / original_length * 100
                            logs.info(f"[DOMCleanerMiddleware] DOM cleaned: {reduction:.1f}% reduction ({original_length} -> {cleaned_length} chars)")
                        cleaned_content.append({**item, 'text': cleaned_text})
                    else:
                        cleaned_content.append(item)
            else:
                cleaned_content = original_content

            # 返回新的 ToolMessage
            return ToolMessage(
                content=cleaned_content,
                name=result.name,
                tool_call_id=result.tool_call_id,
                status=result.status,
                artifact=result.artifact,
            )

        # 如果结果是字符串，进行清理
        if isinstance(result, str):
            cleaned_result = self._clean_content(result)
            # 计算减少的比例（用于监控）
            original_length = len(result)
            cleaned_length = len(cleaned_result)
            if original_length > 0 and original_length != cleaned_length:
                reduction = (original_length - cleaned_length) / original_length * 100
                logs.info(f"[DOMCleanerMiddleware] DOM cleaned: {reduction:.1f}% reduction ({original_length} -> {cleaned_length} chars)")
            return cleaned_result

        # 如果结果是列表（Playwright MCP 返回的格式）
        elif isinstance(result, list):
            return [self._clean_result(item) for item in result]

        # 如果结果是字典
        elif isinstance(result, dict):
            return {k: self._clean_result(v) for k, v in result.items()}

        return result

    async def awrap_tool_call(self, request, handler):
        """
        异步拦截工具执行，清理 Playwright 返回的 DOM 数据

        重写 AgentMiddleware.awrap_tool_call 方法，
        不再依赖工具名称，直接基于内容格式检测并清理。

        同时处理超时错误，返回友好的错误信息。
        """
        # 调试日志：确认中间件被调用
        # request 是 ToolCallRequest 对象，包含 tool_call, tool, state, runtime
        tool_call = getattr(request, 'tool_call', None)
        tool_args = {}
        if tool_call:
            tool_name = tool_call.get('name', 'unknown')
            tool_id = tool_call.get('id', 'unknown')
            tool_args = tool_call.get('args', {}) or tool_call.get('arguments', {})
        else:
            tool_name = 'unknown'
            tool_id = 'unknown'

        # 🚀 P0-004: 跳过内部自动注入的工具调用（不清理 JS 检测结果）
        if tool_call and isinstance(tool_call, dict) and tool_call.get('_internal'):
            return await handler(request)

        logs.info(f"[DOMCleanerMiddleware] awrap_tool_call 被调用")
        logs.info(f"[DOMCleanerMiddleware]   - 工具名称: {tool_name}")
        logs.info(f"[DOMCleanerMiddleware]   - 工具 ID: {tool_id}")

        # 调用原始工具，捕获超时错误
        try:
            result = await handler(request)

            # 🆕 在清理前，提取并传递原始 HTML 给 SemanticSelectorMiddleware
            # browser_navigate/browser_snapshot: 返回页面快照
            # browser_evaluate: 可能返回 HTML 内容
            if tool_name in ['browser_navigate', 'browser_snapshot', 'browser_evaluate']:
                raw_content = self._extract_raw_content(result)
                if raw_content:
                    raw_html = self._extract_raw_html(raw_content)
                    if raw_html:
                        self._pass_raw_html_to_semantic_selector(tool_name, raw_html)
        except Exception as e:
            # 检查是否是超时错误
            error_str = str(e)
            is_timeout = 'TimeoutError' in error_str or 'Timeout' in error_str or 'timeout' in error_str.lower()

            if is_timeout:
                # 提取超时的 URL（如果有）
                url = ""
                if tool_args and 'url' in tool_args:
                    url = tool_args['url']

                # 构造友好的错误信息
                friendly_error = f"""## ⚠️ 操作超时

**错误类型**: 网络超时

**原因分析**:
1. 目标网站 `{url}` 无法访问或响应过慢
2. 网络连接不稳定
3. 目标网站可能暂时不可用

**建议操作**:
1. 请稍后重试
2. 检查网络连接是否正常
3. 确认目标网站是否可以正常访问

如果问题持续存在，请联系项目负责人或技术支持。
"""
                logs.error(f"[DOMCleanerMiddleware] 捕获超时错误: {tool_name} - {error_str}")

                # 返回 ToolMessage 格式的错误信息
                tool_call_id = tool_call.get('id', 'unknown') if tool_call else 'unknown'
                return ToolMessage(
                    content=friendly_error,
                    name=tool_name,
                    tool_call_id=tool_call_id,
                    status="error",
                )
            else:
                # 非超时错误，继续抛出
                raise

        # 调试日志：显示原始结果
        logs.info(f"[DOMCleanerMiddleware]   - 结果类型: {type(result).__name__}")
        if isinstance(result, str):
            logs.info(f"[DOMCleanerMiddleware]   - 原始长度: {len(result)} chars")
            # 检查是否包含 Playwright 特征
            has_playwright = self._contains_playwright_snapshot(result)
            logs.info(f"[DOMCleanerMiddleware]   - 包含 Playwright 特征: {has_playwright}")
        elif isinstance(result, list):
            logs.info(f"[DOMCleanerMiddleware]   - 列表长度: {len(result)}")
        elif isinstance(result, dict):
            logs.info(f"[DOMCleanerMiddleware]   - 字典 keys: {list(result.keys())}")

        # 清理结果
        cleaned_result = self._clean_result(result)

        # 调试日志：显示清理后结果长度
        if isinstance(cleaned_result, str) and isinstance(result, str):
            reduction = (len(result) - len(cleaned_result)) / len(result) * 100 if len(result) > 0 else 0
            logs.info(f"[DOMCleanerMiddleware]   - 清理后长度: {len(cleaned_result)} chars")
            logs.info(f"[DOMCleanerMiddleware]   - 压缩比例: {reduction:.1f}%")

        return cleaned_result
