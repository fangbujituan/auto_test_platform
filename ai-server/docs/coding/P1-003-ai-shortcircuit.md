# P1-003: AI 选择短路优化

## 概述

当规则系统已生成高质量候选选择器（分数 ≤ 200）时，跳过 AI 调用直接使用，减少不必要的 token 消耗。

## 修改文件

- `tools/middleware/semantic_selector.py` — `_generate_semantic_selector_realtime` 方法

## 原来实现逻辑

每次操作都经过完整的 4 步流程：
1. 规则系统生成候选
2. 合并浏览器端候选
3. **AI 从候选中选择最佳**（每次 500-2000 tokens）
4. 最终验证

即使最佳候选已经是 `getByTestId`（分数=1，最优），仍然调用 AI。

## 当前实现逻辑

在 Step 2（合并候选）和 Step 3（AI 选择）之间增加短路判断：

```python
# 分数 <= 200 且不包含 ref 且唯一性验证通过
if (best_candidate_score <= 200 
    and not self._contains_ref_selector(best_candidate_selector)
    and best_candidate_unique is not False):
    return best_candidate_selector  # 直接使用，跳过 AI
```

分数 ≤ 200 覆盖的选择器类型：
- getByTestId (1)
- getByRole+name (100)
- aria-label (110)
- getByPlaceholder (120)
- getByLabel (140)
- getByText (180)
- title (200)

## 主要修复点

1. `_generate_semantic_selector_realtime` 中候选列表生成后、AI 调用前，增加短路判断
2. 短路条件：分数 ≤ 200 + 无 ref + 唯一性非 False

## 预期效果

- AI 调用减少 60-70%（大部分简单操作如按钮点击、链接跳转都能短路）
- 每个脚本节省 15K-25K tokens
- 选择器生成延迟降低（跳过 AI 网络往返）
