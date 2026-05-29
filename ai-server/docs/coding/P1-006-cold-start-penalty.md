# P1-006: 新脚本冷启动惩罚 + 静态代码分析

## 概述

解决新脚本因默认 `success_rate=1.0` 导致质量分数虚高的问题，同时增加静态代码分析能力。

## 修改文件

- `tools/playwright/script_index.py` — `_calculate_quality_score` 方法

## 原来实现逻辑

```python
score = success_rate * 0.4 + semantic_ratio * 0.3 + has_code * 0.2 + usage * 0.1
```

新脚本（`usage_count=0`、`success_rate=1.0`、`has_code=True`）得分 = 0.4 + 0.15 + 0.2 + 0 = 0.75，高于多次执行但偶有失败的脚本。

另外，手动编写的脚本因 `ref_count=0, semantic_count=0`（运行时统计为空），语义比例维度只能拿到中等分数 0.15。

## 当前实现逻辑

### 1. 冷启动惩罚

```python
if entry.usage_count < 3:
    score *= 0.7  # 30% 惩罚
```

新脚本得分：0.75 × 0.7 = 0.525，不再高于经过验证的脚本。

### 2. 静态代码分析

当运行时统计为空（`ref_count=0, semantic_count=0`）但有代码文件时，直接扫描 `.spec.ts` 文件统计选择器类型：

```python
if entry.has_code and total_selectors == 0:
    code = script_path.read_text(encoding='utf-8')
    ref_count, semantic_count = self._count_selectors(code)
    # 使用静态分析结果计算语义比例
```

## 主要修复点

1. `_calculate_quality_score` 末尾：`usage_count < 3` 时分数打 70% 折扣
2. 语义比例计算：当运行时统计为空时，回退到静态代码分析

## 预期效果

- 新脚本不再因默认值虚高排在已验证脚本前面
- 手动编写的高质量脚本也能获得准确的语义比例评分
- 自动清理时不会误删经过验证的脚本
