# P3-002: 相似脚本检测改进

> 完成日期：2026-03-24

## 原来实现逻辑

`find_similar_scripts` 使用三个维度判断相似度：

1. URL 模式匹配（权重 0.4）
2. 关键词重叠（权重 0.4）
3. 脚本名称相似度（权重 0.2）— 使用 `SequenceMatcher` 比较名称

问题：名称相似但功能不同的脚本可能被误判为重复（如 `add_billing_item` vs `edit_billing_item`），而名称不同但功能相同的脚本可能被遗漏。

## 当前实现逻辑

新增操作序列相似度维度，调整权重分配：

| 维度 | 旧权重 | 新权重 | 说明 |
|------|--------|--------|------|
| URL 模式匹配 | 0.4 | 0.3 | 降低，因为同 URL 可能有不同操作 |
| 关键词重叠 | 0.4 | 0.3 | 降低 |
| 操作序列相似度 | — | 0.25 | 新增，从 .spec.ts 提取操作序列 |
| 名称相似度 | 0.2 | 0.15 | 降低 |

### 操作序列提取（`_extract_operation_sequence`）

从 `.spec.ts` 文件中提取操作类型序列：

```python
# 输入: add_billing_item.spec.ts
# 输出: ['goto', 'fill', 'fill', 'fill', 'click', 'wait', 'expect']
```

支持 12 种操作类型：goto、fill、click、hover、select、press、check、uncheck、wait、expect、screenshot、evaluate。

跳过注释行，每行只取第一个操作。

### 相似度计算

使用 `SequenceMatcher` 比较两个脚本的操作序列：
- `['goto', 'fill', 'fill', 'click']` vs `['goto', 'fill', 'fill', 'fill', 'click']` → 高相似度
- `['goto', 'fill', 'fill', 'click']` vs `['goto', 'click', 'click', 'click']` → 低相似度

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| `_extract_operation_sequence` | 从 .spec.ts 提取操作序列 |
| 操作序列相似度 | 新增维度，权重 0.25 |
| 权重重新分配 | URL 0.3 + 关键词 0.3 + 操作序列 0.25 + 名称 0.15 |
