# P0-002: JS 端唯一性验证

> 完成日期：2026-03-24
> 优先级：P0
> 涉及文件：`tools/middleware/semantic_selector.py`

---

## 问题描述

JS 注入脚本（`JS_INTERACTIVE_DETECTOR`）为每个可交互元素生成选择器候选列表并评分，但没有验证选择器在页面上是否唯一匹配。Playwright strict mode 要求选择器只匹配一个元素，否则抛出 `strict mode violation`。

在 43 次测试运行中，约 35% 的失败是选择器错误，其中 strict mode violation 是最常见的子类。

## 原来实现逻辑

### JS 端（`generatePlaywrightSelector`）

为每个元素生成候选选择器列表，按分数排序后返回：

```javascript
candidates.sort((a, b) => a.score - b.score);
return candidates;
```

候选只有 `type`、`code`、`score`、`reason` 四个字段，没有 `unique` 和 `matchCount`。

### Python 端（`_merge_js_detection_to_cache`）

保存 JS 推荐选择器到缓存：

```python
cached_elem['_js_best_selector'] = js_best_selector.get('code')
cached_elem['_js_score'] = js_best_selector.get('score', 999999)
cached_elem['_js_selector_reason'] = js_best_selector.get('reason')
```

### Python 端（`_generate_semantic_selector`）

直接使用 JS 推荐选择器，只检查分数 < 300：

```python
if js_best_selector and js_score < 300:
    return f"await {js_best_selector}.click();"
```

不检查唯一性，即使选择器匹配多个元素也直接使用。

## 当前实现逻辑

### JS 端新增 `verifyUniqueness` 函数

在 `generatePlaywrightSelector` 排序前，对每个候选执行唯一性验证：

```javascript
candidates.forEach(c => verifyUniqueness(c, el));
candidates.sort((a, b) => a.score - b.score);
```

`verifyUniqueness` 针对不同选择器类型使用不同验证策略：

| 选择器类型 | 验证方式 | 说明 |
|-----------|---------|------|
| `locator('#id')` | `querySelectorAll('#id').length` | CSS ID 精确计数 |
| `locator('[name="x"]')` | `querySelectorAll('[name="x"]').length` | CSS 属性精确计数 |
| `getByTestId('x')` | `querySelectorAll('[data-testid="x"]').length` | data-testid 精确计数 |
| `getByRole('button', {name: 'x'})` | 收集 role 匹配元素 + 文本过滤 | 近似验证 |
| `getByText('x')` | 遍历文本节点计数 | 近似验证 |
| `getByPlaceholder('x')` | `querySelectorAll('[placeholder="x"]').length` | 精确计数 |
| `getByLabel('x')` | 匹配 label 元素文本 | 近似验证 |

验证结果影响分数：
- `matchCount === 1`（唯一）：不加分，标记 `[UNIQUE]`
- `matchCount > 1`（非唯一）：+5000 分，标记 `[NOT UNIQUE: N matches]`
- `matchCount === 0`（无匹配）：+10000 分，标记 `[NO MATCH]`

### Python 端 `_merge_js_detection_to_cache` 新增字段

```python
cached_elem['_js_unique'] = js_best_selector.get('unique')
cached_elem['_js_match_count'] = js_best_selector.get('matchCount')
```

### Python 端 `_generate_semantic_selector` 增加唯一性检查

```python
if js_best_selector and js_score < 300:
    if js_unique is False:
        # 非唯一选择器不直接使用，降级到本地生成
        logs.warning(...)
    else:
        # 唯一或未验证，正常使用
        return f"await {js_best_selector}.click();"
```

### Python 端 `_generate_all_candidate_selectors` 注入 JS 候选

在候选生成函数开头，将 JS 端的候选列表（含唯一性验证后的分数）注入到本地候选中：

```python
js_candidates = element_info.get('_js_selector_candidates', [])
for jc in js_candidates:
    # JS 端已对非唯一候选加了 5000+ 分，直接使用
    candidates.append((full_code, jc_score))
```

这样非唯一的 JS 候选会因为高分被排到后面，唯一的 JS 候选会因为低分被优先选择。

## 主要修复点

1. **JS 端**：新增 `verifyUniqueness` 函数（~80 行），支持 7 种选择器类型的唯一性验证
2. **JS 端**：在 `generatePlaywrightSelector` 排序前调用 `verifyUniqueness`
3. **Python 端**：`_merge_js_detection_to_cache` 新增保存 `_js_unique` 和 `_js_match_count`
4. **Python 端**：`_generate_semantic_selector` 增加唯一性检查，非唯一选择器降级到本地生成
5. **Python 端**：`_generate_all_candidate_selectors` 注入 JS 候选（含唯一性分数惩罚）

## 预期效果

- strict mode violation 错误减少 60-80%
- 非唯一选择器在候选排序中被自动降级，唯一选择器被优先选择
- 预计脚本通过率提升 ~5%（选择器错误中的 strict mode violation 子类）
