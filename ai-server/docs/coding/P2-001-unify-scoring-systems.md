# P2-001: 统一两套评分体系

> 完成日期：2026-03-24

## 原来实现逻辑

系统存在两套独立的评分体系：

1. **Codegen 分数**（`K_*` 常量，范围 1 ~ 10000000）：用于 `_generate_all_candidate_selectors` 候选排序
2. **质量分数**（0.0 ~ 1.0）：用于 `_evaluate_selector_quality` 脚本质量评估

两套评分排序不一致：

| 选择器 | Codegen 分数 | 旧质量分数 | 矛盾 |
|--------|-------------|----------|------|
| getByTestId | 1（最优） | 0.90 | Codegen 认为最优，质量评估认为次优 |
| getByRole+name | 100 | 0.95（最优） | 质量评估认为最优，Codegen 认为次优 |
| getByPlaceholder | 120 | 0.70 | 排序差异大 |
| getByText | 180 | 0.65 | 排序基本一致 |

## 当前实现逻辑

`_evaluate_selector_quality` 改为基于 Codegen 分数归一化：

1. 识别选择器类型 → 映射到对应的 `K_*` 常量
2. 使用对数缩放归一化到 0-1：`quality = 1.0 - log(score+1) / log(10000001)`
3. 排序与 Codegen 候选排序完全一致

归一化后的对应关系：

| 选择器 | Codegen 分数 | 归一化质量分 |
|--------|-------------|-------------|
| getByTestId | 1 | 0.957 |
| getByRole+name | 100 | 0.714 |
| getByPlaceholder | 120 | 0.703 |
| getByLabel | 140 | 0.693 |
| getByText | 180 | 0.677 |
| CSS ID | 500 | 0.614 |
| CSS name | 515 | 0.611 |
| .nth() | 10000 | 0.428 |
| CSS fallback | 10000000 | 0.000 |

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| 重写 `_evaluate_selector_quality` | 基于 Codegen 分数归一化，不再硬编码质量分 |
| 对数缩放 | 使用 `math.log` 处理 1~10000000 的巨大跨度 |
| 细化 CSS 选择器识别 | 区分 CSS ID（`#`）、CSS name（`[name=]`）、一般 CSS |
| `page.evaluate` 识别 | 映射到 `K_CSS_FALLBACK_SCORE`（最差） |
