# P0-003: 消除 `.first()` 无效回退

## 概述

消除代码生成管线中所有使用 `.first()` 作为盲猜回退的选择器模式。`.first()` 在宽泛选择器（如 `page.locator('input').first()`）上使用时，在多元素页面几乎必定定位到错误元素，是脚本失败的主要原因之一。

## 修改文件

- `tools/middleware/code_collector.py`
- `tools/middleware/semantic_selector.py`

## 原来实现逻辑

当语义选择器生成失败时，系统使用 `.first()` 作为兜底策略：

### code_collector.py 中的 4 处 `.first()` 回退

1. **click 回退**：`page.getByText('...').first().click()` — 文本匹配多个元素时取第一个
2. **fill 回退**：`page.locator('input').first().fill('...')` — 盲猜页面第一个 input
3. **hover 回退**：`page.locator('[cursor=pointer]').first().hover()` — 盲猜第一个可点击元素
4. **select 回退**：`page.locator('select').first().selectOption('...')` — 盲猜第一个 select

### semantic_selector.py 中的多处 `.first()` 回退

1. **快速路径**（`_generate_semantic_selector`）：
   - 用户名/邮箱框 → `page.locator('input[type="text"], input[type="email"]').first().fill(...)`
   - 通用文本框 → `page.locator('input[type="text"]').first().fill(...)`
   - element_hint getByText → `page.getByText('...').first().click()`

2. **候选路径**（`_generate_all_candidate_selectors`）：
   - CSS type 选择器 → `page.locator('input[type="text"]').first().fill(...)`
   - getByText 模糊匹配 → `page.getByText('...').first().click()`
   - role 无 name → `page.getByRole('button').first().click()`
   - CSS 回退 → `page.locator('input, select, textarea').first().fill(...)`
   - 位置选择器 → `page.locator('input').nth(1).fill(...)`

3. **规则路径**（`_generate_selector_from_rules`）：
   - 通用文本框 → `page.locator('input[type="text"]').first().fill(...)`
   - getByText → `page.getByText('...').first().click()`

4. **AI 提示词**：多处示例代码使用 `.first()` 作为推荐模式

## 当前实现逻辑

### 核心原则

- `.first()` 仅在 `.filter({ hasText: ... })` 或 `.locator(...)` 缩小范围后使用（作用域内 first）
- 宽泛选择器上的 `.first()` 全部替换为语义化选择器或 TODO 标记
- `{ exact: true }` 替代 `.first()` 解决 getByText 多匹配问题

### code_collector.py 修改

| 原来 | 现在 | 说明 |
|------|------|------|
| `getByText('...').first().click()` | `getByText('...', { exact: true }).click()` | 精确匹配替代 first |
| `locator('input').first().fill(...)` | `getByRole('textbox').filter({ hasText: /.*/ }).first().fill(...)` + TODO 注释 | 带过滤的 first + 人工确认标记 |
| `locator('[cursor=pointer]').first().hover()` | `getByText('...', { exact: true }).hover()` 或 `locator('[role]').filter({ hasText }).first().hover()` | 优先用元素描述文本 |
| `locator('select').first().selectOption(...)` | `getByLabel('...').selectOption(...)` 或 `getByRole('combobox').selectOption(...)` | 语义化选择器 |

### semantic_selector.py 修改

| 原来 | 现在 | 说明 |
|------|------|------|
| `locator('input[type="text"]').first().fill(...)` | `getByLabel('...').fill(...)` 或 `getByPlaceholder('...').fill(...)` | 使用 implicit_label/placeholder |
| `getByText('...').first().click()` | `getByText('...', { exact: true }).click()` | 精确匹配 |
| `getByRole('button').first().click()` | 删除此候选 | 无 name 的 role 选择器不生成 |
| `locator('input').nth(1).fill(...)` | 删除此候选 | 盲猜位置不生成 |
| `locator('input, select, textarea').first().fill(...)` | `getByRole('textbox').fill(...)` + TODO 注释 | 语义化 + 人工确认 |
| `locator('input[type="text"]').first().fill(...)` (候选路径) | 仅 password 类型保留（唯一性高），其他改用 getByLabel | password 通常页面唯一 |

### AI 提示词更新

- 所有示例代码中的 `.first()` 替换为语义化选择器
- 推荐模式从 `locator('input').first()` 改为 `getByLabel('...')`、`getByPlaceholder('...')`
- 规则3 从"位置选择器"改为"组合选择器"（filter + first）

### 保留的 `.first()` 使用（合理场景）

以下场景的 `.first()` 是合理的，因为已通过 `.filter()` 或 `.locator()` 缩小了范围：

```typescript
// ✅ 合理：先通过 filter 缩小到特定 form-item，再取第一个可点击元素
page.locator('.el-form-item').filter({ hasText: 'UOM' }).locator('[cursor=pointer]').first().click()

// ✅ 合理：先通过 filter 缩小范围，再取第一个
page.getByRole('textbox').filter({ hasText: /.*/ }).first().fill('...')
```

## 主要修复点

1. **code_collector.py**：4 处 `.first()` 回退全部替换为语义化选择器或 `{ exact: true }`
2. **semantic_selector.py 快速路径**：用户名/邮箱/通用文本框改用 `getByLabel`/`getByPlaceholder`
3. **semantic_selector.py 候选路径**：删除 role 无 name 候选、删除 nth 盲猜候选、CSS type 仅保留 password
4. **semantic_selector.py 规则路径**：通用文本框不再返回 `.first()`，让后续规则处理
5. **AI 提示词**：所有示例和推荐模式更新为语义化选择器

## 预期效果

- 消除 `page.locator('input').first()` 类必定失败的代码
- getByText 使用 `{ exact: true }` 减少 strict mode violation
- 脚本可执行率预计提升 ~5%（从 40% → 45%，与 P0-001/P0-002 叠加后达 ~60%）
