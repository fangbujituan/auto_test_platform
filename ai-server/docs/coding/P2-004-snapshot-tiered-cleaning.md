# P2-004: 快照分级清理

> 完成日期：2026-03-24

## 原来实现逻辑

`DOMCleanerMiddleware` 使用单一阈值 `SNAPSHOT_SUMMARY_THRESHOLD = 20000`，清理后仍超过 20K 字符时直接生成摘要：

```python
if len(cleaned) > self.SNAPSHOT_SUMMARY_THRESHOLD:
    return self._generate_snapshot_summary(content, cleaned)
```

摘要只保留前 3 个交互元素的详细信息，大量元素的 ref 信息丢失，导致后续选择器生成完全失效。

虽然 P0-001 的重复行截断已大幅减少快照大小，但某些复杂页面（多区域表单、嵌套组件）仍可能超过阈值。

## 当前实现逻辑

替换为三级渐进式清理：

```
原始清理后大小
  ├── ≤ 20K → 直接返回（无额外处理）
  ├── > 20K → Tier1 中度清理
  │   ├── ≤ 40K → 返回
  │   └── > 40K → Tier2 重度清理
  │       ├── ≤ 60K → 返回
  │       └── > 60K → 摘要兜底（极端情况）
```

### Tier1 中度清理（`_tier1_clean`）
- 只保留有 `[ref=]` 的元素行
- 保留 ref 行的直接父级行（维持结构上下文）
- 保留页面头部信息（URL、Title 等）
- 移除纯结构行（没有 ref 的 generic、group 等容器）

### Tier2 重度清理（`_tier2_clean`）
- 只保留交互元素行（button、link、textbox、checkbox、radio、combobox 等 14 种类型）
- 保留页面头部信息
- 保留截断注释行（来自 P0-001 的重复行截断）

### 阈值配置
```python
SNAPSHOT_TIER1_THRESHOLD = 20000   # 中度清理
SNAPSHOT_TIER2_THRESHOLD = 40000   # 重度清理
SNAPSHOT_SUMMARY_THRESHOLD = 60000 # 摘要兜底
```

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| 三级阈值替代单一阈值 | 20K/40K/60K 渐进式清理 |
| `_tier1_clean` | 保留 ref 行 + 父级行，移除纯结构行 |
| `_tier2_clean` | 只保留 14 种交互元素类型 |
| 摘要退化延后 | 从 20K 提升到 60K 才触发摘要，大幅减少信息丢失 |
