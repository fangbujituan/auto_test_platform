# Codegen 管线评估报告与改进方向

> 评估日期：2026-03-24
> 评估范围：DOM 快照处理、语义选择器生成、代码收集与生成、Codegen 录制服务、脚本质量评估

---

## 一、整体架构

当前管线是一个 5 层中间件协作的代码生成系统：

```
Playwright MCP 工具调用
  → DOMCleanerMiddleware（清理 DOM/快照，传递原始 HTML）
  → SemanticSelectorMiddleware（提取语义信息 + 生成选择器 + JS 注入增强）
  → CodeCollectorMiddleware（收集代码 + 双阶段生成 + 唯一值检测）
  → ScriptIndexManager（质量评估 + 索引管理 + 自动清理）
  → 最终 .spec.ts 脚本
```

架构分层清晰，中间件之间通过全局单例和引用传递协作。以下按模块逐一评估。

---

## 二、各模块评估

### 2.1 DOM 快照处理

**涉及文件**：`tools/utils/dom_utils.py`、`tools/middleware/dom_cleaner.py`

#### 现状优势

- 40+ 无用属性正则清理模式，覆盖面广（`USELESS_ATTRIBUTES` 列表）
- 空 generic 容器过滤逻辑完善（`_is_empty_generic` 多条件判断）
- 支持 Playwright YAML 快照和 HTML 两种格式的自动检测与分别清理
- `clean_dom_html_for_selectors()` 激进清理模式只保留选择器相关属性
- 动态 ID 检测（React `:r1:`、时间戳、随机字符串、UUID 片段）

#### 存在问题

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| 摘要退化 | `SNAPSHOT_SUMMARY_THRESHOLD = 20000`，清理后仍超过 20K 字符时直接生成摘要，只保留前 3 个交互元素的详细信息 | 大页面（如复杂表单、长列表）的元素信息大量丢失，后续选择器生成无法工作 |
| 属性黑名单模式 | `USELESS_ATTRIBUTES` 是"删除哪些"而非"保留哪些"，新增的无用属性需要手动添加 | 维护成本高，遗漏的属性会浪费 token |
| generic 元素语义缺失 | `_should_filter_element` 对有 `cursor=pointer` 的 generic 元素保留了空壳，但没有向下查找子元素文本 | 自定义组件（下拉框、Tab 等）保留后缺少语义信息，选择器生成时无法识别 |
| 动态 ID 检测可能误判 | `_is_dynamic_html_id` 的元音/辅音比例检测（0.3-0.7 范围）可能误删有效 ID | 部分有意义的短 ID（如 `uom`、`qty`）可能被误判为动态 ID |

#### 改进方向

1. **🔥 重复行截断**（P0，快照过大的根本原因）

   快照过大的根本原因不是属性多，而是列表/表格数据行的重复。一个 500 行的表格，每行结构几乎相同，只是数据不同，但每行都带 `[ref=eXXX]`，清理属性后仍然有 80K+ 字符。

   典型的大快照构成：
   ```
   页面头部/导航栏:     ~500 chars    (有用)
   搜索/筛选区域:       ~1000 chars   (有用)
   表格表头:            ~500 chars    (有用)
   表格数据行 x 500:   ~150K chars   (99% 是浪费) ← 元凶
   分页控件:            ~300 chars    (有用)
   ```

   解决方案：在 `clean_playwright_snapshot` 中增加重复结构检测与截断：
   - 检测连续的同结构行（同缩进、同元素类型模式，如 `row > cell > text + cell > link + cell > button`）
   - 只保留前 5 行 + 最后 1 行 + 摘要注释
   - 摘要格式：`// ... 省略 494 行相同结构的数据行（共 500 行）`

   实现思路：
   ```python
   def _detect_and_truncate_repeated_rows(lines: list, max_keep: int = 5) -> list:
       """检测重复的列表/表格行并截断"""
       # 1. 提取每行的"结构签名"（元素类型 + 缩进，忽略文本和 ref）
       #    例如: "  - row:" → sig = "2:row"
       #          "    - cell:" → sig = "4:cell"
       # 2. 找到连续 N 行（N > max_keep）结构签名相同的区间
       # 3. 只保留前 max_keep 行 + 最后 1 行 + 摘要注释
       pass
   ```

   预期效果：500 行表格 → 6 行 + 1 行注释，快照大小从 150K 降到 ~3K，不再触发 20K 摘要阈值。

2. **分级清理策略**（替代 20K 阈值摘要）
   - 轻度清理：保留完整结构，只移除无用属性（当前默认行为）
   - 中度清理：只保留有 `[ref=]` 的元素及其直接父级
   - 重度清理：只保留交互元素（button、textbox、link 等）
   - 根据清理后大小动态选择级别，避免直接跳到摘要
   - 注意：在重复行截断之后再做分级清理，效果更好

3. **属性白名单化**
   - 改为"保留哪些属性"模式：`[ref=]`、`[name=]`、`[data-testid=]`、`[aria-label=]`、`[placeholder=]`、`[cursor=pointer]`
   - 其他属性默认移除，更安全且不需要维护黑名单

4. **generic 元素语义补充**
   - 对 `generic[cursor=pointer]` 元素，向下搜索子元素的文本内容作为语义标注
   - 格式：`- generic [ref=e157] [cursor=pointer]: "子元素文本"`

5. **动态 ID 检测优化**
   - 增加长度下限：3 字符以下的 ID 不做动态检测
   - 增加语义关键词白名单的覆盖面（当前 50+ 个，建议补充业务相关词汇）

---

### 2.2 语义选择器生成

**涉及文件**：`tools/middleware/semantic_selector.py`

#### 现状优势

- 完整移植了 Playwright Codegen 的评分常量体系（`K_TEST_ID_SCORE = 1` 到 `K_CSS_FALLBACK_SCORE = 10000000`）
- 4 层隐式标签提取策略（前一个兄弟元素 → 同行前缀 → 父级元素 → 附近关键字）
- JS 注入增强检测（v8），支持 cursor:pointer 检测、label[for] 关联、xpath 映射
- 智能恢复机制：ref 失效时通过模糊搜索（完全匹配 → 包含匹配 → 词组匹配 → 类型匹配）找到替代元素
- `_parse_element_hint` 支持中文元素类型关键词解析（复选框 → checkbox、下拉框 → combobox 等）
- `suitable_text_alternatives` 移植了 Codegen 的文本变体生成策略

#### 存在问题

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| 评分体系未真正用于排序 | `_generate_semantic_selector` 中使用 if-elif 硬编码优先级链，而非为每个候选选择器计算分数后取最优 | 评分常量定义了但没有发挥作用，选择器优先级依赖人工维护的 if-elif 顺序 |
| 解析效率低 | `_parse_element_line` 使用 10+ 个独立正则逐一匹配（role、name、testid、aria-label、placeholder、type+text、generic text、textbox、combobox、checkbox、radio、cursor） | 每个元素需要执行 10+ 次正则匹配，大页面（100+ 元素）时性能开销明显 |
| 缓存无大小限制 | `_element_cache`、`_snapshot_context_cache`、`_ai_generated_code`、`_html_element_attrs` 等 dict 无上限 | 长时间运行（多轮对话）时内存持续增长 |
| 隐式标签提取依赖快照顺序 | 策略 1（前一个兄弟元素）依赖元素在快照中的物理顺序 | React/Vue 虚拟 DOM 渲染的组件，快照中的元素顺序可能与视觉顺序不一致 |
| 文本变体策略有限 | `suitable_text_alternatives` 只处理了数字前缀/后缀和长度截断 | 未处理常见 UI 模式：括号内容（"保存 (Ctrl+S)"）、数量词（"删除 3 项"）、省略号（"更多..."） |
| CSS type 选择器回退过于宽泛 | 当 implicit_label 包含 "user" 或 "name" 时，生成 `input[type="text"], input[type="email"]').first()` | `.first()` 在多输入框页面几乎必定定位错误 |

#### 改进方向

1. **真正用评分体系做选择器排序**
   - 为每个元素生成所有候选选择器（getByTestId、getByRole+name、getByLabel、getByPlaceholder、getByText、CSS 选择器）
   - 为每个候选计算分数（使用已定义的 K_* 常量）
   - 取分数最低的选择器作为最终结果
   - 这样新增选择器类型只需要定义分数，不需要调整 if-elif 顺序

2. **统一结构化解析器**
   - 将 `_parse_element_line` 改为一次正则提取所有属性到 dict
   - 参考格式：`- type "name" [ref=eXX] [attr1=val1] [attr2=val2]: text`
   - 一次匹配提取 type、name、ref、所有 `[key=value]` 属性、冒号后文本

3. **LRU 缓存限制**
   - `_element_cache` 限制 500 个元素（使用 `collections.OrderedDict` 或 `functools.lru_cache`）
   - 页面切换时自动清理旧缓存

4. **文本变体增强**
   - 增加括号内容剥离：`"保存 (Ctrl+S)"` → `"保存"`
   - 增加数量词剥离：`"删除 3 项"` → `"删除"`
   - 增加省略号剥离：`"更多..."` → `"更多"`
   - 增加快捷键剥离：`"Ctrl+S"` → 跳过

5. **消除 `.first()` 回退**
   - 当无法生成精确选择器时，生成带 TODO 标记的占位代码 + 元素上下文注释
   - 而非生成 `input[type="text"]').first()` 这种必定失败的代码

---

### 2.3 代码收集与生成

**涉及文件**：`tools/middleware/code_collector.py`

#### 现状优势

- 双阶段生成（v2.0）：工具调用前初步生成 → 返回后利用更新的快照优化
- 唯一值字段检测 + 时间戳变量替换（`const timestamp = Date.now()`）
- JS → Playwright 转换：支持 `querySelector.click()`、`.value = x`、`dispatchEvent()` 模式
- 回退策略分层：AI 代码 → 规则语义 → getByText → JS evaluate
- 选择器统计（`ref_count` vs `semantic_count`）用于质量评估

#### 存在问题

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| 无效回退代码 | click 回退到 `page.getByText('...').first().click()`，type 回退到 `page.locator('input').first().fill()`，hover 回退到 `page.locator('[cursor=pointer]').first().hover()` | 这些 `.first()` 选择器在实际页面上几乎不可能定位到正确元素，生成的脚本必定失败 |
| 缺少等待逻辑 | `browser_navigate` 生成 `page.goto(url)` 后没有插入等待，`browser_click` 后也没有等待 | 考虑到 AGENTS.md 提到的慢网络环境（20-30 秒），脚本回放时容易因时序问题失败 |
| 唯一值检测硬编码 | 关键字列表 `['charge code', 'item name', 'code', '编号', ...]` 是硬编码的 | 不够通用，新业务字段需要手动添加 |
| JS 解析能力有限 | `_parse_javascript_to_playwright` 只处理最简单的 `querySelector.click()` 模式 | 链式调用（`el.closest().querySelector()`）、变量引用（`const el = ...`）、多语句操作无法处理 |
| 缺少断言生成 | 生成的脚本只有操作代码，没有 `expect` 断言 | 脚本只能验证"不报错"，无法验证"操作结果正确" |

#### 改进方向

1. **回退策略改进**
   - 当语义选择器失败时，生成带 TODO 标记的占位代码：
     ```typescript
     // ⚠️ TODO: 需要手动修改选择器
     // 元素描述: "Save Changes 按钮"
     // 元素类型: button, 位于页面底部表单区域
     await page.getByRole('button', { name: 'Save Changes' }).click();
     ```
   - 同时在注释中提供元素的上下文信息（类型、位置、附近元素），方便人工修改

2. **自动插入等待逻辑**
   - `browser_navigate` 后插入 `await page.waitForLoadState('networkidle');`
   - `browser_click` 后，如果下一个操作是不同页面的元素，插入 `await page.waitForTimeout(2000);`
   - 可配置等待策略（aggressive / normal / minimal）

3. **唯一值检测改进**
   - 基于启发式规则：input[type=text] + 值长度 < 20 + 字段名包含 "code/name/id/编号" → 标记为唯一值
   - 或者：检测到填入的值在页面上已存在（通过快照搜索），自动标记为需要唯一化

4. **断言生成**
   - 导航后：`await expect(page).toHaveURL(/expected-pattern/);`
   - 表单提交后：`await expect(page.getByText('成功')).toBeVisible();`
   - 列表操作后：`await expect(page.locator('table tbody tr')).toHaveCount(expectedCount);`
   - 可配置断言级别（none / basic / comprehensive）

---

### 2.4 Codegen 录制服务

**涉及文件**：`tools/playwright/recorder/recorder-server.js`、`tools/playwright/recorder/recorder_client.py`、`tools/playwright/recorder/codegen_tools.py`

#### 现状优势

- 正确使用了 `context._enableRecorder()` 内部 API，获取 Playwright 原生 Codegen 质量的代码
- WebSocket 通信架构清晰，支持完整的操作集（click、fill、select、hover、press、screenshot）
- 支持 storageState 登录态加载
- Python 客户端提供 async context manager 接口，资源管理规范

#### 存在问题

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| 内部 API 无版本保护 | `_enableRecorder` 是 Playwright 未公开 API，没有版本锁定或可用性检测 | Playwright 升级可能直接 break，且无降级方案 |
| 代码读取时序问题 | `getCodegenCode` 直接读取 `outputFile`，没有检测文件写入是否完成 | 可能读取到不完整的代码（Codegen 还在写入时） |
| 备用代码质量低 | `generateCodeFromActions` 直接使用传入的 selector 字符串拼接代码 | 当 Codegen 输出文件不存在时，备用代码没有语义化处理 |
| 无并发控制 | 多个 WebSocket 客户端可以同时连接并操作同一个 browser 实例 | 并发操作会导致状态混乱 |
| 无错误恢复 | 浏览器崩溃后 WebSocket 连接不会自动重连，server 状态不会重置 | 需要手动重启服务 |

#### 改进方向

1. **API 可用性检测 + 降级**
   ```javascript
   // 检测 _enableRecorder 是否可用
   if (typeof this.context._enableRecorder === 'function') {
     await this.context._enableRecorder({ mode: 'recording', ... });
   } else {
     console.warn('_enableRecorder not available, falling back to action log mode');
     this.fallbackMode = true;
   }
   ```

2. **文件写入完成检测**
   ```javascript
   async getCodegenCode() {
     if (this.outputFile && fs.existsSync(this.outputFile)) {
       // 等待文件大小稳定（500ms 内无变化）
       let lastSize = 0;
       for (let i = 0; i < 10; i++) {
         const stat = fs.statSync(this.outputFile);
         if (stat.size === lastSize && stat.size > 0) break;
         lastSize = stat.size;
         await new Promise(r => setTimeout(r, 500));
       }
       return { success: true, code: fs.readFileSync(this.outputFile, 'utf-8') };
     }
   }
   ```

3. **单例锁 + 心跳**
   - 限制同时只有一个客户端连接
   - 增加 WebSocket ping/pong 心跳（30 秒间隔）
   - 浏览器崩溃时自动清理状态并通知客户端

---

### 2.5 脚本质量评估

**涉及文件**：`tools/playwright/script_index.py`

#### 现状优势

- 多维度评分：成功率 40% + 语义比例 30% + 代码完整性 20% + 使用频率 10%
- 回收站机制 + 7 天过期自动清理
- 相似脚本检测（`SequenceMatcher`）
- 后台异步清理（每 50 次操作触发，不阻塞主流程）

#### 存在问题

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| 新脚本分数虚高 | 新脚本 `usage_count=0`、`success_rate=1.0`（默认值），`has_code=True`，计算得分 = 0.4 + 0.15 + 0.2 + 0 = 0.75 | 从未执行过的脚本质量分数高于多次执行但偶有失败的脚本 |
| 语义比例依赖运行时统计 | `ref_count` 和 `semantic_count` 在 CodeCollectorMiddleware 中统计，手动编写的脚本无法评估 | 手动编写的高质量脚本可能因为 `ref_count=0, semantic_count=0` 而得到中等分数 |
| 相似脚本检测不够准确 | 使用 `SequenceMatcher` 比较脚本名称的相似度 | 名称相似但功能不同的脚本可能被误判为重复（如 `add_billing_item` vs `edit_billing_item`） |

#### 改进方向

1. **新脚本冷启动惩罚**
   ```python
   # usage_count < 3 时，质量分数打折
   if entry.usage_count < 3:
       score *= 0.7  # 30% 惩罚
   ```

2. **静态代码分析**
   - 直接扫描 `.spec.ts` 文件内容，统计选择器类型：
     - `getByRole`、`getByLabel`、`getByText`、`getByTestId`、`getByPlaceholder` → 语义化
     - `locator('...')` 中包含 CSS 选择器 → 非语义化
     - `page.evaluate` → 最差
   - 不依赖运行时统计，手动编写的脚本也能准确评估

3. **相似脚本检测改进**
   - 比较 URL pattern + 操作类型序列的相似度（而非脚本名称）
   - 从 `.spec.ts` 文件中提取操作序列：`[goto, click, fill, click, expect]`
   - 两个脚本的操作序列相似度 > 0.8 且 URL pattern 相同 → 判定为相似

---

## 三、系统级改进方向

### 3.1 核心瓶颈：Accessibility Tree 与真实 DOM 的信息鸿沟

Playwright MCP 返回的是 YAML 格式的 accessibility tree（快照），而非真实 DOM。快照中缺少大量 HTML 属性（`data-testid`、`name`、`class`、完整的 `aria-*`），这是选择器生成质量的根本瓶颈。

当前的解决方案是 JS 注入检测（v8），但需要额外的 `browser_evaluate` 工具调用，增加延迟和 token 消耗。

**建议：一次性批量属性提取**

在 `browser_snapshot` 返回后，自动注入一段 JS 脚本，一次性提取所有可交互元素的完整属性：

```javascript
// 注入到页面中，一次性提取所有可交互元素信息
() => {
  const interactiveSelectors = 'button, a, input, select, textarea, [role], [tabindex], [onclick], [cursor]';
  const elements = document.querySelectorAll(interactiveSelectors);
  return Array.from(elements).map((el, i) => ({
    index: i,
    tagName: el.tagName.toLowerCase(),
    id: el.id || null,
    name: el.getAttribute('name'),
    type: el.getAttribute('type'),
    placeholder: el.getAttribute('placeholder'),
    'data-testid': el.getAttribute('data-testid'),
    'aria-label': el.getAttribute('aria-label'),
    role: el.getAttribute('role'),
    textContent: el.textContent?.trim().substring(0, 100),
    isVisible: el.offsetParent !== null,
    cursor: getComputedStyle(el).cursor,
    // label[for] 关联
    label: el.id ? document.querySelector(`label[for="${el.id}"]`)?.textContent?.trim() : null,
  }));
}
```

这样后续所有选择器生成都可以基于完整信息，而非从 YAML 快照中猜测。

### 3.2 端到端验证

当前生成的代码没有经过验证就保存了。建议增加：

1. **选择器验证**：生成后用 `page.locator(selector).count()` 验证是否能定位到元素
2. **自动降级**：如果定位失败，自动尝试下一优先级的选择器
3. **保存前 dry-run**（可选）：无头模式快速回放，验证脚本可执行性

### 3.3 上下文感知的代码生成

当前的代码生成是逐操作独立的，缺少上下文感知：

- 连续两次 click 同一个元素（展开/收起），应该生成不同的注释
- 表单填写场景应该识别为一个整体，生成更结构化的代码块
- 分页操作应该识别为循环模式

建议增加操作序列模式识别：

| 模式 | 识别条件 | 生成模板 |
|------|----------|----------|
| 登录 | navigate + fill(username) + fill(password) + click(submit) | 登录代码块 + 断言 |
| 表单填写 | 连续 3+ 个 fill 操作 | 表单数据对象 + 循环填写 |
| 列表翻页 | click(page N) 重复出现 | for 循环 + 页码变量 |
| 搜索筛选 | fill(search) + click(search button) + 等待结果 | 搜索函数封装 |

### 3.4 Token 效率优化

- 中间件之间用共享上下文对象传递数据，减少重复解析（当前 DOMCleaner 和 SemanticSelector 各自独立解析快照）
- 日志级别细化：正常流程用 DEBUG，只有异常和回退用 INFO/WARNING（当前大量 INFO 日志）
- 快照缓存增加 hash 校验，如果快照内容没变就跳过重新解析

---

## 四、优先级排序

| 优先级 | 改进项 | 涉及文件 | 预期收益 | 工作量 |
|--------|--------|----------|----------|--------|
| P0 | 🔥 重复行截断（列表/表格数据去重） | `dom_utils.py` | 快照大小降低 90%+，根治大页面摘要退化问题 | 中 |
| P0 | 一次性 JS 批量属性提取（替代逐个 JS 检测） | `semantic_selector.py`, `dom_cleaner.py` | 选择器质量大幅提升，减少额外工具调用 | 中 |
| P0 | 消除 `.first()` 无效回退代码 | `code_collector.py`, `semantic_selector.py` | 脚本可执行率提升 | 小 |
| P1 | 操作后自动插入等待逻辑 | `code_collector.py` | 脚本回放稳定性提升（尤其慢网络） | 小 |
| P1 | 真正用评分体系做选择器排序 | `semantic_selector.py` | 选择器质量一致性提升，维护成本降低 | 中 |
| P1 | 选择器生成后立即验证 | `semantic_selector.py`, `code_collector.py` | 减少无效脚本 | 中 |
| P1 | 新脚本冷启动惩罚 + 静态代码分析 | `script_index.py` | 评分准确性提升 | 小 |
| P2 | 快照分级清理（替代 20K 阈值摘要） | `dom_cleaner.py`, `dom_utils.py` | 大页面信息保留度提升 | 中 |
| P2 | 操作序列模式识别 + 断言生成 | `code_collector.py` | 代码可读性和复用性提升 | 大 |
| P2 | recorder-server.js 健壮性增强 | `recorder-server.js`, `recorder_client.py` | 长时间运行稳定性 | 中 |
| P2 | 统一结构化快照解析器 | `semantic_selector.py` | 解析效率提升，新格式适配更容易 | 中 |
| P3 | LRU 缓存限制 + 共享上下文 | `semantic_selector.py` | 内存和性能优化 | 小 |
| P3 | 相似脚本检测改进 | `script_index.py` | 减少误判 | 小 |
| P3 | 文本变体策略增强 | `semantic_selector.py` | 边缘场景选择器质量提升 | 小 |

---

## 五、量化评估：改进后准确率预测

### 5.1 基线数据

基于 `playwright_results/` 目录下 43 次测试运行记录的统计分析：

| 指标 | 数值 |
|------|------|
| 总运行次数 | 43 |
| 通过（expected ≥ 1） | ~17 次 |
| 失败（unexpected ≥ 1） | ~24 次 |
| 解析错误（无测试执行） | 2 次 |
| **当前首次运行通过率** | **~40%** |

### 5.2 失败原因分类

对 24 次失败记录的错误日志进行归因分析：

| 失败类别 | 占比 | 典型错误 | 影响的运行次数 |
|----------|------|----------|----------------|
| 选择器错误 | ~35% | strict mode violation（getByText 匹配到 2 个元素）、getByLabel('*Charge Code') 找不到元素、错误的选择器语法 | ~8 次 |
| 超时错误 | ~30% | page.waitForLoadState timeout、test timeout exceeded（慢网络 20-30s） | ~7 次 |
| 代码生成 Bug | ~15% | `timestamp is not defined`（变量未声明）、`.lter()` 拼写错误（应为 `.filter()`）、`/^*Item Name$/` 无效正则 | ~4 次 |
| 登录态/环境错误 | ~15% | auth state 文件不存在、登录态过期 | ~4 次 |
| 元素可见性 | ~5% | `input[type="checkbox"]` 被 UI 框架隐藏 | ~1 次 |

### 5.3 各改进项对失败类别的影响映射

#### P0 改进项

| 改进项 | 解决的失败类别 | 机制 | 预计消除的失败次数 |
|--------|---------------|------|-------------------|
| 🔥 重复行截断 | 选择器错误（部分） | 快照不再触发 20K 摘要退化，元素信息完整保留，选择器生成有足够上下文 | 3~4 次（约占选择器错误的 50%） |
| JS 批量属性提取 | 选择器错误（部分） | 获取 data-testid、name、aria-label 等真实 DOM 属性，生成更精确的选择器 | 2~3 次（约占选择器错误的 30%） |
| 消除 `.first()` 回退 | 选择器错误（部分） | 不再生成 `page.locator('input').first().fill()` 这类必定失败的代码 | 2~3 次（约占选择器错误的 25%） |

P0 合计预计消除选择器错误：6~8 次中的 **6~7 次**（部分重叠，三项改进互补覆盖几乎所有选择器问题）

#### P1 改进项

| 改进项 | 解决的失败类别 | 机制 | 预计消除的失败次数 |
|--------|---------------|------|-------------------|
| 自动插入等待逻辑 | 超时错误（大部分） | navigate 后 waitForLoadState、click 后适当等待，适配慢网络 | 5~6 次（约占超时错误的 75%） |
| 评分体系排序 | 选择器错误（残余） | 系统化选择最优选择器，减少边缘情况 | 0~1 次 |
| 选择器验证 | 选择器错误（残余） | 生成后立即验证，失败则自动降级 | 0~1 次 |

#### P2 改进项

| 改进项 | 解决的失败类别 | 机制 | 预计消除的失败次数 |
|--------|---------------|------|-------------------|
| 断言生成 + 模式识别 | 代码生成 Bug（部分） | 结构化模板减少拼写错误和变量遗漏 | 2~3 次 |
| 分级清理策略 | 选择器错误（极端场景） | 超大页面也能保留关键元素信息 | 0~1 次 |

#### 不可通过代码改进解决的

| 失败类别 | 次数 | 原因 |
|----------|------|------|
| 登录态/环境错误 | ~4 次 | 属于运维问题（auth 文件管理、网络环境），非代码生成质量问题 |
| 超时错误（残余） | ~1~2 次 | 极端网络波动，无法通过等待逻辑完全消除 |

### 5.4 分阶段准确率预测

```
                    消除的失败次数    剩余失败次数    预测通过率
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前基线               —              ~24 次         ~40%
                                                    
完成 P0 后          6~7 次           ~17 次         ~60%
（重复行截断 +                                      
 JS批量属性 +                                       
 消除.first()）                                     

完成 P0+P1 后       11~13 次         ~11 次         ~72~75%
（+ 等待逻辑 +                                      
 评分排序 +                                         
 选择器验证）                                       

完成 P0+P1+P2 后    13~16 次         ~8 次          ~80~82%
（+ 断言生成 +                                      
 模式识别 +                                         
 分级清理）                                         

理论上限                              ~5 次          ~88%
（排除环境/网络                                     
 不可控因素）                                       
```

### 5.5 关键假设与风险

| 假设 | 风险 |
|------|------|
| 重复行截断能将快照控制在 20K 以内 | 如果页面有多个独立的大表格，可能需要更复杂的截断策略 |
| JS 批量属性提取能获取到 data-testid | 目标应用可能没有设置 data-testid，此时收益降低 |
| 等待逻辑能覆盖大部分超时场景 | 极端慢网络（>30s）可能需要更长的超时配置 |
| 失败原因分类准确 | 部分失败可能有多个原因叠加，实际消除效果可能低于预期 |

### 5.6 投入产出比排序

按"预计提升通过率 / 工作量"排序：

| 排名 | 改进项 | 工作量 | 预计提升 | ROI |
|------|--------|--------|----------|-----|
| 1 | 自动插入等待逻辑 | 小（0.5 天） | +12%（5~6 次） | ⭐⭐⭐⭐⭐ |
| 2 | 消除 `.first()` 回退 | 小（0.5 天） | +5%（2~3 次） | ⭐⭐⭐⭐ |
| 3 | 重复行截断 | 中（1~2 天） | +8%（3~4 次） | ⭐⭐⭐⭐ |
| 4 | JS 批量属性提取 | 中（1~2 天） | +5%（2~3 次） | ⭐⭐⭐ |
| 5 | 评分体系排序 | 中（1~2 天） | +2%（0~1 次） | ⭐⭐ |
| 6 | 断言生成 + 模式识别 | 大（3~5 天） | +5%（2~3 次） | ⭐⭐ |

### 5.7 结论

- 当前首次运行通过率约 **40%**
- 完成全部 P0 改进后，预计提升至 **~60%**（最高 ROI 的阶段）
- 完成 P0+P1 后，预计提升至 **~72~75%**
- 完成全部改进后，预计提升至 **~80~82%**
- 理论上限约 **~88%**（剩余 12% 为登录态过期、极端网络波动等环境因素）

建议优先实施"自动插入等待逻辑"和"消除 `.first()` 回退"两项，工作量最小（各 0.5 天），合计可将通过率从 40% 提升至约 **55%**。

---

## 六、JS 注入深度分析与优化方案

> 涉及文件：`tools/middleware/semantic_selector.py`（`JS_INTERACTIVE_DETECTOR` 常量 + `process_js_detection_result` + `_merge_js_detection_to_cache`）

### 6.1 当前 JS 注入架构

```
browser_snapshot 返回
  → DOMCleaner 清理快照
  → SemanticSelector.update_snapshot() 解析元素
  → [被动等待] Agent 调用 browser_evaluate(JS_INTERACTIVE_DETECTOR)
  → process_js_detection_result() 合并到缓存
  → _merge_js_detection_to_cache() 补充 data-testid/name/aria-label 等
  → 后续操作时 _generate_semantic_selector() 优先使用 JS 推荐选择器
```

JS 注入脚本（`JS_INTERACTIVE_DETECTOR`）在浏览器端完成以下工作：
- 收集所有可交互元素（选择器 + cursor:pointer 全量遍历）
- 提取 20+ 个属性（id、name、role、aria-label、data-testid、placeholder 等）
- 为每个元素生成选择器候选列表（带 Codegen 风格评分）
- 提取 label[for] 关联映射
- 检测动态 ID（React `:r1:`、长随机字符串等）

### 6.2 存在的问题与优化方案

#### 问题 1：`querySelectorAll('*')` 全量遍历性能瓶颈

**现状**：为检测 `cursor:pointer` 元素，遍历页面所有 DOM 节点并调用 `getComputedStyle`。

**影响**：500 行表格页面约 5000+ DOM 节点，每个节点调用 `getComputedStyle` 触发样式计算，耗时 100-300ms，在慢设备上可能更长。

**修复方案**：

```javascript
// ❌ 当前：全量遍历
document.querySelectorAll('*').forEach(el => {
    const style = window.getComputedStyle(el);
    if (style.cursor === 'pointer' || style.cursor === 'hand') {
        interactiveElements.add(el);
    }
});

// ✅ 修复：限制遍历范围到可能可点击的元素
const clickableCandidates = [
    'div[class*="btn"]', 'div[class*="click"]', 'div[class*="link"]',
    'div[class*="item"]', 'div[class*="option"]', 'div[class*="menu"]',
    'span[class*="btn"]', 'span[class*="icon"]', 'span[class*="link"]',
    'li', 'td', 'th', 'img', 'svg', 'i',
    '[style*="cursor"]',  // 内联 cursor 样式
    '[role]',             // 有 ARIA role 的元素（已在 interactiveSelectors 中，但可能有 cursor:pointer 的）
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

**预期效果**：遍历元素数从 5000+ 降到 200-500，`getComputedStyle` 调用减少 90%。

---

#### 问题 2：缺少 `aria-labelledby` 解析

**现状**：JS 脚本提取了 `ariaLabelledby` 属性值，但 `generatePlaywrightSelector` 中未使用它生成选择器。

**影响**：`aria-labelledby` 指向另一个元素的 ID，是 WCAG 标准的标签关联方式。很多 UI 框架（Ant Design、Element UI）使用 `aria-labelledby` 而非 `label[for]`，当前完全忽略了这个信息源。

**修复方案**：

在 `generatePlaywrightSelector` 函数中，label 候选之前增加：

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

同时在 Python 端 `_merge_js_detection_to_cache` 中，将 `aria-labelledby` 解析结果也合并到缓存：

```python
# 在 _merge_js_detection_to_cache 的 matched 分支中增加
js_aria_labelledby = js_elem.get('ariaLabelledby')
if js_aria_labelledby and not cached_elem.get('aria-labelledby'):
    cached_elem['aria-labelledby'] = js_aria_labelledby
    updated = True
```

**预期效果**：对使用 `aria-labelledby` 的 UI 框架，getByLabel 命中率提升 20-30%。

---

#### 问题 3：JS 端选择器缺少唯一性验证（关键缺失）

**现状**：JS 端生成选择器候选后直接返回，没有验证选择器在页面上是否唯一匹配。

**影响**：Playwright strict mode 要求选择器只匹配一个元素，否则抛出 `strict mode violation`。当前 35% 的失败是选择器错误，其中相当一部分是 strict mode violation。如果 JS 端能提前验证唯一性，就能在候选阶段淘汰不唯一的选择器。

**修复方案**：

```javascript
// 在 generatePlaywrightSelector 函数末尾，排序之前增加唯一性验证
function verifyUniqueness(candidate, el) {
    try {
        let matchCount = null;
        const code = candidate.code;
        
        // CSS 选择器验证
        if (code.includes("locator('#")) {
            const id = code.match(/#([^'")]+)/)?.[1];
            if (id) matchCount = document.querySelectorAll('#' + CSS.escape(id)).length;
        }
        else if (code.includes("[name=")) {
            const name = code.match(/name="([^"]+)"/)?.[1];
            if (name) matchCount = document.querySelectorAll(`[name="${name}"]`).length;
        }
        else if (code.includes("[data-testid=")) {
            const testid = code.match(/data-testid="([^"]+)"/)?.[1] ||
                           code.match(/getByTestId\('([^']+)'\)/)?.[1];
            if (testid) matchCount = document.querySelectorAll(`[data-testid="${testid}"]`).length;
        }
        // getByRole 验证（近似）
        else if (code.includes("getByRole")) {
            const roleMatch = code.match(/getByRole\('(\w+)'/);
            const nameMatch = code.match(/name:\s*'([^']+)'/);
            if (roleMatch) {
                const role = roleMatch[1];
                const roleEls = document.querySelectorAll(`[role="${role}"]`);
                // 标签推断的 role
                const tagRoleMap = { button: 'button', a: 'link' };
                const tagEls = Object.entries(tagRoleMap)
                    .filter(([_, r]) => r === role)
                    .flatMap(([tag]) => [...document.querySelectorAll(tag)]);
                const allEls = [...new Set([...roleEls, ...tagEls])];
                
                if (nameMatch) {
                    const name = nameMatch[1];
                    matchCount = allEls.filter(e => 
                        (e.textContent || '').trim().includes(name) ||
                        (e.getAttribute('aria-label') || '').includes(name)
                    ).length;
                } else {
                    matchCount = allEls.length;
                }
            }
        }
        // getByText 验证（近似）
        else if (code.includes("getByText")) {
            const textMatch = code.match(/getByText\('([^']+)'\)/);
            if (textMatch) {
                const searchText = textMatch[1];
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null
                );
                let count = 0;
                while (walker.nextNode()) {
                    if (walker.currentNode.textContent.trim().includes(searchText)) {
                        count++;
                    }
                }
                matchCount = count;
            }
        }
        
        if (matchCount !== null) {
            candidate.unique = matchCount === 1;
            candidate.matchCount = matchCount;
            // 非唯一选择器加重惩罚
            if (matchCount > 1) {
                candidate.score += 5000;  // 大幅降低优先级
            } else if (matchCount === 0) {
                candidate.score += 10000; // 匹配不到的更差
            }
        }
    } catch(e) {
        candidate.unique = null;
        candidate.matchCount = null;
    }
}

// 在 candidates.sort 之前调用
candidates.forEach(c => verifyUniqueness(c, el));
candidates.sort((a, b) => a.score - b.score);
```

Python 端合并时优先选择 `unique=true` 的候选：

```python
# 在 _merge_browser_candidates 中，对浏览器端候选增加唯一性权重
if unique is True:
    score -= 10  # 唯一选择器额外加分（分数越低越好）
elif unique is False:
    score += 5000  # 非唯一选择器大幅降级
```

**预期效果**：strict mode violation 错误减少 60-80%，这是选择器错误中占比最大的子类。

---

#### 问题 4：JS 与 Python 端评分常量不一致

**现状**：

| 评分项 | JS 端 | Python 端 | 差异 |
|--------|-------|-----------|------|
| aria-label | `ARIA_LABEL: 110` | 无对应常量 | JS 多出 |
| CSS name | `CSS_NAME: 510` | `K_ROLE_WITHOUT_NAME_SCORE = 510` | 语义不同 |
| CSS ID | `CSS_ID: 500` | `K_CSS_ID_SCORE = 500` | 一致 |
| role+name | `ROLE_WITH_NAME: 100` | `K_ROLE_WITH_NAME_SCORE = 100` | 一致 |

**影响**：JS 端和 Python 端对同一个元素可能给出不同的最佳选择器推荐，导致合并时出现冲突。

**修复方案**：

1. Python 端增加缺失常量：

```python
# 在常量定义区域增加
K_ARIA_LABEL_SCORE = 110  # aria-label 属性（JS 端已有）
K_CSS_NAME_SCORE = 510    # CSS [name="xxx"] 选择器（重命名，与 JS 端对齐）
```

2. 将常量提取为共享配置：

```python
# tools/middleware/selector_scores.py（新文件）
"""
选择器评分常量（Codegen 风格）
JS 端和 Python 端共享同一套评分体系
"""

SELECTOR_SCORES = {
    'TEST_ID': 1,
    'OTHER_TEST_ID': 2,
    'IFRAME_BY_ATTRIBUTE': 10,
    'ROLE_WITH_NAME': 100,
    'ARIA_LABEL': 110,
    'PLACEHOLDER': 120,
    'LABEL': 140,
    'ALT_TEXT': 160,
    'TEXT': 180,
    'TITLE': 200,
    'TEXT_REGEX': 250,
    'CSS_ID': 500,
    'ROLE_WITHOUT_NAME': 510,
    'CSS_NAME': 515,
    'CSS_INPUT_TYPE': 520,
    'CSS_TAG_NAME': 530,
    'NTH': 10000,
    'CSS_FALLBACK': 10000000,
}
```

3. JS 端的常量从 Python 端动态注入（或在构建时同步）：

```python
def get_js_detection_script(self) -> str:
    """动态生成 JS 脚本，确保评分常量与 Python 端一致"""
    from tools.middleware.selector_scores import SELECTOR_SCORES
    scores_js = "const SCORE = " + json.dumps(SELECTOR_SCORES) + ";"
    return self.JS_INTERACTIVE_DETECTOR_TEMPLATE.replace(
        '// __SCORES_PLACEHOLDER__', scores_js
    )
```

**预期效果**：消除 JS/Python 双端评分不一致导致的选择器冲突。

---

#### 问题 5：JS 注入时机为被动触发

**现状**：`awrap_tool_call` 中，`browser_navigate` 返回后只追加了一个文本提示（`_append_html_fetch_hint`），依赖 Agent 主动调用 `browser_evaluate` 执行 JS 检测脚本。

**影响**：如果 Agent 没有执行 JS 检测（跳过了提示），后续所有操作都只能依赖快照信息生成选择器，质量大幅下降。

**修复方案**（两个层级）：

方案 A（推荐，低侵入）：在 system prompt 中强制要求 Agent 执行 JS 检测

```python
# tools/playwright/prompts.py 中增加
JS_DETECTION_INSTRUCTION = """
⚠️ 重要：每次 browser_navigate 或 browser_snapshot 后，必须立即执行：
browser_evaluate(expression="<JS_INTERACTIVE_DETECTOR>")
这将提取页面所有可交互元素的完整属性，显著提升后续操作的选择器质量。
"""
```

方案 B（理想，需架构调整）：中间件内部自动触发

```python
# 在 awrap_tool_call 中，browser_snapshot 返回后自动注入
if tool_name in ['browser_navigate', 'browser_snapshot']:
    content = self._extract_content(result)
    if content:
        self.update_snapshot(content, raw_html)
        
        # 🚀 自动触发 JS 检测（构造内部工具调用）
        if not self._js_detected_for_current_page:
            try:
                js_request = self._create_internal_request(
                    tool_name='browser_evaluate',
                    args={'expression': self.JS_INTERACTIVE_DETECTOR}
                )
                js_result = await handler(js_request)
                js_content = self._extract_content(js_result)
                if js_content:
                    import json
                    js_data = json.loads(js_content)
                    self.process_js_detection_result(js_data)
                    self._js_detected_for_current_page = True
            except Exception as e:
                logs.warning(f"[SemanticSelector] 自动 JS 检测失败: {e}")
```

方案 B 需要中间件能构造内部请求并调用 handler，这取决于 LangGraph 中间件的 API 是否支持。如果不支持，方案 A 是务实的选择。

**预期效果**：JS 检测覆盖率从"依赖 Agent 行为"提升到 100%。


---

## 七、语义选择器算法体系深度评估

> 涉及文件：`tools/middleware/semantic_selector.py`（4600+ 行）
> 评估范围：Codegen 评分体系、双路径选择器生成、三源数据融合、隐式标签提取、element_hint 解析

### 7.1 架构优势（做得好的部分）

#### 7.1.1 Codegen 评分常量的完整移植

从 `K_TEST_ID_SCORE = 1` 到 `K_CSS_FALLBACK_SCORE = 10000000`，完整移植了 Playwright 官方 Codegen 的 `selectorGenerator.ts` 评分体系。这套分数体系是 Codegen 的核心竞争力，在 JS 端和 Python 端都有使用。

评分常量覆盖了 15+ 个选择器类型，包括精确匹配惩罚（`K_EXACT_PENALTY`）和长度惩罚区间（`K_BEGIN_PENALIZED_SCORE` ~ `K_END_PENALIZED_SCORE`），这些细节在开源社区的 Playwright 封装中很少见到。

#### 7.1.2 双路径架构

系统同时维护两条选择器生成路径：

| 路径 | 函数 | 适用场景 | 特点 |
|------|------|----------|------|
| 快速路径 | `_generate_semantic_selector` | 简单场景（button+name、testid） | if-elif 链，零 AI 开销 |
| 候选排序路径 | `_generate_semantic_selector_realtime` | 复杂场景 | 生成所有候选 → 评分排序 → AI 选择 |

快速路径处理 60-70% 的简单操作（按钮点击、链接跳转），候选排序路径处理剩余的复杂场景（表单填写、自定义组件）。这个分层减少了不必要的 AI 调用。

#### 7.1.3 三源数据融合

```
数据源 1: Playwright YAML 快照（accessibility tree）
    → _parse_all_elements() → _element_cache
    
数据源 2: 原始 HTML（DOMCleaner 传递）
    → _parse_label_for_associations() → _label_for_cache
    → _extract_html_attributes() → _html_element_attrs
    → _build_ref_to_html_mapping() → _ref_to_html_attrs
    
数据源 3: JS 注入检测结果
    → process_js_detection_result() → _js_detected_elements
    → _merge_js_detection_to_cache() → 补充到 _element_cache
    → _update_labels_from_js_detection() → 补充 implicit_label
```

三个数据源互补：快照提供 role/name/ref，HTML 提供 label[for]/data-testid/name，JS 提供 cursor:pointer/可见性/实时属性。这种融合策略是正确的。

#### 7.1.4 四层隐式标签提取

`_extract_implicit_label` 实现了四个策略：

1. 前一个兄弟元素（同缩进级别的前一行）
2. 同行前缀文本（`- text "Username" ... - textbox [ref=e12]`）
3. 父级元素文本（向上查找包含文本的父元素）
4. 附近关键字（在上下文中搜索 label 关键词）

这覆盖了 Element UI / Ant Design 等组件库的常见 label 模式，特别是 `el-form-item` 的 label 通常不是 `<label for>` 而是普通文本。

#### 7.1.5 element_hint 中文解析

`_parse_element_hint` 支持中文元素类型关键词：

```python
# 复选框 → checkbox, 下拉框 → combobox, 单选框 → radio, 按钮 → button, 链接 → link
```

对中文 Agent 场景（用户用中文描述"点击复选框"）很实用，能正确推断 `inferred_role` 并生成 `getByRole('checkbox', { name: '...' })`。


### 7.2 核心问题与修复方案

#### 问题 1：两套选择器生成逻辑并行，优先级不一致

**现状**：

`_generate_semantic_selector`（快速路径，~270 行 if-elif）和 `_generate_all_candidate_selectors`（候选路径，~250 行）做同一件事，但优先级不一致：

| 选择器类型 | 快速路径优先级 | 候选路径分数 | 矛盾 |
|-----------|---------------|-------------|------|
| CSS type（password/text） | 第 3 位（在 getByLabel 之前） | 520 分 | 快速路径更优先 |
| getByLabel | 第 4 位 | 140 分 | 候选路径更优先 |
| getByPlaceholder | 第 5 位 | 120 分 | 候选路径更优先 |

同一个 `input[type="password"]` 元素：
- 快速路径 → `page.locator('input[type="password"]').fill(...)` （CSS 选择器）
- 候选路径 → `page.getByLabel('密码').fill(...)` （语义化选择器，分数更低=更好）

**影响**：同一个元素在不同代码路径下生成不同的选择器，脚本质量不可预测。

**修复方案**：统一到候选路径，废弃 if-elif 快速路径

```python
def _generate_semantic_selector(self, element_info: dict, action: str, value: str = None) -> Optional[str]:
    """
    统一选择器生成入口（废弃 if-elif 链，改用候选排序）
    """
    # 1. 最高优先级：JS 推荐选择器（score < 200，高质量）
    js_best_selector = element_info.get('_js_best_selector')
    js_score = element_info.get('_js_score', 999999)
    if js_best_selector and js_score < 200:
        code = self._build_action_code(js_best_selector, action, value)
        if code:
            return code
    
    # 2. 生成所有候选并排序
    candidates = self._generate_all_candidate_selectors(element_info, action, value)
    if not candidates:
        return None
    
    # 3. 短路优化：最佳候选分数足够低时直接使用，不调用 AI
    best_selector, best_score = candidates[0]
    if best_score <= K_TEXT_SCORE:  # 分数 <= 180（getByText 及以上）
        return best_selector
    
    # 4. 分数较高时，尝试 AI 选择（仅复杂场景）
    # ... 保留现有 AI 选择逻辑 ...
    
    return best_selector  # 兜底返回规则最佳
```

**工作量**：中（1-2 天），需要确保所有调用 `_generate_semantic_selector` 的地方行为一致。

---

#### 问题 2：`_build_ref_to_html_mapping` 位置匹配不可靠

**现状**：当精确匹配（id、name、data-testid）都失败时，按索引位置匹配：

```python
# 当前代码
if i < len(html_elems):
    html_elem = html_elems[i]
    self._ref_to_html_attrs[ref] = html_elem
```

**影响**：accessibility tree 的遍历顺序和 DOM 顺序不一定相同（`tabindex`、`aria-owns`、Shadow DOM 等场景）。错误的映射会导致选择器指向错误的元素——比如把"用户名"输入框的 HTML 属性映射到"密码"输入框的 ref 上。

**修复方案**：位置匹配增加文本交叉验证

```python
# 4. 按索引位置匹配（兜底）+ 文本交叉验证
if i < len(html_elems):
    html_elem = html_elems[i]
    
    # 交叉验证：快照元素的文本/name 与 HTML 元素的文本/placeholder 是否匹配
    snapshot_text = (snapshot_elem.get('name') or snapshot_elem.get('text') or '').lower().strip()
    html_text = (html_elem.get('placeholder') or html_elem.get('_text') or '').lower().strip()
    
    # 至少有一个文本字段匹配，或者两者都为空（纯结构匹配）
    if (not snapshot_text and not html_text) or \
       (snapshot_text and html_text and (
           snapshot_text in html_text or html_text in snapshot_text
       )):
        self._ref_to_html_attrs[ref] = html_elem
        logs.debug(f"[SemanticSelector] 位置匹配+文本验证(ref={ref}): index={i}")
    else:
        logs.warning(f"[SemanticSelector] 位置匹配失败(ref={ref}): "
                     f"快照文本='{snapshot_text}' vs HTML文本='{html_text}'，跳过")
```

**工作量**：小（0.5 天）。

---

#### 问题 3：`_generate_all_candidate_selectors` 中仍有 `.first()` 回退

**现状**：候选路径中多处生成 `.first()` 选择器：

```python
# getByText 模糊匹配
candidates.append((f"await page.getByText('{safe_text}').first().click();", K_TEXT_SCORE))

# role 无 name
candidates.append((f"await page.getByRole('{role}').first().click();", K_ROLE_WITHOUT_NAME_SCORE))

# 通用文本框
candidates.append((f"await page.locator('input[type=\"text\"]').first().fill('{safe_value}');", K_CSS_INPUT_TYPE_NAME_SCORE + 2))
```

**影响**：`.first()` 在多元素页面几乎必定定位到错误元素。虽然不会触发 strict mode violation，但操作的是错误元素，脚本逻辑错误。

**修复方案**：用 TODO 注释 + 上下文信息替代 `.first()`

```python
# ❌ 当前
candidates.append((
    f"await page.getByText('{safe_text}').first().click();", 
    K_TEXT_SCORE
))

# ✅ 修复：不使用 .first()，改用 filter 或 TODO 标记
if role:
    # 方案1：用 role 缩小范围
    candidates.append((
        f"await page.getByRole('{role}').filter({{ hasText: '{safe_text}' }}).click();",
        K_TEXT_SCORE
    ))
else:
    # 方案2：标记为需要人工确认，但仍生成可运行代码
    candidates.append((
        f"await page.getByText('{safe_text}', {{ exact: true }}).click(); "
        f"// ⚠️ 可能匹配多个元素，建议手动确认",
        K_TEXT_SCORE + 100  # 加分惩罚
    ))
```

对于 `input[type="text"]` 等纯类型选择器，直接不生成：

```python
# ❌ 删除这类候选
# candidates.append((f"await page.locator('input[type=\"text\"]').first().fill(...)"))

# ✅ 替代：只在有额外限定条件时才生成
if html_attrs and html_attrs.get('name'):
    name = html_attrs['name']
    candidates.append((
        f"await page.locator('input[name=\"{name}\"]').fill('{safe_value}');",
        K_CSS_INPUT_TYPE_NAME_SCORE
    ))
```

**工作量**：小（0.5 天），逐个替换 `.first()` 调用点。

---

#### 问题 4：AI 选择环节的 token 浪费

**现状**：`_ai_select_best_selector` 每次操作都调用 LLM，即使最佳候选已经是高质量选择器（如 `getByTestId`，分数=1）。

**影响**：每次 AI 调用消耗 500-2000 tokens，一个包含 20 个操作的脚本额外消耗 10K-40K tokens。

**修复方案**：增加短路逻辑，高质量候选直接使用

```python
def _generate_semantic_selector_realtime(self, ref, action, value=None, ...):
    # ... 生成候选 ...
    
    if not candidates:
        return None
    
    best_selector, best_score = candidates[0][0], candidates[0][1]
    
    # 🚀 短路优化：高质量候选直接使用，不调用 AI
    # 分数 <= 200 意味着是 testid/role+name/placeholder/label/text 级别
    if best_score <= K_TITLE_SCORE:  # <= 200
        logs.info(f"[RealtimeSelector] ⚡ 短路：最佳候选分数={best_score}，直接使用")
        if not self._contains_ref_selector(best_selector):
            self._selector_stats['semantic'] += 1
            return best_selector
    
    # 分数 > 200 的复杂场景才调用 AI
    logs.info(f"[RealtimeSelector] 🤖 最佳候选分数={best_score}，调用 AI 选择...")
    ai_result = self._ai_select_best_selector(candidates, ...)
    # ...
```

**预期效果**：AI 调用减少 60-70%，token 消耗降低 15K-25K/脚本。

**工作量**：小（0.5 天）。

---

#### 问题 5：两套独立的评分体系

**现状**：

| 评分体系 | 使用位置 | 范围 | 用途 |
|----------|----------|------|------|
| Codegen 分数（K_* 常量） | `_generate_all_candidate_selectors` | 1 ~ 10000000 | 候选排序 |
| 质量分数 | `_evaluate_selector_quality` | 0.0 ~ 1.0 | 脚本质量评估 |

两套评分的排序不完全一致：

| 选择器 | Codegen 分数 | 质量分数 | 矛盾 |
|--------|-------------|----------|------|
| getByTestId | 1（最优） | 0.90 | Codegen 认为最优，质量评估认为次优 |
| getByRole+name | 100 | 0.95（最优） | 质量评估认为最优，Codegen 认为次优 |
| getByLabel | 140 | 0.85 | 排序一致 |

**修复方案**：统一为一套评分，`_evaluate_selector_quality` 基于 Codegen 分数归一化

```python
def _evaluate_selector_quality(self, selector: str) -> float:
    """
    评估选择器质量（0-1 分）
    基于 Codegen 分数体系归一化，确保与候选排序一致
    """
    # 检查无效选择器
    if '[ref=' in selector or any(p in selector for p in [':contains', ':eq(', ':first']):
        return 0.0
    
    # 识别选择器类型并映射到 Codegen 分数
    codegen_score = K_CSS_FALLBACK_SCORE  # 默认最差
    
    if 'getByTestId' in selector:
        codegen_score = K_TEST_ID_SCORE
    elif 'getByRole' in selector and 'name:' in selector:
        codegen_score = K_ROLE_WITH_NAME_SCORE
    elif 'getByPlaceholder' in selector:
        codegen_score = K_PLACEHOLDER_SCORE
    elif 'getByLabel' in selector:
        codegen_score = K_LABEL_SCORE
    elif 'getByText' in selector:
        codegen_score = K_TEXT_SCORE
    elif "type=\"password\"" in selector or "type='password'" in selector:
        codegen_score = K_CSS_INPUT_TYPE_NAME_SCORE
    elif '.first()' in selector or '.nth(' in selector:
        codegen_score = K_NTH_SCORE
    elif 'locator(' in selector:
        codegen_score = K_CSS_ID_SCORE  # 假设是 CSS 选择器
    
    # 归一化到 0-1（使用对数缩放，因为分数跨度很大）
    import math
    max_log = math.log(K_CSS_FALLBACK_SCORE + 1)  # log(10000001) ≈ 16.1
    score_log = math.log(codegen_score + 1)
    quality = 1.0 - (score_log / max_log)
    
    # 限制范围
    return max(0.0, min(1.0, round(quality, 3)))
```

归一化后的对应关系：

| 选择器 | Codegen 分数 | 归一化质量分 |
|--------|-------------|-------------|
| getByTestId | 1 | 0.957 |
| getByRole+name | 100 | 0.714 |
| getByPlaceholder | 120 | 0.703 |
| getByLabel | 140 | 0.693 |
| getByText | 180 | 0.677 |
| CSS ID | 500 | 0.614 |
| CSS name | 520 | 0.611 |
| .nth() | 10000 | 0.428 |
| .first() fallback | 10000000 | 0.000 |

**工作量**：小（0.5 天），只需修改 `_evaluate_selector_quality` 一个函数。


### 7.3 语义选择器改进优先级

| 优先级 | 改进项 | 涉及函数 | 预期收益 | 工作量 |
|--------|--------|----------|----------|--------|
| P0 | JS 端唯一性验证 | `JS_INTERACTIVE_DETECTOR` | strict mode violation 减少 60-80% | 中（1 天） |
| P0 | 消除 `.first()` 候选 | `_generate_all_candidate_selectors` | 错误定位减少，脚本可执行率提升 | 小（0.5 天） |
| P1 | 统一两套选择器生成逻辑 | `_generate_semantic_selector` | 消除优先级不一致，维护成本降低 | 中（1-2 天） |
| P1 | AI 选择短路优化 | `_generate_semantic_selector_realtime` | token 消耗降低 60-70% | 小（0.5 天） |
| P1 | 位置匹配增加文本验证 | `_build_ref_to_html_mapping` | 减少错误的 ref→HTML 映射 | 小（0.5 天） |
| P1 | JS/Python 评分常量统一 | `selector_scores.py`（新） | 消除双端评分冲突 | 小（0.5 天） |
| P2 | 统一两套评分体系 | `_evaluate_selector_quality` | 脚本质量评估与选择器排序一致 | 小（0.5 天） |
| P2 | `aria-labelledby` 解析 | `JS_INTERACTIVE_DETECTOR` | getByLabel 命中率提升 20-30% | 小（0.5 天） |
| P2 | cursor:pointer 遍历优化 | `JS_INTERACTIVE_DETECTOR` | JS 注入执行时间减少 80% | 小（0.5 天） |
| P2 | JS 注入自动触发 | `awrap_tool_call` | JS 检测覆盖率提升到 100% | 中（1-2 天） |

### 7.4 推荐实施路线

```
第一阶段（2 天）：消除硬伤
├── 消除 .first() 候选（0.5 天）
├── JS 端唯一性验证（1 天）
└── AI 选择短路优化（0.5 天）

第二阶段（3 天）：统一架构
├── 统一两套选择器生成逻辑（1.5 天）
├── JS/Python 评分常量统一（0.5 天）
├── 位置匹配增加文本验证（0.5 天）
└── 统一两套评分体系（0.5 天）

第三阶段（2 天）：增强能力
├── aria-labelledby 解析（0.5 天）
├── cursor:pointer 遍历优化（0.5 天）
└── JS 注入自动触发（1 天）
```

预计总工作量：7 天。完成后语义选择器模块的代码量可从 4600+ 行精简到 3500-4000 行（废弃 if-elif 快速路径后），同时选择器质量和一致性显著提升。

---

## 八、更新后的完整优先级排序

综合第四章原有改进项和第六、七章新增改进项：

| 优先级 | 改进项 | 类别 | 工作量 | 预期收益 |
|--------|--------|------|--------|----------|
| P0 | 🔥 重复行截断 | DOM 快照 | 中（1-2 天） | 快照大小降低 90%+ |
| P0 | JS 端唯一性验证 | JS 注入 | 中（1 天） | strict mode violation 减少 60-80% |
| P0 | 消除 `.first()` 回退（含候选路径） | 选择器生成 | 小（0.5 天） | 错误定位大幅减少 |
| P0 | 一次性 JS 批量属性提取 | JS 注入 | 中（1-2 天） | 选择器质量大幅提升 |
| P1 | 自动插入等待逻辑 | 代码生成 | 小（0.5 天） | 超时错误减少 75% |
| P1 | 统一两套选择器生成逻辑 | 选择器生成 | 中（1-2 天） | 消除优先级不一致 |
| P1 | AI 选择短路优化 | 选择器生成 | 小（0.5 天） | token 消耗降低 60-70% |
| P1 | JS/Python 评分常量统一 | JS 注入 | 小（0.5 天） | 消除双端评分冲突 |
| P1 | 位置匹配增加文本验证 | 选择器生成 | 小（0.5 天） | 减少错误映射 |
| P1 | 选择器生成后立即验证 | 选择器生成 | 中（1 天） | 减少无效脚本 |
| P1 | 新脚本冷启动惩罚 | 质量评估 | 小（0.5 天） | 评分准确性提升 |
| P2 | 统一两套评分体系 | 选择器生成 | 小（0.5 天） | 评估与排序一致 |
| P2 | `aria-labelledby` 解析 | JS 注入 | 小（0.5 天） | getByLabel 命中率提升 |
| P2 | cursor:pointer 遍历优化 | JS 注入 | 小（0.5 天） | JS 执行时间减少 80% |
| P2 | JS 注入自动触发 | JS 注入 | 中（1-2 天） | JS 检测覆盖率 100% |
| P2 | 快照分级清理 | DOM 快照 | 中（1-2 天） | 大页面信息保留度提升 |
| P2 | 操作序列模式识别 + 断言生成 | 代码生成 | 大（3-5 天） | 代码可读性提升 |
| P3 | LRU 缓存限制 | 性能 | 小（0.5 天） | 内存优化 |
| P3 | 文本变体策略增强 | 选择器生成 | 小（0.5 天） | 边缘场景提升 |

---

## 九、总结

整套系统的架构设计扎实，中间件分层、Codegen 评分体系移植、多策略回退、JS 注入增强（v8）、三源数据融合都体现了深入的工程实践。

语义选择器算法体系的核心价值在于：将 Playwright Codegen 的评分思想从"录制时生成"迁移到了"Agent 运行时生成"，这是一个有意义的创新。四层隐式标签提取、element_hint 中文解析、JS 端选择器候选生成，这些在国内 AI Agent + Playwright 项目中属于较深的工程实践。

当前的主要改进方向是**收敛**：
1. 两套选择器生成逻辑（if-elif vs 候选排序）→ 统一到候选排序
2. 两套评分体系（Codegen 分数 vs 质量分数）→ 统一到 Codegen 分数归一化
3. JS 注入从被动触发 → 自动触发
4. JS 端增加唯一性验证 → 从源头消除 strict mode violation

系统的能力已经够了，问题在于同一个功能有多条路径，增加了不一致性和维护成本。收敛后代码量可减少 15-20%，同时选择器质量和一致性显著提升。
