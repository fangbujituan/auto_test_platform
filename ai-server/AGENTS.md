# 项目概览

## 项目类型
这是一个基于 LangGraph 的 AI 智能体系统，用于构建和部署可配置的 AI Agent。项目支持浏览器自动化、数据可视化、网页搜索、操作录制回放、Token 用量追踪等多种功能。

## 核心技术栈
- **LangGraph**: 用于构建状态机驱动的 AI Agent 工作流
- **LangChain**: 提供 LLM 集成和工具管理能力
- **多模型网关**: 支持 AIOP Gateway（Azure/OpenAI/Gemini）、Kiro Gateway（Claude/DeepSeek）、AIClient2API（Claude/Gemini/Qwen/Grok）
- **MCP (Model Context Protocol)**: 用于集成外部工具和服务
- **FastAPI/Uvicorn**: API 服务器
- **BeautifulSoup4**: HTML 解析和 DOM 清理
- **Playwright**: 浏览器自动化和测试脚本执行
- **Loguru**: 日志记录
- **SQLite**: Token 用量统计数据库（`data/token_stats.db`）

## 项目架构
项目采用模块化设计，主要包含以下核心组件：

### 核心文件说明

- **main.py**: Agent 入口文件
  - `agent`: 主 Agent，使用 `make_agent` 工厂函数创建，集成 Playwright + Chart 工具
  - `web_agent`: Web 搜索 Agent，集成 Chrome DevTools MCP 工具
  - `recording_agent`: 录制回放 Agent，支持操作录制和脚本回放

- **llms.py**: LLM 模型配置（多网关路由）
  - 支持三种网关：AIOP Gateway、Kiro Gateway、AIClient2API
  - `get_default_model()`: 获取默认模型（由 `DEFAULT_MODEL` 环境变量控制）
  - `get_aiop_model()`: AIOP 企业网关（Azure GPT / OpenAI / Gemini）
  - `get_kiro_model()`: Kiro 本地网关（Claude / DeepSeek / Qwen）
  - `get_aiclient_model()`: AIClient2API 多模型网关（Claude via Kiro OAuth / Gemini / Qwen / Grok）
  - `get_model()`: 统一路由函数，格式 `gateway/provider/model`
  - `LLMLogger`: LLM 调用日志回调
  - 内置 `TokenCallbackHandler` 自动记录 Token 用量

- **start_server.py**: LangGraph API 服务器启动脚本
  - 配置内存数据库和模拟 Redis
  - 启动 LangGraph Studio UI
  - 提供 API 文档和健康检查端点

- **graph.json**: Agent 配置文件
  - 定义可用的 Agent（agent, web_agent, recording_agent）及其路径
  - 配置环境变量（.env）

- **tools/**: 工具模块目录（模块化结构）
  - `web_demo.py`: Web 演示工具
  - `core/`: 核心架构
    - `agent_factory.py`: Agent 工厂函数 `make_agent()`
  - `middleware/`: 中间件
    - `dom_cleaner.py`: DOM 清理中间件
    - `logging.py`: 日志记录中间件
    - `code_collector.py`: 代码收集中间件（支持 element_hint 参数）
    - `base64_filter.py`: Base64 过滤中间件
    - `semantic_selector.py`: 语义选择器中间件（支持 element_hint 参数）
    - `token_control.py`: Token 控制中间件
    - `selector_scores.py`: **选择器评分常量**（Codegen 风格，JS/Python 共享评分体系）
  - `mcp/`: MCP 客户端工具
    - `clients.py`: MCP 客户端工具函数
  - `playwright/`: Playwright 自动化
    - `agent.py`: UI 自动化 Agent
    - `recording_agent.py`: 录制回放 Agent
    - `executor.py`: Playwright 脚本执行工具
    - `report.py`: 测试结果解析工具
    - `script_generator.py`: 脚本生成工具
    - `script_manager.py`: 脚本管理器
    - `script_index.py`: 脚本索引管理器
    - `bnp_auth_tool.py`: BNP 登录态管理工具
    - `config.py`: 配置类 `UIAutomationConfig`
    - `prompts.py`: 系统提示词
    - `recorder/`: **Codegen 录制模块**
      - `recorder-server.js`: Node.js 录制服务（使用内部 API _enableRecorder）
      - `recorder_client.py`: Python 客户端
      - `codegen_tools.py`: LangChain 工具（供 Agent 调用）
  - `utils/`: 工具函数
    - `dom_utils.py`: DOM 清理工具函数
    - `token_counter.py`: **Token 用量统计**（SQLite 持久化，单例模式，支持用例级追踪）
    - `dashboard.py`: **Token Dashboard API**（用例管理、趋势分析、费用估算）
    - `case_tools.py`: **用例管理工具**（供 Agent 调用的 LangChain 工具集）
  - `examples/`: 示例工具
    - `weather.py`: 天气查询工具
  - `debug/`: 调试工具
    - `readlog.py`: 日志读取工具

- **playwright_scripts/**: TypeScript 测试脚本目录
  - `package.json`: npm 依赖配置
  - `playwright.config.ts`: Playwright 配置文件
  - `bnp_login.spec.ts`: BNP 登录脚本
  - `tests/`: 测试脚本存放目录
    - `add_billing_item*.spec.ts`: 添加 Billing Item 测试脚本系列
  - `recordings/`: 脚本元数据和索引目录
    - `index.json`: 全局脚本索引
    - `.trash/`: 回收站目录
  - `auth_state/`: 登录态保存目录
  - `test-results/`: Playwright 测试结果目录

- **docs/**: 文档目录
  - `middleware-guide.md`: Middleware 开发指南
  - `token-dashboard-api.md`: Token Dashboard API 文档
  - `kiro-gateway-deployment.md`: Kiro Gateway 部署指南
  - `jquery-syntax-fix.md`: jQuery 语法修复说明
  - `UI 智能体介绍.md`: UI 智能体功能介绍
  - `测试用例示例.md`: 测试用例示例文档
  - `coding/`: **Codegen Pipeline 优化任务文档**
    - `codegen-pipeline-assessment.md`: Codegen 管线整体评估
    - `P0-*.md`: 最高优先级任务（重复行截断、JS 唯一性验证、消除首次回退、自动 JS 批量注入）
    - `P1-*.md`: 高优先级任务（自动等待逻辑、统一选择器生成、AI 短路、分数统一、位置匹配验证、冷启动惩罚）
    - `P2-*.md`: 中优先级任务（统一评分系统、aria-labelledby 解析、cursor-pointer 优化、快照分层清理、模式识别断言）
    - `P3-*.md`: 低优先级任务（LRU 缓存限制、相似脚本检测、文本变体增强）

- **shell/**: 辅助脚本目录
  - `kill-2025-simple.bat`: 简化版终止端口 2025 进程脚本
  - `init_script_index.py`: 脚本索引初始化工具，用于部署时初始化脚本库
  - `run_ts.py`: **Playwright 测试运行器**（支持有头/无头模式、登录态、超时配置）
  - `refresh_auth.py`: **BNP 登录态刷新脚本**（检查有效性、自动重新登录）
  - `check_middleware.py`: 中间件属性检查工具
  - `kiro_cleaner.py`: **Kiro IDE 清理工具**（缓存/日志/认证清理，支持基础/深度/完全三种模式）
  - `kiro-gateway-manager.bat`: Kiro Gateway 管理脚本
  - `start-kiro-gateway.bat`: Kiro Gateway 启动脚本
  - `test_auth_loading.py`: 登录态加载测试
  - `test_bnp_auth.py`: BNP 认证测试
  - `test_login.py`: 登录流程测试

- **data/**: 数据目录
  - `token_stats.db`: Token 用量统计 SQLite 数据库

- **logs/**: 日志目录（git-ignored）
- **base64_images/**: Base64 图片保存目录
- **playwright_reports/**: 测试报告目录
- **playwright_results/**: 测试结果 JSON 目录

## 构建和运行

### 环境准备
```bash
# 创建虚拟环境（如果尚未创建）
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 环境变量配置
```bash
# 复制环境变量示例文件
copy .env.example .env

# 编辑 .env 文件，填写实际的 API 密钥
```

#### 核心环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DEFAULT_MODEL` | 默认模型（格式: `gateway/provider/model`） | `aiop/azure/gpt-5.4` |
| `AIOP_BASE_URL` | AIOP Gateway 端点 | `https://aiop-gateway.item.com/openai/v1` |
| `AIOP_API_KEY` | AIOP Gateway API 密钥（支持 JWT Token） | - |
| `AIOP_APP_CODE` | AIOP 应用编码（非 JWT 方式必填） | - |
| `KIRO_BASE_URL` | Kiro Gateway 端点 | `http://localhost:9000/v1` |
| `KIRO_API_KEY` | Kiro Gateway API 密钥 | - |
| `AICLIENT_BASE_URL` | AIClient2API 端点 | `http://localhost:9000` |
| `AICLIENT_API_KEY` | AIClient2API API 密钥 | `sk-test` |
| `ZHIPU_API_KEY` | 智谱 AI API 密钥（搜索 MCP） | - |
| `TVLY_API_KEY` | Tavily 搜索 API 密钥 | - |
| `DATABASE_URI` | 数据库连接字符串 | `:memory:` |
| `REDIS_URI` | Redis 连接字符串 | `fake` |
| `LANGGRAPH_API_URL` | LangGraph API 地址 | `http://localhost:2025` |
| `LANGGRAPH_DEFAULT_RECURSION_LIMIT` | 递归限制 | `200` |
| `UI_WORKSPACE_ROOT` | 工作空间根目录 | - |
| `PLAYWRIGHT_AUTH_STATE` | Playwright 登录态文件路径 | - |

#### 模型路由格式

```
gateway/provider/model
```

| 网关 | 示例 | 说明 |
|------|------|------|
| `aiop` | `aiop/azure/gpt-5.4` | AIOP 企业网关 |
| `kiro` | `kiro/claude-sonnet-4.5` | Kiro 本地网关 |
| `aiclient` | `aiclient/claude-kiro-oauth/claude-sonnet-4-6` | AIClient2API 多模型网关 |

### 启动服务器
```bash
python start_server.py
```

服务器将在以下地址启动：
- **API Server**: http://localhost:2025
- **API 文档**: http://localhost:2025/docs
- **Studio UI**: http://localhost:2025/ui
- **健康检查**: http://localhost:2025/ok

### 终止服务器
```bash
# 使用批处理脚本
shell\kill-2025-simple.bat
```

### 运行测试脚本
```bash
# 使用测试运行器（推荐）
python shell\run_ts.py

# 或修改 run_ts.py 中的参数后运行
# SCRIPT_NAME: 脚本文件名
# AUTH_STATE: 登录态文件路径
# HEADED: 是否显示浏览器（True/False）
# TEST_TIMEOUT: 测试超时时间（毫秒）
```

### 登录态管理
```bash
# 检查登录态
python shell\refresh_auth.py --check

# 自动刷新（检查 + 按需重新登录）
python shell\refresh_auth.py

# 强制重新登录
python shell\refresh_auth.py --force
```

### Kiro IDE 清理
```bash
# 基础清理（缓存、日志）
python shell\kiro_cleaner.py

# 深度清理（含认证数据，用于账户切换）
python shell\kiro_cleaner.py --deep

# 完全重置（恢复初始状态）
python shell\kiro_cleaner.py --full

# 自动确认（跳过交互提示）
python shell\kiro_cleaner.py -y
```

### 初始化脚本库（部署时）
```bash
# 重建索引（保留回收站）
python shell\init_script_index.py

# 完全清理 + 重建索引
python shell\init_script_index.py --clean-all
```

### 使用 Agent
启动服务器后，可以通过以下方式与 Agent 交互：

1. **通过 Studio UI**: 访问 http://localhost:2025/ui
2. **通过 API**: 使用 REST API 调用 Agent
3. **通过 LangGraph CLI**: 使用 `langgraph` 命令行工具

## 开发约定

### 代码风格
- 所有 Python 文件使用 UTF-8 编码
- 遵循 PEP 8 代码规范

### Agent 定义
- Agent 使用 `make_agent()` 工厂函数或 `create_agent()` 创建
- 每个 Agent 需要指定 model、tools 和 system_prompt
- Agent 定义在 `main.py` 中，并在 `graph.json` 中注册
- 使用 `asynccontextmanager` 管理 MCP session，确保资源正确释放

### 工具集成
- 工具函数定义在 `tools/` 目录中
- MCP 工具通过 `MultiServerMCPClient` 集成
- 支持的传输方式：stdio, sse, streamable_http

### Token 用量追踪系统

项目内置完整的 Token 用量追踪系统（v2 重构，以 `thread_id` 为核心维度）：

1. **TokenCounter v2**（`tools/utils/token_counter.py`）：
   - 单例模式，SQLite 持久化存储（`data/token_stats.db`）
   - **v2 核心**：以 LangGraph `thread_id` 为主维度，自动关联 token 消耗
   - 3 张新表：`threads`（会话主表）、`token_records`（LLM 调用明细）、`thread_events`（事件日志）
   - 会话生命周期：active → completed / failed / interrupted
   - 软删除机制：删除后统计数据保留
   - 费用估算：支持 aiop/kiro/aiclient 三网关费率
   - 中断检测：超时会话自动标记为 interrupted
   - 向后兼容：保留 v1 旧表（`token_usage`、`case_usage`），双写机制

2. **TokenCallbackHandler v2**：
   - LangChain 回调处理器，自动挂载到所有模型调用
   - `on_llm_start`：记录开始时间，计算 `latency_ms`
   - `on_llm_end`：记录 token 消耗 + 延迟
   - `on_llm_error`：捕获错误，记录到 `token_records` + `thread_events`

3. **ThreadContextMiddleware**（`tools/middleware/thread_context.py`）：
   - 从 LangGraph runtime 自动提取 `thread_id` 注入 ContextVar
   - 零侵入：不修改 Agent 代码，纯中间件注入
   - 同时设置 `agent_name`

4. **Dashboard API v2**（`tools/utils/dashboard.py`）：
   - v1 路由（`/token-stats/*`）：保留兼容
   - v2 路由（`/api/v1/token-stats/*`）：以 thread_id 为核心
   - 会话 CRUD + 软删除/恢复
   - 全局概览、趋势、费用、明细记录
   - 数据迁移接口（v1→v2）

5. **用例管理工具**（`tools/utils/case_tools.py`，v1 兼容）：
   - `case_create`: 创建测试用例，后续 token 自动关联
   - `case_get_stats`: 获取用例当前统计
   - `case_complete`: 完成用例并返回最终统计
   - `case_rename`: 重命名用例
   - `case_list`: 获取历史用例列表

### 中间件机制
项目实现了多层中间件机制：

0. **Thread Context 中间件**（`thread_context.py`）：
   - 从 LangGraph runtime 提取 `thread_id` 注入 ContextVar
   - 同时设置 `agent_name`
   - 放在中间件列表最前面，确保后续所有操作都能获取 thread_id

1. **DOM 清理中间件**（`dom_cleaner.py`）：
   - 自动清理 Playwright 返回的 DOM 数据
   - 移除 `<script>`, `<style>`, `<link>`, `<meta>` 等标签
   - 移除 `class`, `style`, 事件属性等无用属性
   - 保留 `id`, `name`, `type`, `aria-*`, `data-*` 等关键属性
   - 可减少 10-90% 的 token 消耗

2. **代码收集中间件**（`code_collector.py`）：
   - 拦截 Playwright MCP 工具调用
   - 从工具调用参数提取并生成 TypeScript 代码
   - 支持保存为可复用的测试脚本
   - **element_hint 参数**：传递元素描述给语义选择器，提高按钮选择器准确性

3. **Base64 图片过滤中间件**（`base64_filter.py`）：
   - 将截图的 base64 数据保存到本地 `base64_images/` 目录
   - 替换消息中的 base64 为文件路径
   - 显著减少 token 消耗

4. **语义选择器中间件**（`semantic_selector.py`）：
   - 从页面快照中提取元素的语义信息（role, name, text 等）
   - 智能恢复机制：当 ref 失效时，自动在快照中搜索相似元素并重试
   - 为 CodeCollectorMiddleware 提供语义信息，生成稳定的语义化选择器
   - 支持模糊匹配和相似度评分
   - **element_hint 参数**：当快照缺少 name/text 时，使用外部传入的元素描述生成选择器
   - **Codegen 分数体系**：分数越低越好（1=最优，10000000=最差）

5. **Token 控制中间件**（`token_control.py`，替代 SummarizationMiddleware）：
   - 使用 `Overwrite` 直接替换 messages，避免发送 remove 消息（解决 LangGraph Studio UI 报错问题）
   - 滑动窗口机制：保留最近 N 条完整消息
   - 智能摘要：对旧消息生成摘要，保留关键信息（意图、操作、上下文）
   - 触发阈值：100K tokens（DeepSeek 128K 的约 78%）
   - 保留消息数：50 条

6. **选择器评分常量**（`selector_scores.py`）：
   - 移植自 Playwright `selectorGenerator.ts` 的评分体系
   - JS 端和 Python 端共享同一套评分标准
   - 分数越低 = 选择器质量越高
   - 关键分数：`TEST_ID=1`（最优）→ `ROLE_WITH_NAME=100` → `TEXT=180` → `CSS_ID=500` → `NTH=10000` → `CSS_FALLBACK=10000000`（最差）
   - 导出为 dict（`SELECTOR_SCORES`）供 JS 端注入使用

### Playwright 选择器语法

#### 元素定位优先级（必须严格遵守）

| 优先级 | 定位方式 | 示例 | 说明 |
|--------|----------|------|------|
| 1️⃣ | `getByRole()` | `getByRole('button', {name: 'Submit'})` | 语义化，最稳定 |
| 2️⃣ | `getByLabel()` | `getByLabel('Username')` | 关联 label 的表单元素 |
| 3️⃣ | `getByPlaceholder()` | `getByPlaceholder('Enter email')` | 输入框 placeholder |
| 4️⃣ | `getByText()` | `getByText('Sign in')` | 文本内容匹配 |
| 5️⃣ | `getByTestId()` | `getByTestId('submit-btn')` | data-testid 属性 |
| 6️⃣ | CSS 属性选择器 | `[name="username"]` | name/id/data-* 属性 |
| 7️⃣ | CSS ID 选择器 | `#submit-btn` | 唯一 ID（如果稳定）|
| 8️⃣ | **JavaScript 执行** | `page.evaluate(() => ...)` | **终极备用方案** |

#### 支持的语法
- ✅ 文本选择器：`text="Username"` 或 `getByRole('button', {name: 'Username'})`
- ✅ Playwright 文本定位：`getByText("Username")`
- ✅ 标准 CSS 选择器：`label[for="inputUserName"]`
- ✅ 属性选择器：`[data-testid="username"]`

#### 不支持的语法
- ❌ jQuery 语法（如 `:contains("Username")`）
- ❌ jQuery 伪类选择器
- ❌ 临时引用选择器 `(ref=e123)`
- ❌ 动态索引定位 `.nth(3)`

#### 分页/数字精确匹配（重要）
当点击分页按钮或数字元素时，必须使用精确匹配：

```typescript
// ❌ 错误：getByText('2') 会匹配 "2", "22", "20/page"
await page.getByText('2').click();

// ✅ 正确：使用正则精确匹配
await page.getByText(/^2$/).click();

// ✅ 更好：使用 aria-label
await page.locator('[aria-label="page 2"]').click();
```

#### JavaScript 执行备用方案
当所有选择器都无效时，使用 JavaScript 执行：
```typescript
// 点击被遮挡的元素
await page.evaluate(() => {
  document.querySelector('button[type="submit"]').click();
});

// 修改输入框值（绕过 React/Vue 的双向绑定）
await page.evaluate(() => {
  const input = document.querySelector('input[name="email"]');
  input.value = 'test@example.com';
  input.dispatchEvent(new Event('input', { bubbles: true }));
});
```

### 两种浏览器模式

| 模式 | 工具 | 登录态支持 | 适用场景 |
|------|------|------------|----------|
| **实时浏览器** | `browser_navigate`, `browser_click` 等 MCP 工具 | ❌ 不支持 | 无需登录的页面、一次性操作 |
| **脚本执行** | `run_playwright_script` | ✅ 支持 auth_state | 需要登录态、可回放脚本 |

**关键点：**
- Playwright MCP 工具（browser_xxx）和 run_playwright_script 是**两个独立的浏览器会话**
- 登录态（auth_state）**只在 run_playwright_script 中生效**
- **不能混用**：如果需要登录态，必须创建完整脚本并用 run_playwright_script 执行

## Agent 功能说明

### agent（主 Agent）
- **功能**：浏览器自动化和数据可视化
- **工具**：Playwright MCP + AntV Chart MCP
- **特点**：
  - 支持 DOM 清理，减少 token 消耗
  - 支持对话历史总结
  - 适用于复杂的网页交互和数据可视化任务

### web_agent
- **功能**：Web 搜索
- **工具**：Chrome DevTools MCP
- **特点**：
  - 简单的搜索 Agent
  - 适用于基本的网页搜索和信息获取

### recording_agent（录制回放 Agent）
- **功能**：浏览器操作录制和脚本回放
- **工具**：Playwright MCP + Chart MCP + 录制回放工具 + 用例管理工具
- **中间件栈**（按执行顺序）：
  - `CodeCollectorMiddleware`: 从工具调用参数生成 TypeScript 代码
  - `SemanticSelectorMiddleware`: 从快照提取语义信息，生成稳定选择器
  - `DOMCleanerMiddleware`: 清除多余 DOM 元素
  - `TokenControlMiddleware`: 滑动窗口 + 智能摘要控制 token
  - `Base64FilterMiddleware`: 截图保存到本地，替换为文件路径
- **特点**：
  - **element_hint 增强**：使用元素描述生成更准确的选择器
  - **脚本保存/执行**：save_current_recording, run_playwright_script
  - **结果解析**：parse_test_results 解析测试结果
  - **脚本索引**：ScriptIndexManager 管理脚本质量评估和自动清理
  - **BNP 登录态管理**：bnp_check_auth, bnp_login, bnp_list_auth_states
  - **用例管理**：case_create, case_get_stats, case_complete, case_rename, case_list
- **适用场景**：
  - 需要重复执行的测试任务
  - 需要登录态的操作
  - 需要生成可复用脚本
  - 需要追踪 token 消耗的任务

## MCP 工具集成

项目集成了以下 MCP 工具：

| 工具 | 传输方式 | 用途 |
|------|----------|------|
| `@playwright/mcp` | stdio | 浏览器自动化 |
| `@antv/mcp-server-chart` | stdio | 数据可视化图表 |
| Chrome DevTools MCP | stdio | Chrome 开发者工具 |
| 智谱搜索 | sse | Web 搜索 |
| Tavily 搜索 | streamable_http | Web 搜索 |

## 录制回放功能

### 工作流程

#### 需要登录态的任务流程（推荐）
1. **检查登录态**：调用 `bnp_check_auth` 检查 `playwright_scripts/auth_state/bnp_auth.json`
   - 文件不存在 → 调用 `bnp_login` 登录并保存
   - 文件存在但已过期 → 调用 `bnp_login` 重新登录
   - 文件存在且有效 → 直接使用
2. **执行脚本**：调用 `run_playwright_script` 并设置 `auth_state="playwright_scripts/auth_state/bnp_auth.json"`
3. **保存脚本**：操作完成后，调用 `save_current_recording` 保存脚本供下次复用

#### 无需登录的任务流程
直接使用 Playwright MCP 工具操作即可。

### 可用工具

#### 脚本操作
- `check_script`: 检查是否有匹配的录制脚本
- `save_current_recording`: 保存当前录制的脚本（含质量评估）
- `list_scripts`: 列出所有已保存的脚本（含质量分数）
- `delete_script`: 删除已保存的脚本
- `reset_recording`: 重置当前录制
- `get_current_code`: 获取当前录制的代码
- `create_script_with_auth`: 创建带登录态的 Playwright 脚本

#### 脚本索引管理
- `init_script_library`: 初始化脚本库（重建索引 + 清理过期文件 + 自动清理）
- `rebuild_index`: 重建脚本索引
- `list_low_quality_scripts`: 列出低质量脚本
- `cleanup_scripts`: 清理脚本（支持回收站、恢复、自动清理）

#### 脚本执行
- `run_playwright_script`: 执行 Playwright 测试脚本
- `parse_test_results`: 解析测试结果

#### 登录态管理
- `bnp_check_auth`: 检查 BNP 登录态是否有效
- `bnp_login`: 执行 BNP 登录并保存登录态
- `bnp_list_auth_states`: 列出已保存的登录态

#### 用例管理
- `case_create`: 创建测试用例（自动关联后续 token 消耗）
- `case_get_stats`: 获取用例当前统计信息
- `case_complete`: 完成用例并返回最终统计
- `case_rename`: 重命名用例
- `case_list`: 获取历史用例列表

### Codegen 录制模块

集成 Playwright 官方 Codegen 录制功能，生成高质量的语义化选择器代码。

#### 使用方式

```python
# 方式一：直接使用客户端
from tools.playwright.recorder import CodegenRecorder

async with CodegenRecorder() as recorder:
    await recorder.start(url="https://example.com")
    await recorder.click("button")
    code = await recorder.get_codegen_code()

# 方式二：通过 Agent 工具
# Agent 可以调用 codegen_start, codegen_click 等工具
```

#### 可用工具
- `codegen_start`: 启动 Codegen 录制会话
- `codegen_click`: 点击元素（自动录制）
- `codegen_fill`: 填充输入框（自动录制）
- `codegen_navigate`: 导航到 URL
- `codegen_get_code`: 获取生成的代码
- `codegen_save_script`: 保存到脚本库
- `codegen_stop`: 停止录制会话
- `codegen_screenshot`: 截图

#### 技术说明
- Python Playwright 没有暴露 `_enableRecorder` 内部 API
- 需要通过 Node.js 调用 TypeScript 内部 API
- 录制服务通过 WebSocket 通信

### 脚本索引系统

#### 功能特点
- **质量评估**：自动评估脚本质量分数（0-1）
  - 成功率（40%）
  - 语义化选择器比例（30%）
  - 代码完整性（20%）
  - 使用频率（10%）
- **定期自动清理**：每 10 次操作后自动清理低质量脚本
- **回收站机制**：删除的脚本移入回收站，7 天后自动清理
- **相似脚本检测**：识别功能相似的脚本，保留最优版本

#### 索引结构
```json
{
  "version": "1.0",
  "updated_at": "2026-03-17T10:00:00",
  "scripts": [
    {
      "name": "billing_items_add",
      "description": "添加 Billing Item",
      "keywords": ["billing", "add"],
      "url_patterns": ["https://bnp-test.item.pub/**"],
      "usage_count": 5,
      "success_rate": 0.85,
      "quality_score": 0.8,
      "has_code": true,
      "ref_count": 2,
      "semantic_count": 8
    }
  ]
}
```

#### 使用建议
1. **服务器启动后**：调用 `init_script_library` 初始化脚本库
2. **脚本变更后**：调用 `rebuild_index` 重建索引
3. **定期维护**：调用 `cleanup_scripts(action='auto')` 自动清理
4. **查看状态**：调用 `list_scripts` 查看脚本质量分数

## Codegen Pipeline 优化

`docs/coding/` 目录包含 Codegen 管线的系统性优化任务，按优先级分为四个等级：

| 优先级 | 任务数 | 关注领域 |
|--------|--------|----------|
| P0（紧急） | 4 | 重复行截断、JS 唯一性验证、消除首次回退、自动 JS 批量注入 |
| P1（高） | 6 | 自动等待逻辑、统一选择器生成、AI 短路、JS/Python 分数统一、位置匹配验证、冷启动惩罚 |
| P2（中） | 5 | 统一评分系统、aria-labelledby 解析、cursor-pointer 优化、快照分层清理、模式识别断言 |
| P3（低） | 3 | LRU 缓存限制、相似脚本检测、文本变体增强 |

详见 `docs/coding/codegen-pipeline-assessment.md` 获取整体评估。

## 中间件开发

详见 `docs/middleware-guide.md`，包含：
- SubAgent 与 Middleware 层级关系
- AgentMiddleware 基类使用方法
- DOM 清理中间件实现细节
- 代码收集中间件实现细节
- Base64 过滤中间件实现细节
- 语义选择器中间件实现细节
- Token 控制中间件实现细节
- 问题诊断流程

## 项目结构
```
├───main.py                      # Agent 入口
├───llms.py                      # LLM 模型配置（多网关路由）
├───start_server.py              # 服务器启动脚本
├───graph.json                   # Agent 配置文件
├───requirements.txt             # Python 依赖
├───Readme.md                    # 项目说明
├───.env                         # 环境变量配置
├───.env.example                 # 环境变量示例
├───tools/                       # 工具模块
│   ├───__init__.py              # 统一导出
│   ├───web_demo.py              # Web 演示工具
│   ├───core/                    # 核心架构
│   │   ├───__init__.py
│   │   └───agent_factory.py     # Agent 工厂
│   ├───middleware/              # 中间件
│   │   ├───__init__.py
│   │   ├───dom_cleaner.py       # DOM 清理中间件
│   │   ├───logging.py           # 日志记录中间件
│   │   ├───code_collector.py    # 代码收集中间件
│   │   ├───base64_filter.py     # Base64 过滤中间件
│   │   ├───semantic_selector.py # 语义选择器中间件
│   │   ├───token_control.py     # Token 控制中间件
│   │   └───selector_scores.py   # 选择器评分常量
│   ├───mcp/                     # MCP 客户端
│   │   ├───__init__.py
│   │   └───clients.py           # MCP 工具函数
│   ├───playwright/              # Playwright 自动化
│   │   ├───__init__.py
│   │   ├───agent.py             # UI 自动化 Agent
│   │   ├───recording_agent.py   # 录制回放 Agent
│   │   ├───executor.py          # 脚本执行工具
│   │   ├───report.py            # 结果解析工具
│   │   ├───script_generator.py  # 脚本生成工具
│   │   ├───script_manager.py    # 脚本管理器
│   │   ├───script_index.py      # 脚本索引管理器
│   │   ├───bnp_auth_tool.py     # BNP 登录态管理
│   │   ├───config.py            # 配置类
│   │   ├───prompts.py           # 系统提示词
│   │   └───recorder/            # Codegen 录制模块
│   │       ├───__init__.py
│   │       ├───codegen_tools.py
│   │       ├───recorder_client.py
│   │       └───recorder-server.js
│   ├───utils/                   # 工具函数
│   │   ├───__init__.py
│   │   ├───dom_utils.py         # DOM 清理工具
│   │   ├───token_counter.py     # Token 用量统计
│   │   ├───dashboard.py         # Token Dashboard API
│   │   └───case_tools.py        # 用例管理工具
│   ├───examples/                # 示例工具
│   │   ├───__init__.py
│   │   └───weather.py           # 天气工具
│   └───debug/                   # 调试工具
│       ├───__init__.py
│       └───readlog.py           # 日志读取工具
├───playwright_scripts/          # TypeScript 测试脚本
│   ├───package.json             # npm 依赖
│   ├───playwright.config.ts     # Playwright 配置
│   ├───bnp_login.spec.ts        # BNP 登录脚本
│   ├───tests/                   # 测试脚本目录
│   │   └───add_billing_item*.spec.ts
│   ├───recordings/              # 脚本元数据和索引
│   │   ├───index.json           # 全局脚本索引
│   │   └───.trash/              # 回收站目录
│   ├───auth_state/              # 登录态保存
│   └───test-results/            # 测试结果
├───data/                        # 数据目录
│   └───token_stats.db           # Token 用量统计数据库
├───docs/                        # 文档
│   ├───middleware-guide.md      # 中间件开发指南
│   ├───token-dashboard-api.md   # Token Dashboard API 文档
│   ├───kiro-gateway-deployment.md # Kiro Gateway 部署指南
│   ├───jquery-syntax-fix.md     # jQuery 语法修复
│   ├───UI 智能体介绍.md         # UI 智能体介绍
│   ├───测试用例示例.md           # 测试用例示例
│   └───coding/                  # Codegen Pipeline 优化任务
│       ├───codegen-pipeline-assessment.md
│       ├───P0-*.md              # 紧急任务
│       ├───P1-*.md              # 高优先级任务
│       ├───P2-*.md              # 中优先级任务
│       └───P3-*.md              # 低优先级任务
├───shell/                       # 辅助脚本
│   ├───kill-2025-simple.bat     # 终止服务器脚本
│   ├───init_script_index.py     # 脚本索引初始化
│   ├───run_ts.py                # Playwright 测试运行器
│   ├───refresh_auth.py          # 登录态刷新脚本
│   ├───check_middleware.py      # 中间件检查工具
│   ├───kiro_cleaner.py          # Kiro IDE 清理工具
│   ├───kiro-gateway-manager.bat # Kiro Gateway 管理
│   ├───start-kiro-gateway.bat   # Kiro Gateway 启动
│   ├───test_auth_loading.py     # 登录态加载测试
│   ├───test_bnp_auth.py         # BNP 认证测试
│   └───test_login.py            # 登录流程测试
├───base64_images/               # Base64 图片保存目录
├───playwright_reports/          # 测试报告
├───playwright_results/          # 测试结果 JSON
└───logs/                        # 日志目录
```

## 相关资源
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 文档](https://python.langchain.com/)
- [MCP 协议](https://modelcontextprotocol.io/)
- [Playwright 文档](https://playwright.dev/python/)
- [AntV Chart](https://antv.antgroup.com/)
