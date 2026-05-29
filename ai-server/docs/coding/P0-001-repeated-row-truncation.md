# P0-001: 重复行截断（列表/表格数据去重）

> 完成日期：2026-03-24
> 优先级：P0
> 涉及文件：`tools/utils/dom_utils.py`、`tools/middleware/dom_cleaner.py`

---

## 问题描述

快照过大的根本原因是列表/表格数据行的重复。一个 500 行的表格，每行结构几乎相同（只是数据不同），清理属性后仍有 150K+ 字符，超过 `SNAPSHOT_SUMMARY_THRESHOLD = 20000` 后触发摘要退化，丢失所有元素的 ref 信息，导致后续选择器生成完全失效。

## 原来实现逻辑

`clean_playwright_snapshot()` 的处理流程：

1. 移除代码块（`### Ran Playwright code`）
2. 移除事件日志（`### Events`）
3. 移除无用属性（`[orientation]`、`[implicit]` 等）
4. 筛选非交互元素
5. 移除空 generic 容器
6. 压缩空行

**没有任何重复行检测和截断逻辑。**

当清理后仍超过 20K 字符时，`DOMCleanerMiddleware._generate_snapshot_summary()` 生成摘要，只保留每种交互元素类型的前 3 个详细信息，其余全部丢失。

## 当前实现逻辑

在步骤 5（属性清理）之前新增步骤 5a——重复行截断：

```
1. 移除代码块
2. 移除事件日志
3. 移除激活状态、URL 信息
4. 移除无用属性前的预处理
5a. 🔥 重复行截断（新增，在属性清理之前，因为需要原始缩进信息）
5b. 逐行清理属性 + 筛选非交互元素
6. 移除空 generic 容器
7. 压缩空行
```

### 新增函数

#### `_get_structure_signature(line: str) -> str`

提取行的"结构签名"：缩进级别 + 元素类型，忽略文本内容和 ref 值。

```python
'    - row [ref=e45]:'  → '4:row'
'    - row [ref=e99]:'  → '4:row'   # 相同签名
'      - cell [ref=e46]: "Apple"'  → '6:cell'
```

#### `_detect_and_truncate_repeated_rows(lines, max_keep=5, min_repeat=8)`

检测连续重复的表格行/列表项并截断：

1. 扫描所有行，识别可重复类型（`row`、`listitem`、`option`、`treeitem`、`gridcell`）的"组"（父行 + 子行）
2. 找到连续 ≥ 8 组相同签名的区间
3. 只保留前 5 组 + 最后 1 组 + 摘要注释
4. 摘要格式：`# ... 省略 N 个相同结构的 row （共 M 个，已保留前 5 个和最后 1 个）`

关键设计点：
- 通过缩进判断父子关系，一个"组"包含父行及所有更深缩进的子行
- 相邻性检查：两个组之间如果有其他内容行（如按钮），不算连续序列，分别处理
- 在属性清理之前执行，因为 `_remove_useless_attributes` 会 `.strip()` 掉缩进

### 配置常量

```python
REPEATED_ROW_MAX_KEEP = 5       # 保留前 N 组
REPEATED_ROW_MIN_REPEAT = 8     # 至少连续 N 组才触发
REPEATED_ROW_TYPES = {'row', 'listitem', 'option', 'treeitem', 'gridcell'}
```

## 主要修复点

1. `tools/utils/dom_utils.py`：新增 `_get_structure_signature`、`_detect_and_truncate_repeated_rows` 两个函数，新增 3 个配置常量
2. `tools/utils/dom_utils.py`：`clean_playwright_snapshot` 中在属性清理之前插入截断步骤（5a），属性清理步骤中增加对摘要注释行（`#` 开头）的跳过处理

## 测试验证

| 测试场景 | 输入 | 结果 |
|----------|------|------|
| 少于阈值（5 行） | 5 个 row | 不截断，原样返回 |
| 超过阈值（50 行） | 50 个 row | 保留 6 组 + 摘要，省略 44 组 |
| listitem 类型 | 20 个 listitem | 保留 6 组 + 摘要，省略 14 组 |
| 混合内容 | 不同类型元素 | 不截断 |
| 多个独立表格 | 2 个 15 行表格，中间有按钮 | 分别截断，按钮保留 |
| 真实快照模拟（500 行） | 500 个 row + 表头 + 分页 | 64250 → 1131 chars（98.2% reduction） |
| 完整管线集成 | 200 行 + 代码块 + 事件 | 33076 → 1113 chars（96.6% reduction） |

## 预期效果

- 500 行表格快照：150K → ~3K 字符
- 不再触发 20K 摘要阈值，元素 ref 信息完整保留
- 后续选择器生成有足够上下文，质量提升
- 预计脚本通过率提升 ~8%（从 40% → 48%）
