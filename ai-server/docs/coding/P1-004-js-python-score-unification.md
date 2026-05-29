# P1-004: JS/Python 评分常量统一

> 完成日期：2026-03-24

## 原来实现逻辑

JS 端和 Python 端各自独立定义评分常量，存在以下问题：

1. **Python 端**：在 `semantic_selector.py` 顶部定义 `K_*` 常量（约 30 个），如 `K_TEST_ID_SCORE = 1`、`K_ROLE_WITH_NAME_SCORE = 100` 等
2. **JS 端**：在 `JS_INTERACTIVE_DETECTOR` 脚本内硬编码 `SCORE` 对象，如 `TEST_ID: 1`、`ROLE_WITH_NAME: 100` 等
3. **不一致**：JS 端有 `ARIA_LABEL: 110` 但 Python 端缺少对应常量；JS 端用 `FALLBACK` 而 Python 端用 `CSS_FALLBACK`；JS 端缺少 `CSS_INPUT_TYPE`、`CSS_TAG_NAME` 等常量

修改任一端的常量值时，另一端不会自动同步，导致同一元素在 JS 端和 Python 端可能得到不同的最佳选择器推荐。

## 当前实现逻辑

1. **共享常量文件** `tools/middleware/selector_scores.py`：
   - 定义所有评分常量（Python 变量 + `SELECTOR_SCORES` dict）
   - 包含 `ARIA_LABEL = 110`、`CSS_NAME = 515` 等之前缺失的常量
   - `SELECTOR_SCORES` dict 用于 JS 端注入

2. **Python 端**：从 `selector_scores.py` 导入所有常量，通过 `K_*` 别名保持向后兼容
   ```python
   from tools.middleware.selector_scores import (
       TEST_ID, ROLE_WITH_NAME, ARIA_LABEL, CSS_NAME, ...
       SELECTOR_SCORES,
   )
   K_TEST_ID_SCORE = TEST_ID
   K_ROLE_WITH_NAME_SCORE = ROLE_WITH_NAME
   K_ARIA_LABEL_SCORE = ARIA_LABEL  # 新增
   K_CSS_NAME_SCORE = CSS_NAME      # 新增
   ```

3. **JS 端**：`get_js_detection_script()` 动态注入评分常量
   ```python
   def get_js_detection_script(self) -> str:
       scores_js = "const SCORE = " + json.dumps(SELECTOR_SCORES) + ";"
       script = self.JS_INTERACTIVE_DETECTOR.replace(
           '// __SCORES_INJECTED_FROM_PYTHON__', scores_js
       )
       return script
   ```
   JS 脚本中的硬编码 `SCORE` 对象替换为占位符 `// __SCORES_INJECTED_FROM_PYTHON__`

4. **自动注入**：`_auto_inject_js_detection()` 改为调用 `get_js_detection_script()` 而非直接使用 `self.JS_INTERACTIVE_DETECTOR`

## 主要修复点

| 修复项 | 说明 |
|--------|------|
| 创建 `selector_scores.py` | 统一的评分常量定义文件 |
| Python 端改为导入 | 从 `selector_scores.py` 导入，K_* 别名保持兼容 |
| JS 端动态注入 | `get_js_detection_script()` 用 `json.dumps(SELECTOR_SCORES)` 替换占位符 |
| 修复 `SCORE.FALLBACK` → `SCORE.CSS_FALLBACK` | JS 端引用名与 SELECTOR_SCORES key 对齐 |
| 新增 `K_ARIA_LABEL_SCORE`、`K_CSS_NAME_SCORE` | Python 端补齐之前缺失的常量 |
| `_auto_inject_js_detection` 使用 `get_js_detection_script()` | 确保自动注入也使用动态常量 |
