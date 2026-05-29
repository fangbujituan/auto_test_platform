# P2-002: aria-labelledby 解析

> 完成日期：2026-03-24

## 原来实现逻辑

JS 端 `extractElementInfo` 已经提取了 `ariaLabelledby` 属性值，但存在两个缺失：

1. **JS 端**：`generatePlaywrightSelector` 中未使用 `ariaLabelledby` 生成 `getByLabel` 候选
2. **Python 端**：`_merge_js_detection_to_cache` 中未将 `ariaLabelledby` 合并到元素缓存

`aria-labelledby` 是 WCAG 标准的标签关联方式，很多 UI 框架（Ant Design、Element UI）使用它而非 `label[for]`。完全忽略这个信息源导致 `getByLabel` 命中率偏低。

## 当前实现逻辑

### JS 端

在 `generatePlaywrightSelector` 中新增第 6 步 `aria-labelledby` 解析：

```javascript
// 6. aria-labelledby 关联（通过 ID 查找关联元素的文本）
if (info.ariaLabelledby) {
    const ids = info.ariaLabelledby.split(/\s+/);
    const labelParts = [];
    for (const id of ids) {
        const labelEl = document.getElementById(id);
        if (labelEl) {
            const text = (labelEl.textContent || '').trim();
            if (text) labelParts.push(text);
        }
    }
    const labelText = labelParts.join(' ');
    if (labelText && labelText.length <= 80) {
        candidates.push({
            type: 'getByLabel',
            code: `page.getByLabel('${escapeString(labelText)}')`,
            score: SCORE.LABEL,
            reason: 'aria-labelledby association'
        });
    }
}
```

支持多 ID 关联（`aria-labelledby="id1 id2"`），将多个关联元素的文本拼接为完整 label。

### Python 端

在 `_merge_js_detection_to_cache` 的属性合并区域新增：

```python
js_aria_labelledby = js_elem.get('ariaLabelledby')
if js_aria_labelledby and not cached_elem.get('aria-labelledby'):
    cached_elem['aria-labelledby'] = js_aria_labelledby
    updated = True
```

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| JS 端 `generatePlaywrightSelector` 新增 aria-labelledby | 通过 ID 查找关联元素文本，生成 `getByLabel` 候选 |
| 支持多 ID 关联 | `aria-labelledby="id1 id2"` → 拼接多个元素文本 |
| Python 端缓存合并 | `_merge_js_detection_to_cache` 保存 `aria-labelledby` 到缓存 |
| 评分使用 `SCORE.LABEL` | 与 `label[for]` 关联同等优先级（140 分） |
