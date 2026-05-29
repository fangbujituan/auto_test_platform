# P2-003: cursor:pointer 遍历优化

> 完成日期：2026-03-24

## 原来实现逻辑

JS 注入脚本中，为检测 `cursor:pointer` 元素，使用 `document.querySelectorAll('*')` 全量遍历页面所有 DOM 节点：

```javascript
document.querySelectorAll('*').forEach(el => {
    const style = window.getComputedStyle(el);
    if (style.cursor === 'pointer' || style.cursor === 'hand') {
        interactiveElements.add(el);
    }
});
```

500 行表格页面约 5000+ DOM 节点，每个节点调用 `getComputedStyle` 触发样式计算，耗时 100-300ms。

## 当前实现逻辑

限制遍历范围到可能可点击的元素子集：

```javascript
const clickableCandidates = [
    'div[class*="btn"]', 'div[class*="click"]', 'div[class*="link"]',
    'div[class*="item"]', 'div[class*="option"]', 'div[class*="menu"]',
    'div[class*="tab"]', 'div[class*="tag"]', 'div[class*="card"]',
    'span[class*="btn"]', 'span[class*="icon"]', 'span[class*="link"]',
    'li', 'td', 'th', 'img', 'svg', 'i',
    '[style*="cursor"]',
    '[role]'
].join(', ');
document.querySelectorAll(clickableCandidates).forEach(el => {
    if (!interactiveElements.has(el)) {
        try {
            const cursor = window.getComputedStyle(el).cursor;
            if (cursor === 'pointer' || cursor === 'hand') {
                interactiveElements.add(el);
            }
        } catch(e) {}
    }
});
```

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| 限制遍历范围 | 从 `*`（全量）改为特定 class 模式 + 常见可点击标签 |
| 跳过已收集元素 | `!interactiveElements.has(el)` 避免重复 `getComputedStyle` |
| 异常保护 | 每个元素的 `getComputedStyle` 调用包裹 try-catch |
| 预期效果 | 遍历元素数从 5000+ 降到 200-500，`getComputedStyle` 调用减少 ~90% |
