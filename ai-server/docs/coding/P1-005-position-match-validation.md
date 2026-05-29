# P1-005: 位置匹配增加文本交叉验证

## 概述

在 ref → HTML 属性映射的位置匹配兜底策略中，增加文本交叉验证，防止因 accessibility tree 与 DOM 顺序不一致导致的错误映射。

## 修改文件

- `tools/middleware/semantic_selector.py` — `_build_ref_to_html_mapping` 方法

## 原来实现逻辑

当精确匹配（id、name、data-testid）都失败时，直接按索引位置匹配：

```python
if i < len(html_elems):
    html_elem = html_elems[i]
    self._ref_to_html_attrs[ref] = html_elem  # 无验证，直接映射
```

问题：accessibility tree 的遍历顺序和 DOM 顺序不一定相同（tabindex、aria-owns、Shadow DOM 等场景），可能把"用户名"输入框的 HTML 属性映射到"密码"输入框的 ref 上。

## 当前实现逻辑

位置匹配后增加文本交叉验证：

```python
if i < len(html_elems):
    html_elem = html_elems[i]
    snapshot_text = (snapshot_elem.get('name') or snapshot_elem.get('text') or '').lower().strip()
    html_text = (html_elem.get('placeholder') or html_elem.get('_text') or '').lower().strip()
    
    # 两者都为空（纯结构匹配）或文本包含关系
    if (not snapshot_text and not html_text) or \
       (snapshot_text and html_text and (
           snapshot_text in html_text or html_text in snapshot_text)):
        self._ref_to_html_attrs[ref] = html_elem  # 验证通过
    else:
        pass  # 验证失败，跳过此映射
```

## 主要修复点

1. `_build_ref_to_html_mapping` 中第 4 步位置匹配：增加快照文本 vs HTML 文本的交叉验证
2. 验证通过条件：两者都为空（纯结构匹配），或文本存在包含关系

## 预期效果

- 减少因错误映射导致的选择器指向错误元素
- 对表单页面（多个输入框）效果最明显
