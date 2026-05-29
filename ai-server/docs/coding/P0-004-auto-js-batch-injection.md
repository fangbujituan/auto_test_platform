# P0-004: 一次性 JS 批量属性提取（自动注入）

## 概述

将 JS 注入检测从"被动等待 Agent 调用"改为"中间件自动触发"。在 `browser_navigate` 或 `browser_snapshot` 返回后，中间件自动调用 `browser_evaluate` 工具执行 JS 检测脚本，确保 JS 检测覆盖率达到 100%。

## 修改文件

- `tools/middleware/semantic_selector.py` — 核心：自动注入逻辑 + 工具缓存 + 结果解析
- `tools/playwright/recording_agent.py` — 工具列表传递

## 原来实现逻辑

### 被动提示方式

```
browser_navigate 返回
  → SemanticSelector.update_snapshot() 解析快照
  → _append_html_fetch_hint() 追加文本提示
  → [等待] Agent 看到提示后主动调用 browser_evaluate(JS_INTERACTIVE_DETECTOR)
  → process_js_detection_result() 合并到缓存
```

问题：
- Agent 可能忽略提示，跳过 JS 检测
- JS 检测覆盖率取决于 Agent 行为，不可控
- 额外消耗 token（提示文本 ~500 tokens）
- Agent 需要额外一轮对话才能执行 JS 检测

## 当前实现逻辑

### 自动注入方式（直接工具调用）

```
make_recording_agent() 加载 playwright_tools
  → semantic_selector.set_tools(playwright_tools)
    → 查找并缓存 browser_evaluate 工具实例
    → 打印工具 schema（用于调试参数名）

browser_navigate / browser_snapshot 返回
  → SemanticSelector.update_snapshot() 解析快照
  → _auto_inject_js_detection() 自动执行 JS 检测
    → _find_browser_evaluate_tool() 获取缓存的工具实例
    → _detect_evaluate_param_name() 从 schema 检测必填参数名
    → IIFE 格式转换：(() => {...})() → () => {...}
    → evaluate_tool.ainvoke({param_name: js_function})
    → 解析 MCP content blocks 返回格式
    → raw_decode 处理多段 JSON 拼接
  → process_js_detection_result() 合并到缓存
  → 后续操作直接使用完整的元素属性
```

## 调试过程与踩坑记录

### 问题1：无法找到 browser_evaluate 工具实例

**现象**：`'InternalRequest' object has no attribute 'tool'`

**原因**：最初尝试构造 `InternalRequest` 通过 `handler()` 执行，但 LangGraph 的 handler 根据 `request.tool`（工具对象实例）路由，不是根据 `tool_call['name']` 字符串路由。我们无法从 request 对象中获取其他工具的实例。

**解决**：改为在 `make_recording_agent()` 加载 `playwright_tools` 后，调用 `semantic_selector.set_tools(playwright_tools)` 显式传入工具列表，预缓存 `browser_evaluate` 工具实例。然后用 `evaluate_tool.ainvoke()` 直接调用（绕过中间件链）。

### 问题2：参数名错误 — `url` 验证失败

**现象**：`Invalid input: expected string, received undefined, path: ["url"]`

**原因**：最初硬编码参数名为 `function`，但 MCP 返回 `url` 字段验证错误。后来改为自动检测，但 `_detect_evaluate_param_name` 的优先级列表把 `expression` 排在 `function` 前面，而 schema 里根本没有 `expression`，走到了默认回退 `expression`。

**解决**：重写 `_detect_evaluate_param_name()`，从工具的 `args_schema` 中读取 `required` 字段，优先使用必填的 string 参数。Playwright MCP `browser_evaluate` 的实际 schema 是：
```json
{
  "properties": {
    "function": {"type": "string", "description": "() => { /* code */ } ..."},
    "element": {"type": "string", "description": "..."}
  },
  "required": ["function"]
}
```

### 问题3：函数序列化失败

**现象**：`Passed function is not well-serializable!`

**原因**：`JS_INTERACTIVE_DETECTOR` 是 IIFE 格式 `(() => { ... })()`，而 Playwright MCP 的 `function` 参数期望可序列化的函数定义 `() => { ... }`（内部调用 `page.evaluate(fn)`）。IIFE 带了末尾的 `()` 调用，不是合法的函数定义。

**解决**：用正则 `re.match(r'^\((.+)\)\(\);?\s*$', js_script, re.DOTALL)` 将 IIFE 转换为纯函数定义，去掉外层的 `(` 和末尾的 `)()`。

### 问题4：ainvoke 返回类型不是 str

**现象**：`Expecting value: line 1 column 1 (char 0)` — JSON 解析空字符串

**原因**：`evaluate_tool.ainvoke()` 返回的是 `list[dict]`（MCP content blocks 格式），不是 `str`。格式为：
```python
[{'type': 'text', 'text': '### Result\n{"elements": [...], ...}'}]
```
之前的代码用 `str(js_raw_result)` 转换，得到的是 Python repr 字符串，不是有效 JSON。

**解决**：正确解析 MCP content blocks，遍历 list 提取 `type == 'text'` 的 `text` 字段拼接。

### 问题5：多段 JSON 拼接

**现象**：`Extra data: line 13 column 1 (char 225)` — JSON 后面有多余内容

**原因**：MCP 可能返回多个 content blocks，拼接后变成两段 JSON。`json.loads()` 只能解析单个 JSON 值。

**解决**：先尝试 `json.loads()`，失败后用 `json.JSONDecoder().raw_decode()` 只解析第一个完整的 JSON 对象，忽略后面的多余内容。

## 核心代码

### 1. 工具注入（recording_agent.py）

```python
# make_recording_agent() 中，加载 MCP 工具后：
playwright_tools = await load_mcp_tools(playwright_session)
semantic_selector.set_tools(playwright_tools)  # 🚀 P0-004
```

### 2. set_tools() 方法

```python
def set_tools(self, tools: list):
    self._available_tools = tools
    for t in tools:
        if getattr(t, 'name', '') == 'browser_evaluate':
            self._browser_evaluate_tool = t
            # 打印 schema 用于调试
            break
```

### 3. _detect_evaluate_param_name() 方法

```python
def _detect_evaluate_param_name(self, evaluate_tool) -> str:
    """从 args_schema 的 required 字段检测必填 string 参数名"""
    schema = getattr(evaluate_tool, 'args_schema', None)
    schema_dict = schema.schema()  # Pydantic v1
    required = schema_dict.get('required', [])
    properties = schema_dict.get('properties', {})
    
    # 优先使用 required 中的第一个 string 参数
    for req_field in required:
        if properties.get(req_field, {}).get('type') == 'string':
            return req_field  # → 'function'
    
    return 'function'  # 默认值
```

### 4. IIFE → 函数定义转换

```python
js_to_send = js_script.strip()
iife_match = re.match(r'^\((.+)\)\(\);?\s*$', js_to_send, re.DOTALL)
if iife_match:
    js_to_send = iife_match.group(1).strip()
    # (() => { ... })() → () => { ... }
```

### 5. MCP content blocks 解析

```python
if isinstance(js_raw_result, list):
    text_parts = []
    for block in js_raw_result:
        if isinstance(block, dict) and block.get('type') == 'text':
            text_parts.append(block.get('text', ''))
    js_content = '\n'.join(text_parts)
```

### 6. 多段 JSON 容错

```python
try:
    js_data = json.loads(js_content)
except json.JSONDecodeError:
    decoder = json.JSONDecoder()
    js_data, _ = decoder.raw_decode(js_content)  # 只取第一个 JSON 对象
```

## 实例变量

| 变量 | 类型 | 说明 |
|------|------|------|
| `_available_tools` | `List[Any]` | 外部注入的工具列表 |
| `_browser_evaluate_tool` | `Any` | 缓存的 browser_evaluate 工具实例 |
| `_evaluate_param_name` | `Optional[str]` | 缓存的参数名（检测一次后复用） |
| `_js_auto_injected_url` | `Optional[str]` | 已注入的 URL，避免重复 |
| `_js_auto_inject_enabled` | `bool` | 是否启用自动注入（默认 True） |

## 注入时机

| 触发工具 | 注入条件 | 说明 |
|----------|----------|------|
| `browser_navigate` | URL 变化时 | 通过 `_js_auto_injected_url` 去重 |
| `browser_snapshot` | 每次都注入 | 页面可能已变化（AJAX 加载等） |

## 容错机制

- JS 注入失败不影响主流程（try-except 包裹）
- `browser_evaluate` 不可用时自动禁用（`_js_auto_inject_enabled = False`）
- 禁用后回退到原来的被动提示方式（`_append_html_fetch_hint`）

## 预期效果

- JS 检测覆盖率从"依赖 Agent 行为"提升到 **100%**
- 每次页面导航/快照后，元素缓存自动包含完整的 HTML 属性
- 选择器生成质量大幅提升（不再依赖纯快照信息猜测）
- 减少 Agent 对话轮次（不再需要额外一轮执行 JS 检测）
- Token 消耗减少（去掉 ~500 tokens 的被动提示文本）
