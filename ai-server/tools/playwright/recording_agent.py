"""
统一智能体 - 整合所有能力

特点：
1. 脚本录制：CodeCollectorMiddleware 从工具调用参数生成 TypeScript 代码
2. DOM清理：DOMCleanerMiddleware 清除多余元素，减少 token 消耗
3. Token控制：TokenControlMiddleware 对话历史控制（替代 SummarizationMiddleware）
4. Base64过滤：将截图保存到本地，替换为文件路径
5. 脚本保存/执行：save_playwright_script, run_playwright_script
6. 结果解析：parse_test_results 解析测试结果

使用官方 @playwright/mcp + Chart MCP。
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import anyio

from langchain.agents import AgentState
from tools.middleware.token_control import TokenControlMiddleware
from llms import get_model
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.pregel import Pregel

from deepagents import create_deep_agent

from tools.debug.readlog import logs
from tools.middleware.code_collector import CodeCollectorMiddleware, get_collector, reset_collector
from tools.middleware.dom_cleaner import DOMCleanerMiddleware
from tools.middleware.logging import BeforeAgentMiddleware
from tools.middleware.thread_context import ThreadContextMiddleware
from tools.middleware.base64_filter import Base64FilterMiddleware
from tools.middleware.semantic_selector import SemanticSelectorMiddleware, get_semantic_selector, reset_semantic_selector
from tools.playwright.script_manager import ScriptManager, get_manager
from tools.playwright.script_generator import create_script_save_tool
from tools.playwright.executor import create_playwright_executor_tool
from tools.playwright.report import create_result_parser_tool
from tools.playwright.bnp_auth_tool import create_bnp_login_tool, create_bnp_list_auth_states_tool
from tools.playwright.config import DEFAULT_CONFIG, UIAutomationConfig
from tools.playwright.script_index import ScriptIndexManager, get_index_manager


# ============================================================================
# 系统提示词
# ============================================================================

SYSTEM_PROMPT = """你是一个专业的 Web 自动化测试助手，支持浏览器操作和脚本录制。

## ⚠️ 重要：正确的脚本生成流程

**必须按以下流程操作，否则生成的脚本将无法使用：**

### ✅ 正确流程（操作录制）
1. **检查登录态**：`bnp_check_auth`（如无效则 `bnp_login`）
2. **获取快照**：`browser_snapshot` → 获取元素语义信息（role, name, text）
3. **执行操作**：`browser_click`, `browser_type` 等工具操作页面
4. **保存脚本**：`save_current_recording` → 保存实际的可执行代码

### ❌ 错误做法
- 使用 `create_script_with_auth` → 只生成占位代码，不可执行！
- 不获取快照就操作 → 无法生成语义化选择器！
- 使用 `ref=e157` 这样的选择器 → 每次刷新都会变，完全不可靠！

---

## 🎯 工作模式

### 模式一：操作录制（复杂任务推荐）
实际操作页面，自动录制生成脚本。
```
用户任务 → browser_snapshot → 操作页面 → 完成任务 → save_current_recording 保存
```
⚠️ **关键：操作前必须先调用 browser_snapshot 获取快照！**
- 快照包含元素的语义信息（role, name, text 等）
- 有了快照才能生成正确的语义化选择器（getByRole, getByText 等）
- 没有快照时只能生成不稳定的 ref 选择器

**适用：** 复杂流程、需要验证操作、精确控制

### 模式二：快速生成（简单任务推荐）
根据页面快照直接生成脚本，无需实际操作。
```
browser_snapshot → 根据快照生成脚本 → save_current_recording
```
**适用：** 简单操作、快速创建模板、节省 token

---

## ⚠️ 元素定位优先级（Codegen 分数体系：分数越低越好）

| 优先级 | 方式 | 分数 | 示例 |
|--------|------|------|------|
| 1️⃣ | `getByTestId()` | 1-2 | `getByTestId('submit-btn')` - 测试专用属性（最稳定） |
| 2️⃣ | `getByRole()` | 100 | `getByRole('button', {name: '提交'})` - 语义化选择器 |
| 3️⃣ | `getByPlaceholder()` | 120 | `getByPlaceholder('请输入')` |
| 4️⃣ | `getByLabel()` | 140 | `getByLabel('用户名')` |
| 5️⃣ | `getByText()` | 180 | `getByText('登录')` - ⚠️ 需限定范围 |
| 6️⃣ | CSS 属性选择器 | 500+ | `[name="xxx"]`, `#id`（需判断是否动态） |
| 7️⃣ | `page.evaluate()` | - | JavaScript 执行（终极备用） |
| ❌ | 位置选择器 | 10000+ | `.nth()`, `.first()` - 不稳定，应避免 |

**🚨 绝对禁止使用 `ref=e123` 临时引用选择器！**

`ref` 是 Playwright MCP 快照中的临时引用，每次页面刷新都会变化，**绝对不能用于代码生成**。

```typescript
// 🚨 绝对禁止！每次页面刷新 ref 都会变
await page.locator('[ref=e157]').click();
await page.click('[ref=e101]');

// ✅ 必须转换为语义化选择器
await page.getByRole('button', {name: 'Submit'}).click();
await page.getByText('Box').first().click();
await page.locator('form').getByText('UOM').click();
```

**当快照显示 `[ref=e157]` 时，必须：**
1. 查看该元素的 `role`、`name`、`text` 属性
2. 转换为 `getByRole('xxx', {name: '...'})` 或 `getByText('...')`
3. 如果文本可能重复，使用 `.first()` 或限定范围

**❌ 其他禁止：** `:nth-child()`、动态ID（如 `:r1:`）

### 🎯 选择器限定范围规则（避免 strict mode 违规）

当 `getByText()` 可能匹配多个元素时，必须限定范围：

```typescript
// ❌ 错误：getByText('UOM') 匹配了表单标签 + 表格列头，导致 strict mode violation
await page.getByText('UOM').click();

// ✅ 正确：限定在表单范围内
await page.locator('form').getByText('UOM').click();

// ✅ 正确：限定在 .el-form-item 范围内
await page.locator('.el-form-item').filter({ hasText: 'UOM' }).locator('[role="combobox"]').click();

// ✅ 正确：使用 .first() 避免 strict mode
await page.getByText('UOM').first().click();
```

**何时需要限定范围：**
- 文本可能在页面多处出现（如表头、表单标签）
- 通用文本如 "Search"、"Submit"、"Add"
- 表格列名与筛选器同名

**最佳实践：**
1. 优先使用 `getByRole('xxx', {name: '...'})` 而非 `getByText()`
2. 使用 `page.locator('form')` 或 `.el-form-item` 限定表单范围
3. 快照中查看元素的父级结构，选择合适的限定容器

**⚠️ 不推荐 jQuery 语法：** `:contains("text")` - 系统会自动转换为标准 JavaScript，但建议直接使用标准写法

---

## 🔢 数字/页码精确匹配规则（重要！）

**问题**：`getByText('2')` 是模糊匹配，会匹配到：
- `<li>2</li>` ✅ 页码 2
- `<li>22</li>` ❌ 页码 22（包含 "2"）
- `<span>20/page</span>` ❌ 包含 "2"

**解决方案**：对数字、短文本、分页场景使用正则精确匹配：

```typescript
// ❌ 错误：模糊匹配
await page.locator('.el-pagination').getByText('2').click();  // 匹配 3 个元素！

// ✅ 正确：精确匹配
await page.locator('.el-pagination').getByText(/^2$/).click();  // 只匹配 "2"

// ✅ 正确：使用 role 定位页码
await page.getByRole('listitem', { name: 'page 2' }).click();

// ✅ 正确：使用 aria-label
await page.locator('[aria-label="page 2"]').click();
```

**判断条件**：
- 纯数字（如 "2", "10"）→ 必须精确匹配
- 短文本（< 3字符）→ 建议精确匹配
- 分页场景 → 精确匹配页码

---

## 🔧 JavaScript 执行备用方案

当选择器失效时使用：
```typescript
// 点击被遮挡元素
await page.evaluate(() => {
  document.querySelector('button[type="submit"]').click();
});

// 修改输入框（绕过双向绑定）
await page.evaluate(() => {
  const input = document.querySelector('input[name="email"]');
  input.value = 'test@example.com';
  input.dispatchEvent(new Event('input', { bubbles: true }));
});
```

⚠️ **JavaScript 选择器陷阱（重要！）**：

**querySelector 不支持 jQuery 语法！**（系统会自动转换，但建议直接使用标准写法）
```javascript
// ⚠️ jQuery 语法（系统会自动转换，但不推荐）
document.querySelector('li.item:has(span:contains("Box"))')
// 系统自动转换为：
// [...document.querySelectorAll('li.item')].find(el => el.querySelector('span') && el.textContent.includes('Box'))

// ✅ 推荐直接使用标准写法（转换后效果相同）
const items = [...document.querySelectorAll('li.el-select-dropdown__item')];
const target = items.find(li => li.textContent.includes('Box'));
if (target) target.click();

// ✅ 正确方式 2：使用 :has()（现代浏览器支持）+ 遍历检查文本
document.querySelectorAll('li.el-select-dropdown__item:has(span)').forEach(li => {
  if (li.textContent.includes('Box')) li.click();
});

// ✅ 正确方式 3：直接用 XPath（支持文本匹配）
document.evaluate(
  "//li[contains(@class, 'el-select-dropdown__item')]//span[contains(text(), 'Box')]",
  document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
).singleNodeValue?.click();
```

**其他常见陷阱**：
```javascript
// ❌ 错误：SVG 元素的 className 是 SVGAnimatedString 对象，不是字符串
el.className?.toLowerCase()  // TypeError: toLowerCase is not a function

// ✅ 正确：使用 getAttribute 获取 class 属性
el.getAttribute('class')?.toLowerCase()

// ✅ 正确：或使用 classList
el.classList.contains('some-class')

// ❌ 错误：直接访问可能不存在的属性
el.style?.toLowerCase()  // style 是对象，不是字符串

// ✅ 正确：获取 style 属性字符串
el.getAttribute('style')?.toLowerCase()
```

---

## 📦 工具使用

### 页面操作（优先使用）

⚠️ **快照优先原则**：
1. 导航后立即调用 `browser_snapshot` 获取快照
2. 操作前确认快照是最新的（页面变化后需重新获取）
3. 快照是生成语义化选择器的前提

| 工具 | 用途 |
|------|------|
| `browser_navigate` | 导航到页面 → 然后必须调用 browser_snapshot |
| `browser_snapshot` | 获取页面快照 → **操作前必须先调用！** |
| `browser_click` | 点击元素 |
| `browser_type` | 输入文本 |
| `browser_scroll` | 滚动页面 |

### 脚本管理（用户要求时使用）
| 工具 | 用途 |
|------|------|
| `save_current_recording` | 保存录制脚本 |
| `get_current_code` | 查看当前代码 |
| `reset_recording` | 重置录制 |
| `list_scripts` | 列出脚本 |
| `rebuild_index` | 重建索引 |

### 登录态管理
| 工具 | 用途 |
|------|------|
| `bnp_check_auth` | 检查登录态 |
| `bnp_login` | 执行登录 |

**登录态路径：** `playwright_scripts/auth_state/bnp_auth.json`

⚠️ **何时不应使用登录态：**
- 用户正在登录或测试登录流程
- 操作登录页面（填写用户名密码、点击登录按钮）
- 修改密码、找回密码等认证相关操作
- 录制登录脚本时

✅ **何时应使用登录态：**
- 执行需要前置登录的业务操作
- 访问已登录后才能看到的页面
- 填写表单、提交数据等业务流程

---

## 🔐 两种浏览器模式

| 模式 | 工具 | 登录态 |
|------|------|--------|
| 实时浏览器 | `browser_xxx` | ❌ 不支持 |
| 脚本执行 | `run_playwright_script` | ✅ 支持 |

**关键：** 需要登录态时必须用 `run_playwright_script` + `auth_state` 参数

---

## 🎨 Vue 组件库特殊处理

### Element-UI / Ant-Design 下拉框

这些组件库使用 `div` 模拟下拉框，**不是原生 `<select>` 元素**，快照可能无法识别。

**操作步骤（必须按顺序）：**

1️⃣ **找到触发器**：下拉框的触发器通常是 `combobox` 或 `textbox` 角色
```yaml
# 快照中可能显示为：
- combobox "UOM": [ref=e89]  # 这就是下拉框触发器
- textbox "请选择": [ref=e90]
```

2️⃣ **点击触发器**：使用 `browser_click` 点击
```
browser_click(element="UOM下拉框", ref="e89")
```

3️⃣ **等待展开**：下拉选项会动态加载，调用 `browser_snapshot` 查看选项
```
browser_snapshot  # 获取新快照，查看展开的选项
```

4️⃣ **选择选项**：使用 `browser_click` 点击目标选项
```yaml
# 展开后快照显示：
- option "Box": [ref=e101]
- option "Pallet": [ref=e102]
```
```
browser_click(element="Box选项", ref="e101")
```

**⚠️ 禁止直接使用 browser_evaluate！**
- `browser_evaluate` 执行的 JavaScript **无法被录制**
- 应该使用 `browser_click` + `browser_snapshot` 组合

**如果快照中找不到下拉框：**
1. 尝试搜索 `combobox`、`listbox`、`haspopup` 角色
2. 查找带有 `aria-haspopup="listbox"` 的元素
3. 使用 `page.getByRole('combobox')` 定位

### 常见 Vue 组件角色映射

| 组件 | 快照中的角色 | 操作方式 |
|------|-------------|----------|
| el-select | `combobox` | 点击触发器 → 点击选项 |
| el-cascader | `combobox` | 点击触发器 → 逐级选择 |
| el-date-picker | `textbox` | 点击 → 选择日期 |
| a-select | `combobox` | 同 el-select |
| a-tree-select | `combobox` | 点击 → 展开树 → 选择节点 |

---

## ⚠️ 错误恢复

**Ref 失效时：**
1. 调用 `browser_snapshot` 获取新快照
2. 从新快照找到元素
3. 使用新 ref 重试

**禁止重试失效的 ref！**

---

## 🌐 网络环境提示（非常重要！）

**⚠️ 公司网络非常缓慢，页面加载平均需要 30 秒！**

这会影响你的所有操作决策：
- **不要因为超时就判定失败** - 很可能只是网络慢
- **不要因为元素没出现就报错** - 等待更长时间再判断
- **每次导航后必须等待 30 秒** - 这是公司网络的基本要求
- **如果工具返回超时错误，等待后重试** - 不要立即放弃

### 操作时的等待规则
- 页面导航后等待至少 30 秒再判断是否超时
- 不要因为页面响应慢就过早判定操作失败
- 遇到加载缓慢时，先等待再重试，而非立即放弃
- 如果浏览器工具返回超时错误，可能是网络原因，应等待后重试
- 使用 `browser_snapshot` 前确保页面已基本加载完成

### 代码生成的统一等待规则（重要！）

**生成 TypeScript 代码时，必须遵循以下等待规则：**

1. **页面导航（page.goto）后统一等待 30 秒**：
```typescript
await page.goto('url');
await page.waitForLoadState('networkidle', { timeout: 30000 });
await page.waitForTimeout(30000);  // 公司网络缓慢，页面加载需要30秒
```

2. **元素操作前等待（5-10秒）**：
```typescript
// 等待元素出现（最长 10 秒）
await page.waitForSelector('selector', { timeout: 10000 });
await expect(page.locator('selector')).toBeVisible({ timeout: 10000 });
```

3. **下拉框展开后等待（5-10秒）**：
```typescript
await page.click('combobox');
await page.waitForTimeout(5000);  // 等待下拉选项加载（本地渲染，较快）
```

4. **选择选项后等待（3-5秒）**：
```typescript
await page.click('.el-select-dropdown__item');
await page.waitForTimeout(3000);  // 等待选项被选中
```

5. **提交/搜索后等待结果（10秒）**：
```typescript
await page.click('button:has-text("Search")');
await page.waitForLoadState('networkidle', { timeout: 10000 });
await page.waitForTimeout(10000);  // 等待查询结果（API请求）
```

**⚠️ 等待时间分级总结**：
| 操作类型 | 等待时间 | 说明 |
|---------|---------|------|
| `page.goto` 导航 | 30秒 | 网络请求 + 页面渲染 |
| 下拉框展开 | 5秒 | 本地渲染 |
| 选择选项 | 3秒 | 本地交互 |
| 提交/搜索 | 10秒 | API请求 |
| 元素出现 | 10秒 | DOM更新 |

**⚠️ 禁止使用过长的等待**：非导航操作不要使用 30 秒等待，避免测试时间过长。

---

## 📝 测试数据唯一性规则

**生成测试脚本时，必须确保唯一性字段的值不重复！**

### 唯一性字段处理

| 字段类型 | 是否需要唯一 | 处理方式 |
|---------|------------|---------|
| Charge Code | ✅ 是 | `TEST-AUTO-${Date.now()}` |
| Item Name | ✅ 是 | `Test Item Auto ${Date.now()}` |
| Code / 编号 | ✅ 是 | 时间戳或随机数 |
| Status | ❌ 否 | 固定值 "Active" |
| Billing Category | ❌ 否 | 固定选项 |
| UOM | ❌ 否 | 固定选项 |

### 正确示例

```typescript
test('add_billing_item', async ({ page }) => {
  // ✅ 脚本开头定义时间戳变量
  const timestamp = Date.now();
  const chargeCode = `TEST-AUTO-${timestamp}`;
  const itemName = `Test Billing Item Auto ${timestamp}`;
  
  // ✅ 填写唯一字段
  await page.getByLabel('Charge Code').fill(chargeCode);
  await page.getByLabel('Item Name').fill(itemName);
  
  // ✅ 选择固定选项（不需要唯一）
  await page.getByText('Active').click();
});
```

### 错误示例

```typescript
// ❌ 硬编码值，重复运行会失败
await page.getByLabel('Charge Code').fill('TEST-AUTO-123');
```
"""


# ============================================================================
# 录制回放工具
# ============================================================================

@tool
def check_script(url: str, task_description: str) -> str:
    """
    检查是否有匹配的录制脚本。
    
    在执行新任务前，先检查脚本库中是否有可复用的脚本。
    
    Args:
        url: 目标 URL
        task_description: 任务描述（如：登录、搜索、填写表单）
    
    Returns:
        匹配结果，包括脚本名称和描述
    """
    manager = get_manager()
    
    best_match = manager.find_best_match(url, task_description)
    
    if best_match:
        metadata = manager.load_metadata(best_match)
        if metadata:
            return f"""找到匹配脚本：
- 名称: {best_match}
- 描述: {metadata.description}
- 变量: {', '.join(metadata.variables) if metadata.variables else '无'}
- 使用次数: {metadata.usage_count}
- 成功率: {metadata.success_rate * 100:.1f}%

使用 run_playwright_script 工具执行此脚本，路径为: {metadata.description}.spec.ts"""
    else:
        all_scripts = manager.list_scripts()
        if all_scripts:
            return f"未找到完全匹配的脚本。\n可用脚本: {', '.join(all_scripts)}\n\n可以使用 Playwright 工具手动操作，完成后用 save_current_recording 保存。"
        else:
            return "脚本库为空。可以使用 Playwright 工具手动操作，完成后用 save_current_recording 保存。"


@tool
def save_current_recording(name: str, description: str = "", keywords: str = "") -> str:
    """
    保存当前录制的脚本。
    
    将当前会话中收集的 Playwright 操作保存为可复用的脚本。
    自动更新索引并评估脚本质量。
    
    Args:
        name: 脚本名称（如：login_github, search_google）
        description: 脚本描述
        keywords: 关键词，多个用逗号分隔（如：登录,login,github）
    
    Returns:
        保存结果（包含质量评估）
    """
    # 确保 semantic_selector 已关联
    collector = get_collector(get_semantic_selector())
    manager = get_manager()
    index_manager = get_index_manager()
    
    code = collector.get_collected_code()
    
    if not code.strip():
        return "错误：没有收集到任何代码。请先执行一些 Playwright 操作。"
    
    # 获取选择器统计信息（已在操作时实时生成）
    ref_count, semantic_count = collector.get_selector_stats()
    total_selectors = ref_count + semantic_count
    
    # 生成完整脚本
    full_script = collector.generate_script(
        name=name,
        description=description,
    )
    
    keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
    
    success = manager.save_script(
        name=name,
        code=full_script,
        description=description,
        url_patterns=[],
        keywords=keyword_list,
        variables=[]
    )
    
    if success:
        script_save_tool = create_script_save_tool(DEFAULT_CONFIG)
        file_result = script_save_tool.invoke({
            "script_content": full_script,
            "script_name": name,
            "language": "typescript"
        })
        
        # 更新索引
        metadata = {
            "description": description,
            "keywords": keyword_list,
            "url_patterns": [],
        }
        index_manager.update_entry(name, metadata=metadata, code=full_script)
        
        # 获取质量评估
        entries = index_manager.find_scripts(query=name)
        quality_score = 0
        for entry in entries:
            if entry.name == name:
                quality_score = entry.quality_score
                break
        
        # 生成质量报告
        quality_report = ""
        if total_selectors > 0:
            semantic_ratio = semantic_count / total_selectors
            if semantic_ratio >= 0.8:
                quality_report = f"✅ 高质量脚本：{semantic_count}/{total_selectors} 使用语义化选择器 ({semantic_ratio:.0%})"
            elif semantic_ratio >= 0.5:
                quality_report = f"⚠️ 中等质量：{semantic_count}/{total_selectors} 使用语义化选择器 ({semantic_ratio:.0%})"
            else:
                quality_report = f"❌ 低质量：仅 {semantic_count}/{total_selectors} 使用语义化选择器 ({semantic_ratio:.0%})，建议优化"
        else:
            quality_report = "ℹ️ 无选择器统计信息"
        
        # 检测相似脚本
        similar_scripts = index_manager.find_similar_scripts(name, keywords=keyword_list)
        similar_report = ""
        if similar_scripts:
            similar_report = f"\n\n⚠️ 发现 {len(similar_scripts)} 个相似脚本：\n"
            for sim in similar_scripts[:3]:  # 最多显示3个
                quality_diff = quality_score - sim.quality_score
                if quality_diff > 0.1:
                    status = "✅ 当前脚本更优"
                elif quality_diff < -0.1:
                    status = f"❌ 建议保留 {sim.name}"
                else:
                    status = "⚖️ 质量相近"
                similar_report += f"- {sim.name} (质量: {sim.quality_score:.2f}) {status}\n"
            similar_report += "\n使用 cleanup_scripts(action='auto') 自动清理重复脚本。"
        
        # 构建脚本路径（供 run_playwright_script 使用）
        script_virtual_path = f"/playwright_scripts/tests/{name}.spec.ts"
        
        collector.reset()
        
        return f"""脚本保存成功！
- 名称: {name}
- 代码行数: {len(code.split(chr(10)))}
- 质量分数: {quality_score:.2f}
- 选择器统计: {quality_report}

{file_result}{similar_report}

## 📋 运行此脚本

使用以下路径运行脚本：
```
script_path: "{script_virtual_path}"
```

示例调用：
```python
run_playwright_script(script_path="{script_virtual_path}", headless=False)
```"""
    else:
        return "错误：脚本保存失败。"


@tool
def list_scripts() -> str:
    """
    列出所有已保存的脚本。
    
    Returns:
        脚本列表，包含名称、描述、质量分数和使用统计
    """
    index_manager = get_index_manager()
    entries = index_manager.index.scripts
    
    if not entries:
        return "脚本库为空。执行一些操作后使用 save_current_recording 保存。"
    
    result = "已保存的脚本：\n\n"
    for entry in entries:
        # 质量指示器
        if entry.quality_score >= 0.7:
            quality_indicator = "✅"
        elif entry.quality_score >= 0.4:
            quality_indicator = "⚠️"
        else:
            quality_indicator = "❌"
        
        result += f"{quality_indicator} {entry.name}\n"
        result += f"   描述: {entry.description}\n"
        result += f"   质量: {entry.quality_score:.2f} | 使用次数: {entry.usage_count}\n"
        if entry.ref_count > 0 or entry.semantic_count > 0:
            result += f"   选择器: {entry.semantic_count} 语义化 / {entry.ref_count} ref\n"
        if not entry.has_code:
            result += f"   ⚠️ 无代码文件\n"
        result += "\n"
    
    return result


@tool
def rebuild_index() -> str:
    """
    重建脚本索引。
    
    扫描所有脚本文件，重建全局索引。用于修复索引损坏或手动添加脚本后的同步。
    
    Returns:
        重建结果
    """
    index_manager = get_index_manager()
    count = index_manager.rebuild_index()
    
    # 获取统计信息
    entries = index_manager.index.scripts
    high_quality = len([e for e in entries if e.quality_score >= 0.7])
    low_quality = len([e for e in entries if e.quality_score < 0.3])
    incomplete = len([e for e in entries if not e.has_code])
    
    return f"""索引重建完成！

- 总脚本数: {count}
- 高质量脚本: {high_quality}
- 低质量脚本: {low_quality}
- 不完整脚本: {incomplete}

使用 list_scripts 查看详细列表。
使用 list_low_quality_scripts 查看需要优化的脚本。"""


@tool
def init_script_library(auto_cleanup: bool = True) -> str:
    """
    初始化脚本库。
    
    一键完成：重建索引 + 清理过期回收站 + 自动清理低质量脚本。
    建议在服务器启动后或大量脚本变更后执行一次。
    
    Args:
        auto_cleanup: 是否自动清理低质量和重复脚本（默认 True）
    
    Returns:
        初始化结果报告
    """
    from tools.debug.readlog import logs
    
    index_manager = get_index_manager()
    
    logs.info("[init_script_library] 开始初始化脚本库...")
    
    # 1. 重建索引
    logs.info("[init_script_library] 步骤1: 重建索引...")
    script_count = index_manager.rebuild_index()
    
    # 2. 清理过期回收站
    logs.info("[init_script_library] 步骤2: 清理过期回收站...")
    expired_count = index_manager.cleanup_expired_trash()
    
    # 3. 自动清理低质量和重复脚本
    cleanup_result = {"total_removed": 0, "details": []}
    if auto_cleanup:
        logs.info("[init_script_library] 步骤3: 自动清理低质量脚本...")
        cleanup_result = index_manager.auto_cleanup(keep_best=True, quality_threshold=0.4)
    
    # 获取最终统计
    entries = index_manager.index.scripts
    high_quality = len([e for e in entries if e.quality_score >= 0.7])
    medium_quality = len([e for e in entries if 0.4 <= e.quality_score < 0.7])
    low_quality = len([e for e in entries if e.quality_score < 0.4])
    
    # 生成报告
    report = f"""# 脚本库初始化完成

## 执行结果

| 步骤 | 结果 |
|------|------|
| 重建索引 | {script_count} 个脚本 |
| 清理过期回收站 | {expired_count} 个文件 |
| 自动清理 | {cleanup_result['total_removed']} 个脚本 |

## 当前状态

| 质量等级 | 数量 |
|----------|------|
| ✅ 高质量 (≥0.7) | {high_quality} |
| ⚠️ 中等质量 (0.4-0.7) | {medium_quality} |
| ❌ 低质量 (<0.4) | {low_quality} |
| **总计** | {len(entries)} |
"""
    
    if cleanup_result['details']:
        report += "\n## 清理详情\n"
        for detail in cleanup_result['details'][:5]:
            report += f"- {detail['name']}: {detail['reason']}\n"
        if len(cleanup_result['details']) > 5:
            report += f"- ... 还有 {len(cleanup_result['details']) - 5} 个\n"
    
    # 获取定期清理配置（后台异步执行）
    cleanup_status = index_manager.get_cleanup_status()
    report += f"""
## 定期清理配置

- 清理间隔: 每 {cleanup_status['cleanup_interval']} 次操作（后台异步）
- 质量阈值: {cleanup_status['quality_threshold']}
- 上次清理: {cleanup_status['last_cleanup_time'] or '未执行'}

使用 `cleanup_scripts(action='auto')` 手动触发清理。
使用 `list_scripts` 查看详细列表。"""
    
    logs.info(f"[init_script_library] 初始化完成: {len(entries)} 个脚本")
    
    return report


@tool
def list_low_quality_scripts(threshold: float = 0.3) -> str:
    """
    列出低质量脚本。
    
    质量分数低于阈值的脚本，建议优化或删除。
    
    Args:
        threshold: 质量分数阈值（默认 0.3，范围 0-1）
    
    Returns:
        低质量脚本列表
    """
    index_manager = get_index_manager()
    low_quality = index_manager.get_low_quality_scripts(threshold)
    incomplete = index_manager.get_incomplete_scripts()
    
    if not low_quality and not incomplete:
        return "没有发现低质量或不完整的脚本。"
    
    result = "需要关注的脚本：\n\n"
    
    if low_quality:
        result += "### 低质量脚本\n"
        for entry in low_quality:
            result += f"- {entry.name} (质量: {entry.quality_score:.2f})\n"
            result += f"  描述: {entry.description}\n"
            if entry.ref_count > 0:
                result += f"  问题: {entry.ref_count} 个不稳定 ref 选择器\n"
            if entry.success_rate < 0.5:
                result += f"  成功率: {entry.success_rate:.0%}\n"
            result += "\n"
    
    if incomplete:
        result += "### 不完整脚本（无代码文件）\n"
        for entry in incomplete:
            result += f"- {entry.name}\n"
            result += f"  描述: {entry.description}\n\n"
    
    result += "建议：\n"
    result += "- 低质量脚本：使用 cleanup_scripts 移入回收站\n"
    result += "- 不完整脚本：检查是否有对应的 .ts 文件，或删除\n"
    
    return result


@tool
def cleanup_scripts(action: str = "list", script_name: str = "") -> str:
    """
    清理脚本（移入回收站）。
    
    Args:
        action: 操作类型
            - "list": 列出回收站内容
            - "trash": 移入回收站（需提供 script_name）
            - "restore": 从回收站恢复（需提供 script_name）
            - "empty": 清空回收站
            - "auto": 自动清理低质量和重复脚本
        script_name: 脚本名称（trash/restore 操作时必需）
    
    Returns:
        操作结果
    """
    index_manager = get_index_manager()
    
    if action == "list":
        trash_items = index_manager.list_trash()
        if not trash_items:
            return "回收站为空。"
        
        result = "回收站内容：\n\n"
        for item in trash_items:
            expired = " [已过期]" if item["is_expired"] else ""
            result += f"- {item['original_name']}{expired}\n"
            result += f"  删除时间: {item['deleted_at']}\n\n"
        
        result += "使用 cleanup_scripts(action='restore', script_name='...') 恢复脚本。"
        return result
    
    elif action == "trash":
        if not script_name:
            return "错误：请提供 script_name 参数。"
        
        if index_manager.move_to_trash(script_name):
            return f"脚本 '{script_name}' 已移入回收站。\n使用 cleanup_scripts(action='restore', script_name='{script_name}') 可恢复。"
        else:
            return f"脚本 '{script_name}' 不存在或移入失败。"
    
    elif action == "restore":
        if not script_name:
            return "错误：请提供 script_name 参数。"
        
        if index_manager.restore_from_trash(script_name):
            return f"脚本 '{script_name}' 已从回收站恢复。"
        else:
            return f"回收站中未找到脚本 '{script_name}'。"
    
    elif action == "empty":
        cleaned = index_manager.cleanup_expired_trash()
        return f"已清理 {cleaned} 个过期文件。"
    
    elif action == "auto":
        # 自动清理低质量和重复脚本
        result = index_manager.auto_cleanup(keep_best=True, quality_threshold=0.4)
        
        summary = f"""自动清理完成！

统计：
- 无代码文件: {result['removed_no_code']} 个
- 低质量脚本: {result['removed_low_quality']} 个  
- 重复脚本: {result['removed_similar']} 个
- 总计移除: {result['total_removed']} 个
"""
        
        if result['details']:
            summary += "\n详情：\n"
            for detail in result['details'][:10]:  # 最多显示10个
                summary += f"- {detail['name']}: {detail['reason']}\n"
            if len(result['details']) > 10:
                summary += f"... 还有 {len(result['details']) - 10} 个\n"
        
        summary += "\n使用 cleanup_scripts(action='list') 查看回收站内容。"
        return summary
    
    else:
        return f"未知操作: {action}。可用操作: list, trash, restore, empty, auto"


@tool
def delete_script(name: str) -> str:
    """
    删除已保存的脚本。
    
    Args:
        name: 脚本名称
    
    Returns:
        删除结果
    """
    manager = get_manager()
    
    if manager.delete_script(name):
        return f"脚本 '{name}' 已删除。"
    else:
        return f"脚本 '{name}' 不存在或删除失败。"


@tool
def reset_recording() -> str:
    """
    重置当前录制。
    
    清空当前会话收集的所有代码和缓存，开始新的录制。
    
    Returns:
        重置结果
    """
    collector = get_collector()
    collector.reset()
    reset_semantic_selector()
    return "录制已重置，可以开始新的操作录制。"


@tool
def get_current_code() -> str:
    """
    获取当前录制的代码。
    
    查看当前会话已收集的 TypeScript 代码。
    
    Returns:
        当前收集的代码
    """
    collector = get_collector()
    code = collector.get_collected_code()
    
    if not code.strip():
        return "当前没有收集到任何代码。"
    
    return f"当前收集的代码：\n```typescript\n{code}\n```"


@tool
def create_script_with_auth(
    script_name: str,
    url: str,
    operations: str,
    auth_state_path: str = "auth_state/bnp_auth.json",
) -> str:
    """
    创建带登录态的 Playwright 脚本框架。
    
    ⚠️ 此工具只生成脚本框架，不生成实际操作代码！
    
    正确使用流程：
    1. 使用 browser_navigate 访问页面
    2. 使用 browser_click, browser_type 等工具执行操作
    3. 中间件会自动收集工具调用并生成代码
    4. 使用 save_current_recording 保存完整脚本
    
    Args:
        script_name: 脚本名称（如 billing_navigation）
        url: 起始 URL（如 https://bnp-test.item.pub/Home.html）
        operations: 操作步骤描述（仅用于注释，不影响实际代码）
        auth_state_path: 登录态文件相对路径
    
    Returns:
        脚本保存结果（仅框架，需要通过录制补充实际代码）
    """
    from datetime import datetime
    
    # 解析操作步骤
    ops_list = [op.strip() for op in operations.split("\\n") if op.strip()]
    
    # 生成脚本内容（简洁版，登录态由 playwright.config.ts 的 storageState 处理）
    # ⚠️ 注意：此脚本只是框架，实际代码需要通过录制生成！
    script_content = f"""import {{ test, expect }} from '@playwright/test';

/**
 * {script_name}
 * ⚠️ 此脚本需要通过录制补充实际操作代码！
 * 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
 * 
 * 使用方式：
 * 1. 在 LangGraph 中使用 Playwright MCP 工具操作浏览器
 * 2. 中间件会自动生成代码
 * 3. 使用 save_current_recording 保存完整脚本
 * 
 * 运行方式：
 * PLAYWRIGHT_AUTH_STATE={auth_state_path} npx playwright test tests/{script_name}.spec.ts --project=chromium-auth
 */

test('{script_name}', async ({{ page }}) => {{
  // ⚠️ 公司网络缓慢，导航后必须等待 30 秒
  await page.goto('{url}');
  await page.waitForLoadState('networkidle', {{ timeout: 30000 }});
  await page.waitForTimeout(30000);  // 公司网络缓慢
  
  // ========== 以下是操作步骤（需要通过录制补充实际代码）==========
"""

    # 添加操作步骤注释
    for i, op in enumerate(ops_list, 1):
        script_content += f"""
  // TODO 步骤 {i}: {op}
  // await page.getByRole('button', {{name: 'xxx'}}).click();
  // await page.waitForTimeout(5000);
"""

    script_content += """
  // 等待最终页面加载
  await page.waitForLoadState('networkidle');
  
  console.log('测试完成！');
});
"""

    # 保存脚本（不添加 .spec 后缀，让 save_playwright_script 自动处理）
    script_save_tool = create_script_save_tool(DEFAULT_CONFIG)
    file_result = script_save_tool.invoke({
        "script_content": script_content,
        "script_name": script_name,
        "language": "typescript"
    })
    
    # 保存元数据
    manager = get_manager()
    manager.save_metadata(
        name=script_name,
        description=f"带登录态脚本: {script_name}（需要补充实际代码）",
        url_patterns=[url],
        keywords=ops_list,
        variables=["auth_state"]
    )
    
    return f"""脚本已创建！

文件: /playwright_scripts/tests/{script_name}.spec.ts

⚠️ 重要提示：
1. 脚本中的选择器是占位符，需要根据实际页面修改
2. 登录态文件: playwright_scripts/{auth_state_path}
3. 执行方式:
   - 方式一: run_playwright_script(script_path="/playwright_scripts/tests/{script_name}.spec.ts", auth_state="{auth_state_path}")
   - 方式二: PLAYWRIGHT_AUTH_STATE={auth_state_path} npx playwright test tests/{script_name}.spec.ts --project=chromium-auth

请查看生成的脚本，修改选择器后再执行。
{file_result}"""


# ============================================================================
# Agent 工厂函数
# ============================================================================

@asynccontextmanager
async def make_recording_agent() -> AsyncIterator[Pregel]:
    """
    创建统一智能体，具备所有能力：
    
    1. 脚本录制：CodeCollectorMiddleware
    2. DOM清理：DOMCleanerMiddleware
    3. Token控制：TokenControlMiddleware（替代 SummarizationMiddleware）
    4. Base64过滤：filter_base64_content
    5. 脚本保存/执行：save_playwright_script, run_playwright_script
    6. 结果解析：parse_test_results
    
    智能登录态加载：
    - 通过环境变量 PLAYWRIGHT_LOAD_AUTH_STATE 控制（默认 auto）
    - auto: 自动检测登录态有效性，无效则自动刷新
    - true: 强制加载登录态（文件必须存在）
    - false: 不加载登录态（用于录制登录流程）
    - 登录态文件路径: playwright_scripts/auth_state/bnp_auth.json
    """
    config = DEFAULT_CONFIG
    
    # 获取登录态加载配置
    load_auth_state = os.getenv("PLAYWRIGHT_LOAD_AUTH_STATE", "auto").lower()
    
    # 登录态文件路径
    # 使用绝对路径（正斜杠格式），确保 MCP 能正确找到文件
    # MCP 通过 npx 启动，工作目录可能不是项目根目录
    auth_state_abs_path = Path(__file__).parent.parent.parent / "playwright_scripts" / "auth_state" / "bnp_auth.json"
    # 转换为正斜杠格式（跨平台兼容）
    auth_state_path_str = str(auth_state_abs_path).replace("\\", "/")
    
    # 决定是否加载登录态
    should_load_auth = False
    
    if load_auth_state == "true":
        # 强制加载
        if auth_state_abs_path.exists():
            should_load_auth = True
            logs.info(f"[recording_agent] 🔐 强制加载登录态: {auth_state_path_str}")
        else:
            logs.error(f"[recording_agent] ❌ 登录态文件不存在: {auth_state_path_str}")
            logs.error(f"[recording_agent]   请先创建登录态文件，或设置 PLAYWRIGHT_LOAD_AUTH_STATE=auto/false")
    elif load_auth_state == "false":
        # 强制不加载
        logs.info(f"[recording_agent] ℹ️ 禁用登录态加载（PLAYWRIGHT_LOAD_AUTH_STATE=false）")
        logs.info(f"[recording_agent]   可用于录制登录流程")
    else:
        # auto: 自动检测并刷新
        from tools.playwright.bnp_auth_tool import (
            bnp_check_auth, 
            bnp_login_and_save,
            wait_for_login_complete,
            _is_login_in_progress,
        )
        
        # 首先检查是否有其他进程正在登录
        if _is_login_in_progress(auth_state_path_str):
            logs.info(f"[recording_agent] ⏳ 检测到其他进程正在登录，等待完成...")
            wait_result = await asyncio.to_thread(wait_for_login_complete, auth_state_path_str, timeout=90.0)
            
            if wait_result.get("success"):
                should_load_auth = True
                logs.info(f"[recording_agent] ✅ 等待登录完成，登录态有效")
            elif wait_result.get("waited"):
                logs.warning(f"[recording_agent] ⚠️ 等待登录完成但登录态无效: {wait_result.get('message')}")
            # 如果没有等待或等待失败，继续正常流程
        
        if not should_load_auth and auth_state_abs_path.exists():
            # 检查登录态有效性
            logs.info(f"[recording_agent] 🔍 检查登录态有效性: {auth_state_path_str}")
            check_result = bnp_check_auth()
            
            if check_result.get("valid") and not check_result.get("token_expired"):
                # 登录态有效
                should_load_auth = True
                time_remaining = check_result.get("time_remaining", "未知")
                logs.info(f"[recording_agent] ✅ 登录态有效（剩余时间: {time_remaining}）")
            else:
                # 登录态无效或过期，自动刷新
                reason = check_result.get("message", "未知原因")
                logs.warning(f"[recording_agent] ⚠️ 登录态无效: {reason}")
                logs.info(f"[recording_agent] 🔄 正在自动刷新登录态...")
                
                # 使用 asyncio.to_thread 在单独线程中运行同步的 Playwright 代码
                # 避免在 asyncio 事件循环中直接调用 sync_playwright
                login_result = await asyncio.to_thread(bnp_login_and_save, headless=False, wait_stable_seconds=10)
                
                # 检查是否因为其他进程正在登录
                if login_result.get("error") == "login_in_progress":
                    logs.info(f"[recording_agent] ⏳ 其他进程正在登录，等待完成...")
                    wait_result = await asyncio.to_thread(wait_for_login_complete, auth_state_path_str, timeout=90.0)
                    if wait_result.get("success"):
                        should_load_auth = True
                        logs.info(f"[recording_agent] ✅ 等待登录完成，登录态有效")
                    else:
                        logs.error(f"[recording_agent] ❌ 等待登录失败: {wait_result.get('message')}")
                        logs.warning(f"[recording_agent]   将启动无登录态的浏览器会话")
                elif login_result.get("success"):
                    should_load_auth = True
                    logs.info(f"[recording_agent] ✅ 登录态刷新成功！")
                else:
                    logs.error(f"[recording_agent] ❌ 登录态刷新失败: {login_result.get('error')}")
                    logs.warning(f"[recording_agent]   将启动无登录态的浏览器会话")
        elif not should_load_auth and not auth_state_abs_path.exists():
            # 文件不存在，尝试自动登录
            logs.info(f"[recording_agent] ℹ️ 登录态文件不存在，尝试自动登录...")
            # 使用 asyncio.to_thread 在单独线程中运行同步的 Playwright 代码
            login_result = await asyncio.to_thread(bnp_login_and_save, headless=False, wait_stable_seconds=10)
            
            # 检查是否因为其他进程正在登录
            if login_result.get("error") == "login_in_progress":
                logs.info(f"[recording_agent] ⏳ 其他进程正在登录，等待完成...")
                wait_result = await asyncio.to_thread(wait_for_login_complete, auth_state_path_str, timeout=90.0)
                if wait_result.get("success"):
                    should_load_auth = True
                    logs.info(f"[recording_agent] ✅ 等待登录完成，登录态有效")
                else:
                    logs.warning(f"[recording_agent] ⚠️ 等待登录失败: {wait_result.get('message')}")
                    logs.info(f"[recording_agent]   将启动无登录态的浏览器会话")
            elif login_result.get("success"):
                should_load_auth = True
                logs.info(f"[recording_agent] ✅ 自动登录成功！")
            else:
                logs.warning(f"[recording_agent] ⚠️ 自动登录失败: {login_result.get('error')}")
                logs.info(f"[recording_agent]   将启动无登录态的浏览器会话")
    
    # 构建 Playwright MCP 启动参数
    # 注意：--storage-state 需要配合 --isolated 参数才能生效
    # 参考：https://github.com/microsoft/playwright-mcp
    playwright_args = [
        "-y", "@playwright/mcp@latest",
        "--viewport-size", "1920x1080",  # 默认浏览器窗口大小
    ]
    
    if should_load_auth:
        # 必须添加 --isolated 参数，否则 --storage-state 不生效
        playwright_args.append("--isolated")
        # 使用正斜杠格式的绝对路径，确保 MCP 能正确找到文件
        playwright_args.append(f"--storage-state={auth_state_path_str}")
    
    # 🚀 启动日志：区分 MCP 浏览器 vs 脚本执行浏览器
    logs.info("=" * 60)
    logs.info("🚀 [MCP Playwright] 启动浏览器（实时 MCP 模式）")
    logs.info("=" * 60)
    logs.info(f"   登录态加载: {'是' if should_load_auth else '否'}")
    if should_load_auth:
        logs.info(f"   登录态文件: {auth_state_path_str}")
    else:
        logs.info(f"   登录态文件: 未加载")
    logs.info(f"   启动参数: {' '.join(playwright_args)}")
    logs.info("=" * 60)
    
    # 创建 Playwright MCP client
    playwright_client = MultiServerMCPClient(
        {
            "playwright": {
                "transport": "stdio",
                "command": "npx",
                "args": playwright_args,
            }
        }
    )
    
    # Chart MCP 已移除 — recording_agent 不需要图表生成能力
    # 如需数据可视化，请使用主 agent（已集成 Chart MCP）
    
    # API Key 已由 llms.py 统一管理（通过 kiro-gateway）
    
    # 初始化模型（需要在中间件之前创建）
    model = get_model(agent_name="recording_agent")
    
    # 中间件配置（按执行顺序）
    # 创建语义选择器中间件（需要在代码收集器之前）
    semantic_selector = get_semantic_selector()
    
    # 创建代码收集器，传入语义选择器
    collector = get_collector(semantic_selector=semantic_selector)
    dom_cleaner = DOMCleanerMiddleware()
    base64_filter = Base64FilterMiddleware(config)
    
    logs.info(f"[unified_agent] 创建 SemanticSelectorMiddleware 实例: {id(semantic_selector)}")
    logs.info(f"[unified_agent] 创建 CodeCollectorMiddleware 实例: {id(collector)}")
    logs.info(f"[unified_agent] 创建 DOMCleanerMiddleware 实例: {id(dom_cleaner)}")
    logs.info(f"[unified_agent] 创建 Base64FilterMiddleware 实例: {id(base64_filter)}")
    
    middleware = [
        # Thread Context 中间件（最先执行，注入 thread_id 到 ContextVar）
        ThreadContextMiddleware(agent_name="recording_agent"),
        
        # 日志记录中间件
        BeforeAgentMiddleware(),
        
        # 语义选择器中间件（解析页面快照，提供语义信息）
        semantic_selector,
        
        # 代码收集中间件（拦截工具调用参数，生成语义化代码）
        collector,
        
        # Base64 图片过滤（awrap_tool_call 类型，工具返回后立即执行）
        # 关键：在存入消息历史之前就完成替换，避免 token 超限
        base64_filter,
        
        # DOM 清理中间件（清理工具返回的 DOM 数据）
        dom_cleaner,
        
        # Token 控制中间件（替代 SummarizationMiddleware）
        # 使用 Overwrite 直接替换 messages，避免发送 remove 消息
        # 支持历史摘要：保留关键信息，避免丢失上下文
        # 触发阈值：100000 tokens
        # 保留消息：最近 50 条
        # 摘要长度：最大 8000 字（~5300 tokens）
        TokenControlMiddleware(
            model=model,
            trigger_tokens=100000,
            keep_messages=50,
            max_summary_length=8000,
        ),
    ]
    
    # 录制回放工具（索引管理工具已移除，改用 shell/init_script_index.py 手动维护）
    recording_tools = [
        check_script,
        save_current_recording,
        list_scripts,
        delete_script,
        reset_recording,
        get_current_code,
        create_script_with_auth,
    ]
    
    # 本地工具
    # 注：Codegen 核心算法已移植到 SemanticSelectorMiddleware，无需 Codegen 服务
    script_save_tool = create_script_save_tool(config)
    executor_tool = create_playwright_executor_tool(config)
    parser_tool = create_result_parser_tool(config)
    
    # BNP 认证状态管理工具
    bnp_login_tool = create_bnp_login_tool(config)
    bnp_list_auth_tool = create_bnp_list_auth_states_tool(config)
    
    # 使用 Playwright MCP session（Chart MCP 已移除）
    # 使用 try-except 包裹整个 async with 块，捕获会话关闭时的 BrokenResourceError
    agent = None
    try:
        async with playwright_client.session("playwright") as playwright_session:
            
            # 初始化索引（启动时构建）
            index_manager = get_index_manager()
            index_manager.rebuild_index()
            logs.info(f"[unified_agent] 索引初始化完成，脚本数: {len(index_manager.index.scripts)}")
            
            # 加载 MCP 工具
            playwright_tools = await load_mcp_tools(playwright_session)
            
            # 🚀 P0-004: 将工具列表传递给语义选择器中间件
            # 使其能找到 browser_evaluate 工具进行自动 JS 注入
            semantic_selector.set_tools(playwright_tools)
            
            # 合并工具列表
            all_tools = (
                playwright_tools + 
                recording_tools + 
                [script_save_tool, executor_tool, parser_tool, bnp_login_tool, bnp_list_auth_tool]
            )
            
            logs.info(f"[unified_agent] 工具数量: {len(all_tools)}")
            logs.info(f"[unified_agent] 中间件数量: {len(middleware)}")
            logs.info(f"[unified_agent] 中间件类型: {[type(m).__name__ for m in middleware]}")
            
            # 创建 agent
            agent = create_deep_agent(
                tools=all_tools,
                system_prompt=SYSTEM_PROMPT,
                model=model,
                middleware=middleware,
            )
            
            yield agent
            
    except (anyio.BrokenResourceError, BaseExceptionGroup) as e:
        # MCP 会话在服务器关闭时可能抛出这些异常
        # 这是正常关闭流程，不需要打印错误日志
        error_msg = str(e)
        if isinstance(e, BaseExceptionGroup):
            # 检查是否是正常的关闭异常
            # 1. BrokenResourceError
            broken_errors = [exc for exc in e.exceptions if isinstance(exc, anyio.BrokenResourceError)]
            # 2. TaskGroup 异常（MCP 会话关闭时常见）
            is_taskgroup = "TaskGroup" in error_msg
            
            if broken_errors or is_taskgroup:
                # 正常关闭
                logs.info("[unified_agent] MCP 会话已正常关闭")
            else:
                # 包含其他异常，记录警告
                logs.warning(f"[unified_agent] MCP 会话关闭时出现异常: {e}")
        else:
            logs.info("[unified_agent] MCP 会话资源已释放")
    except Exception as e:
        # 其他异常正常抛出
        logs.error(f"[unified_agent] Agent 运行异常: {e}")
        raise


# 导出供 LangGraph API 使用
recording_agent = make_recording_agent