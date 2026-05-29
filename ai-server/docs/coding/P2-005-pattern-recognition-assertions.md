# P2-005: 操作序列模式识别 + 断言生成

> 完成日期：2026-03-24

## 原来实现逻辑

`CodeCollectorMiddleware` 逐操作独立生成代码，缺少两个能力：

1. **无断言**：生成的脚本只有操作代码（goto、click、fill），没有 `expect` 断言，只能验证"不报错"，无法验证"操作结果正确"
2. **无模式识别**：连续的登录操作（navigate + fill + fill + click）、表单填写（连续 fill）、搜索（fill + click）等常见模式没有被识别和标注

## 当前实现逻辑

### 1. 操作序列跟踪

新增 `_operation_sequence` 列表，在 `awrap_tool_call` 中记录每个 browser_* 操作：

```python
self._operation_sequence.append({
    'tool': tool_name,
    'args': tool_args,
    'url': self._current_url,
})
```

### 2. 模式识别（`_detect_pattern_and_comment`）

检测最近操作序列，识别三种常见模式并插入结构化注释：

| 模式 | 识别条件 | 生成注释 |
|------|----------|----------|
| 登录 | navigate + type + type + click | `// === 登录流程 ===` |
| 表单填写 | 连续 3+ 个 type | `// === 表单填写（N 个字段）===` |
| 搜索/筛选 | type + click(含搜索关键词) | `// === 搜索/筛选操作 ===` |

### 3. 断言生成（`_generate_assertion`）

在工具返回后，根据操作类型生成断言：

| 操作 | 断言 |
|------|------|
| `browser_navigate` | `await expect(page).toHaveURL(/path-pattern/);` |
| 提交类 `browser_click` | `await expect(page.getByText(/成功\|success\|saved\|completed/i)).toBeVisible({ timeout: 10000 });` |
| 其他操作 | 不生成断言（中间操作） |

### 4. 集成到 `awrap_tool_call`

```
工具调用前:
  → _track_operation()     跟踪操作
  → _detect_pattern_and_comment()  检测模式，插入注释
  → _generate_code_from_tool_call()  生成操作代码

工具调用后:
  → _generate_assertion()  生成断言代码
```

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| `_operation_sequence` | 新增操作序列跟踪列表 |
| `_track_operation` | 记录每个 browser_* 操作 |
| `_detect_pattern_and_comment` | 识别登录/表单/搜索三种模式 |
| `_generate_assertion` | navigate 后验证 URL，提交后验证成功提示 |
| `awrap_tool_call` 集成 | 操作前插入模式注释，操作后插入断言 |
