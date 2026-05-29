# P1-002: 统一两套选择器生成逻辑

> 完成日期：2026-03-24

## 原来实现逻辑

系统存在两条并行的选择器生成路径：

### 快速路径：`_generate_semantic_selector`（~270 行 if-elif 链）
- 硬编码优先级：JS推荐 → testid → role+name → CSS type → getByLabel → getByPlaceholder → getByText → hint_text
- 优先级由 if-elif 顺序决定，不使用评分常量
- 被 `get_semantic_code` 调用（CodeCollectorMiddleware 的入口）

### 候选排序路径：`_generate_all_candidate_selectors` + `_generate_semantic_selector_realtime`
- 为每个元素生成所有候选选择器
- 使用 K_* 评分常量排序
- 被 `awrap_tool_call` 中的实时生成流程调用

### 优先级不一致

| 选择器类型 | 快速路径优先级 | 候选路径分数 | 矛盾 |
|-----------|---------------|-------------|------|
| CSS type（password/text） | 第 3 位（在 getByLabel 之前） | 520 分 | 快速路径更优先 |
| getByLabel | 第 4 位 | 140 分 | 候选路径更优先 |
| getByPlaceholder | 第 5 位 | 120 分 | 候选路径更优先 |

## 当前实现逻辑

重构 `_generate_semantic_selector` 为三层结构：

### 第一层：快速路径（保留，处理 60-70% 的简单场景）
1. JS 推荐选择器（score < 300 且唯一）→ 直接使用
2. getByTestId → 直接使用
3. button/link + name → getByRole 直接使用

### 第二层：候选排序路径（新增，处理复杂场景）
```python
candidates = self._generate_all_candidate_selectors(element_info, action, value)
if candidates:
    best_selector, best_score = candidates[0]
    return best_selector
```

所有表单元素（textbox、combobox、checkbox 等）的选择器生成统一走候选排序，由 K_* 评分常量决定优先级，消除了 if-elif 链中的优先级不一致。

### 第三层：hint_text 兜底（保留）
当候选排序也无法生成时，使用 element_hint 解析的 inferred_role + label_text 生成。

### 关键变化

| 场景 | 旧行为 | 新行为 |
|------|--------|--------|
| `input[type="password"]` | 快速路径直接生成 CSS 选择器（520 分） | 候选排序，getByLabel 优先（140 分） |
| textbox + implicit_label | 快速路径 getByLabel（第 4 位） | 候选排序，getByPlaceholder 可能更优（120 分） |
| textbox + placeholder | 快速路径 getByPlaceholder（第 5 位） | 候选排序，正确排在 getByLabel 之后 |

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| 删除 ~150 行 if-elif 链 | 表单元素的 CSS type、getByLabel、getByPlaceholder 等分支全部删除 |
| 委托给 `_generate_all_candidate_selectors` | 复杂场景统一走候选排序 |
| 保留三个快速路径 | JS 推荐、testid、button/link 仍走快速路径（高确定性场景） |
| 优先级统一 | 所有选择器类型的优先级由 K_* 评分常量决定 |
