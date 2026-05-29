# P3-001: LRU 缓存限制

> 完成日期：2026-03-24

## 原来实现逻辑

`SemanticSelectorMiddleware` 中有 7+ 个 dict 缓存，全部无大小限制：

- `_element_cache`：元素语义缓存
- `_snapshot_context_cache`：快照上下文缓存
- `_ai_generated_code`：AI 生成代码缓存
- `_html_element_attrs`：HTML 元素属性缓存
- `_ref_to_html_attrs`：ref→HTML 属性映射
- `_xpath_to_js_attrs`：xpath→JS 属性映射
- `_js_best_selector_map`：xpath→JS 最佳选择器映射

长时间运行（多轮对话、多页面操作）时，缓存持续增长，内存占用不断上升。

## 当前实现逻辑

新增 `_CACHE_MAX_SIZE = 500` 限制和 `_trim_caches()` 方法：

```python
def _trim_caches(self):
    max_size = self._CACHE_MAX_SIZE
    for cache in [self._element_cache, self._snapshot_context_cache, 
                  self._ai_generated_code, self._html_element_attrs,
                  self._ref_to_html_attrs, self._xpath_to_js_attrs,
                  self._js_best_selector_map]:
        if len(cache) > max_size:
            excess = len(cache) - max_size
            keys_to_remove = list(cache.keys())[:excess]
            for key in keys_to_remove:
                del cache[key]
```

利用 Python 3.7+ dict 保持插入顺序的特性，移除最旧的条目（近似 LRU）。

在 `_update_cache` 中调用 `_trim_caches()`，每次更新缓存时检查大小。

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| `_CACHE_MAX_SIZE = 500` | 统一的缓存大小限制 |
| `_trim_caches()` | 遍历所有 dict 缓存，超限时移除最旧条目 |
| 集成到 `_update_cache` | 每次缓存更新后自动检查 |
