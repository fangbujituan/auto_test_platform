# 自动化测试平台 (ATP)

基于 Flask + Vue 的 API 自动化测试平台，支持接口管理、测试用例、Bug 跟踪、用例执行和结果分析。

## 🌟 项目亮点

### 1. 现代化 Python Web 架构

**工程化标准实践**
- **蓝图模块化**：采用 Flask-Smorest 构建 RESTful API，所有路由基于 MethodView，自动生成 OpenAPI 3.0 文档
- **三层架构清晰**：Routes（接口层）→ Services（业务层）→ Models（数据层），职责分离，易于测试和维护
- **Schema 驱动开发**：Marshmallow 统一管理请求/响应定义，类型校验与文档生成一体化
- **依赖注入与配置分离**：环境变量 + 应用工厂模式，支持开发/测试/生产多环境无缝切换

**代码质量保障**
- **统一异常处理**：全局异常捕获与标准化错误响应（HTTP 状态码 + 业务错误码）
- **ORM 最佳实践**：BaseModel 抽象公共字段（id/created_at/updated_at），所有模型继承统一规范
- **安全加固**：密码 Werkzeug 哈希、API Key Fernet 对称加密存储、JWT Token 认证、CORS 白名单
- **代码规范**：遵循 PEP 8，统一使用 `from __future__ import annotations` 前向引用，类型注解覆盖核心模块

### 2. 容器化部署与运维

**一键式 Docker Compose 编排**
- **多容器协同**：Flask 后端（flask-app）+ Nginx 前端（nginx-frontend）+ MySQL 数据库（mysql-db）三容器独立部署
- **健康检查机制**：每个服务配置 healthcheck，确保依赖就绪后再启动（depends_on + condition: service_healthy）
- **数据持久化**：MySQL 数据卷映射到宿主机 `/opt/vplatform/auto_test_platform/mysql_data`，日志统一挂载便于运维
- **环境变量注入**：`.env` 文件管理敏感配置，容器内通过环境变量读取，避免硬编码
- **时区统一**：容器与宿主机时区一致（Asia/Shanghai），消除时间戳混乱

**生产级运维能力**
- **日志分级与滚动**：RotatingFileHandler 按大小切分，同时输出到控制台和文件，支持多级日志（INFO/ERROR）
- **优雅重启**：Docker 重启策略 `unless-stopped`，服务异常自动拉起
- **快速回滚**：Git 版本控制 + `docker compose up -d --build` 重新构建，支持灰度发布
- **监控友好**：容器日志可通过 `docker logs -f` 或宿主机文件直接查看，便于接入 ELK/Prometheus

### 3. 多 Agent 协作与 MCP 生态

**基于 LangGraph 的 Agent 编排**
- **微服务化 Agent 设计**：每个 Agent 单一职责（IntentAgent 意图识别、TestcaseAgent 用例生成、ReviewGateAgent 质量门禁、PersistenceAgent 落库、UIScriptAgent/APIScriptAgent 脚本生成），通过 Orchestrator 动态组装工作流
- **状态机驱动**：LangGraph StateGraph 管理多 Agent 协作状态，支持条件分支（如审核通过/拒绝）、循环迭代、异常回退
- **可插拔式扩展**：新增测试类型（性能测试/App 测试）只需实现 BaseAgent 接口 + 注册到 Orchestrator，零侵入现有代码
- **流式输出**：AI 对话接口支持 SSE（Server-Sent Events），实时推送 Agent 执行进度与中间结果

**MCP（Model Context Protocol）工具生态**
- **自建 MCP 工具**：
  - `atp-mcp`：将 ATP 后端能力（接口/用例/Bug/需求 CRUD）暴露为 MCP 工具，供外部 AI 调用
  - `http-api-mcp`：轻量 HTTP 客户端工具集（13 个工具），支持加载 OpenAPI、按 operationId 发请求、JSONPath 断言、会话变量管理
  - `recording-mcp`：基于 Playwright 的 Web UI 录制回放，生成可执行 TypeScript 脚本
- **MCP 即插即用**：`app/agents/mcp_clients/clients.py` 统一管理 MCP 连接，Agent 通过 `get_mcp_client()` 动态获取工具，支持本地进程和远程服务两种模式
- **多提供商 AI 适配**：`ai_adapters.py` 封装 OpenAI / DashScope（通义千问）/ Ollama 三种 LLM 提供商，统一接口调用，支持同步/流式响应

**Agent → Engine → Platform 三级架构**
- **Agent 层**：负责理解用户意图、生成测试资产（用例/脚本），通过 MCP 调用底层能力
- **Engine 层**：执行引擎按测试类型拆分（api_engine / ui_engine / perf_engine），统一"用例 → 脚本 → 执行 → 报告"闭环
- **Platform 层**：存储与查询测试数据（APIs / TestCases / TestResults），提供 RESTful 接口供前端和 Agent 调用

**Token 经济性设计**
- **缓存优先**：录制脚本落库，相同测试意图直接复用，避免重复生成
- **分层路由**：简单分类用小模型（llama3.2-1b / deepseek），复杂生成用大模型（Claude / GPT-4）
- **延迟加载**：AI 增强功能（质量周报/异常诊断）独立端点，默认关闭，按需触发
- **Token 统计系统**：LangChain Callback 追踪每次调用的 token 消耗，按 thread_id 聚合，支持成本分析与优化度量

### 4. 执行引擎的工业化设计

**统一 API 执行引擎（api_engine）**
- **四路径统一收敛**：单接口测试 / 多接口编排 / 自动化任务 / 用例执行四条路径共用同一引擎，消除重复代码
- **注册中心式扩展**：6 种内置断言（status_code / json_equals / json_contains / json_schema / json_subset / response_time）+ 3 种内置抽取器（json_path / regex / header），新增断言/抽取器只需注册，无需改引擎代码
- **链式抽取与变量传递**：前一接口的响应字段通过 `extracts` 配置提取到上下文，后续接口用 `{{变量名}}` 自动替换，支持复杂业务流
- **失败策略可插拔**：`continue`（失败继续）/ `fail_fast`（遇错即停），满足不同场景需求
- **老代码归档**：原有 `liu_shui_xian` / `test_factory` 等流水线实现迁移至 `_legacy/`，确保历史可追溯

**UI 自动化引擎（ui_engine）**
- **Playwright MCP 集成**：录制用户操作生成可执行脚本，支持 Chrome / Firefox / Safari 多浏览器
- **脚本模板化**：生成的 TS 脚本遵循统一模板（含等待策略、异常处理、截图保存），开箱即用

**未来扩展预留**
- **性能测试引擎（perf_engine）**：规划接入 k6 / Locust，支持压测脚本生成与指标采集
- **App 自动化引擎（app_engine）**：预留 Appium 方向，统一移动端测试能力

### 5. 数据库设计与迁移管理

**规范化表结构**
- **RBAC 权限模型**：users / roles / permissions / role_permissions 四表分离，项目级权限隔离（project_members 关联表）
- **测试资产分类存储**：apis（接口配置）/ test_cases（用例编排）/ test_results（执行结果）清晰分层，支持复杂查询与聚合统计
- **树形结构支持**：api_folders / modules 通过 `parent_id` 自关联实现多级目录，便于大型项目组织
- **敏捷需求管理**：requirements / sprints / tags / operation_logs 完整支持 Scrum 流程

**Migration 一次性脚本**
- **Alembic 版本管理**：`app/migrations/` 存放数据库变更脚本，支持自动升级/回退
- **索引优化**：高频查询字段（project_id / user_id / status）建立索引，聚合查询场景建联合索引
- **字符集统一**：utf8mb4_unicode_ci 支持 Emoji 和多语言，避免乱码问题

### 6. 前后端分离与接口文档自动化

**Swagger / ReDoc 自动生成**
- **零额外工作量**：所有路由迁移至 flask-smorest MethodView，接口描述、参数定义、响应示例自动生成 OpenAPI 文档
- **在线调试**：Swagger UI 支持直接发送请求测试接口，无需 Postman
- **文档即合约**：前端团队直接消费 `/api/docs/openapi.json`，减少沟通成本

**Vue 3 现代化前端**
- **Composition API**：组件逻辑更内聚，复用性强
- **Element Plus 组件库**：开箱即用的企业级 UI，支持按需引入
- **Axios 拦截器**：统一处理 Token 注入、错误码转换、登录态失效跳转

### 7. 可扩展的质量度量体系

**质量看板（规划中）**
- **7 大主题**：测试执行趋势 / Bug 分析 / 用例覆盖率 / 需求追踪 / 项目总览 / 团队效能 / 数据导出
- **纯 SQL 聚合**：默认零 LLM 调用，60s TTL 缓存 + 10s 查询熔断，高性能低成本
- **AI 增强可选**：质量周报 / 异常诊断通过独立端点触发，结果缓存 24h，按需消耗 token

**Token 统计系统 v2（开发中）**
- **多维度追踪**：按 thread_id / agent_name / model_name 聚合 token 消耗，支持成本核算
- **性能指标**：记录每次 LLM 调用的 latency / tokens_per_second，优化慢查询
- **预算告警**：超过预设阈值自动降级到小模型或触发通知

### 8. 架构设计哲学

本项目在代码组织和系统设计中贯彻以下核心原则：

#### **高内聚，低耦合**

**模块职责单一化**
- **业务 Agent 各司其职**：`IntentAgent` 只负责意图识别，`TestcaseAgent` 只负责用例生成，`PersistenceAgent` 只负责数据持久化。每个 Agent 平均代码量 < 200 行，单元测试覆盖率目标 > 80%
- **执行引擎独立演进**：`api_engine` / `ui_engine` / `perf_engine` 各自封装完整的"执行 → 断言 → 报告"逻辑，互不依赖。新增测试类型不影响现有引擎
- **Routes-Services-Models 强制分层**：路由层只做参数校验和权限检查，业务逻辑全部下沉到 Services，Models 只负责数据映射。跨层调用会触发 code review 告警

**依赖反转与接口抽象**
- **BaseAgent 抽象类**：所有业务 Agent 继承 `BaseAgent`，强制实现 `name` / `output_schema` / `async _process` 三个接口，Orchestrator 通过协议编程而非具体类
- **MCP 客户端抽象**：`mcp_clients/clients.py` 定义 `MCPClient` 协议，支持本地进程（stdio）和远程服务（SSE）两种实现，Agent 代码无需感知传输细节
- **断言与抽取器注册中心**：`api_engine` 的 `AssertionRegistry` / `ExtractorRegistry` 采用工厂模式，新增断言类型只需实现 `Assertion` 接口并注册，引擎核心逻辑零修改

**事件驱动与消息解耦**
- **LangGraph 状态机**：Agent 间通过 `StateGraph` 的状态字段传递数据，不直接调用彼此方法。例如 `ReviewGateAgent` 输出 `review_passed: bool`，Orchestrator 根据状态决定下一步流转
- **Webhook 预留**：执行结果支持通过 Webhook 异步通知外部系统（钉钉 / 飞书 / 企业微信），测试平台不强依赖通知渠道

#### **减少硬编码，拥抱配置化**

**YAML 配置驱动核心逻辑**
- **路由规则外置**：`app/agents/config/routing_rules.yaml` 定义意图关键词到 Agent 的映射，新增测试类型只需修改配置文件，无需改 Python 代码
```yaml
ui_automation:
  keywords: ["UI", "页面", "点击", "输入", "浏览器"]
  agent: "ui_script_agent"
  mcp_tool: "recording-mcp"
```
- **质量门禁可编程**：`review_gates.yaml` 定义用例审核规则（必填字段、命名规范、复杂度阈值），测试经理可自行调整门禁严格度
- **AI 提示词模板化**：`ai_prompt_templates` 表存储场景化提示词（用例生成 / Bug 分析 / 代码审查），非技术人员可通过 UI 编辑模板，无需发版

**环境变量与密钥管理**
- **.env 文件集中配置**：数据库连接 / AI API Key / JWT Secret 全部通过环境变量注入，同一套代码适配开发 / 测试 / 生产三环境
- **密钥加密存储**：`ai_provider_configs` 表的 `api_key` 字段用 Fernet 对称加密，加密密钥 `AI_ENCRYPTION_KEY` 独立管理，数据库泄露也无法直接窃取密钥
- **容器化配置注入**：Docker Compose 通过 `env_file: .env` 统一注入环境变量，避免 Dockerfile 硬编码敏感信息

**数据驱动的业务规则**
- **权限资源动态加载**：`permissions` 表定义资源（project / api / case）和操作（read / write / delete），新增业务模块只需插入权限记录，`@check_project_permission` 装饰器自动生效
- **断言规则 JSON 配置**：`apis` 表的 `assertions` 字段存储 JSON 数组，如 `[{"type": "status_code", "expected": 200}, {"type": "json_path", "path": "$.code", "expected": 0}]`，测试人员通过 UI 拖拽配置，无需写代码
- **失败策略可选**：`api_engine` 支持通过 `failure_strategy` 参数动态切换 `continue` / `fail_fast`，同一批用例可根据执行场景（冒烟 / 回归）选择不同策略

#### **面向扩展开放，面向修改封闭（OCP）**

**插件式架构实践**
- **新增测试类型零侵入**：要支持性能测试，只需：
  1. 实现 `PerfScriptAgent` 继承 `BaseAgent`
  2. 在 `app/agents/business/__init__.py` 导出
  3. 在 `routing_rules.yaml` 添加路由规则
  4. 在 `app/engine/perf_engine/` 实现执行逻辑
  核心 Orchestrator 无需任何改动
- **MCP 工具热插拔**：`mcp_clients/clients.py` 的 `get_mcp_client()` 通过工具名动态查找，新增 MCP 只需在 `AVAILABLE_MCPS` 字典注册，Agent 自动发现可用工具
- **前端路由约定式注册**：`client/src/router/index.js` 基于文件名约定自动加载路由，新增页面只需在 `views/` 目录创建 `.vue` 文件，无需手动注册

**版本化 API 设计**
- **URL 路径带版本号**：`/api/v1/projects`，未来接口变更时可并存 `/api/v2/projects`，老版本客户端平滑迁移
- **响应格式向后兼容**：新增字段放在对象末尾，废弃字段标记 `@deprecated` 但保留返回（至少 3 个版本），避免破坏性变更

#### **防御式编程与优雅降级**

**异常处理全覆盖**
- **三级异常捕获**：
  1. 路由层捕获参数校验异常 → 返回 400 + 详细错误信息
  2. Service 层捕获业务逻辑异常 → 记录日志 + 返回 500 + 用户友好提示
  3. 全局异常处理器捕获未预期异常 → 防止堆栈泄露 + 上报监控
- **LLM 调用熔断**：AI 接口超时设置 30s，失败自动降级到预设响应（如用例生成失败返回模板用例），避免挂起
- **数据库查询超时保护**：聚合查询设置 10s 超时 + LIMIT 1000 行限制，防止慢查询拖垮服务

**优雅降级策略**
- **缓存优先**：质量看板查询先读 Redis 缓存（TTL 60s），缓存未命中才查数据库，数据库故障时返回上一次缓存快照
- **AI 功能可关闭**：环境变量 `AI_ENABLED=false` 可全局关闭 AI 功能，平台核心能力（接口管理 / 用例执行）不受影响
- **部分失败不阻断**：批量执行用例时，单个用例失败不影响后续用例（`continue` 模式），最终汇总全部结果

#### **可测试性优先**

**依赖注入便于 Mock**
- **Service 构造函数注入依赖**：`APIService(db_session, http_client)`，单元测试时可注入 Mock 对象，无需真实数据库和网络请求
- **MCP 客户端可替换**：`BaseAgent` 的 `get_mcp_client()` 通过参数传入，测试时可注入返回预设响应的 Fake 客户端

**测试分层清晰**
- **单元测试**：`app/tests/` 覆盖 Services / Engines 核心逻辑，每个函数按"正常 / 边界 / 异常"三类组织测试用例
- **集成测试**：使用 SQLite in-memory 数据库 + Flask `app.test_client()`，测试完整的 API 调用链路
- **E2E 测试（规划中）**：基于 Playwright 录制的脚本回归执行，覆盖关键业务流程

---

**设计哲学落地检查清单**：
- ✅ 新增功能是否需要修改超过 3 个文件？（若是，考虑抽象）
- ✅ 配置项是否硬编码在代码中？（应移到 YAML / .env / 数据库）
- ✅ 是否有超过 200 行的函数？（应拆分为子函数或独立 Service）
- ✅ 异常路径是否有测试覆盖？（至少覆盖"输入非法 / 依赖失败 / 并发冲突"三类）
- ✅ 新增依赖是否会增加耦合？（优先组合而非继承，优先接口而非具体类）

---

**技术栈选型理念**：工业级 > 学院派，成熟方案 > 造轮子，渐进式架构 > 过度设计。每个技术选型都经过"是否解决实际痛点"和"团队学习成本"双重验证。

## 系统架构与规划

### 总体定位

本平台是一个 **AI 驱动的自动化测试平台**。前后端代码同仓库管理但运行时相互独立，通过 Git 同步到服务器后基于 Docker 分别部署（`flask-app`、`nginx-frontend`、`mysql-db` 各自独立容器，通过内部网络通信）。

目标形态：用户在页面的对话框中描述测试意图，平台即可**自动生成测试用例与可执行脚本**，覆盖三类测试：

- **UI 测试** — UI 用例 + 脚本（Web 端，对应 `app/engine/ui_engine`）
- **API 测试** — API 用例 + 脚本（接口端，对应 `app/engine/api_engine`）
- **性能测试** — 性能用例 + 脚本（压测，对应 `app/engine/perf_engine`）

> App 端自动化（`app/engine/app_engine`）作为后续扩展方向预留。

### 执行引擎（app/engine）

引擎层按测试类型拆分为独立子引擎，统一负责"用例 → 脚本 → 执行 → 报告"的闭环：

| 子引擎 | 目录 | 职责 | 状态 |
|--------|------|------|------|
| API 引擎 | `api_engine` | 接口用例执行、变量渲染、断言、抽取、报告，统一收敛单接口/多接口/自动化任务/用例执行四条路径 | ✅ 已落地 |
| UI 引擎 | `ui_engine` | Web UI 用例执行（Playwright）| ✅ 已落地 |
| App 引擎 | `app_engine` | 移动 App 用例执行（Appium 方向，预留） | ⬜ 规划中 |
| 性能引擎 | `perf_engine` | 性能/压测执行与指标采集（Locust / JMeter 方向） | ⬜ 规划中 |

> `api_engine` 已替代早期的 `liu_shui_xian.py` / `test_factory.py` 流水线实现；老代码归档在 `app/engine/_legacy/`。详见 `app/engine/api_engine/README.md`。

### AI 与 Agent 协作（app/agents）

- 平台通过 **MCP（Model Context Protocol）** 对外暴露能力，供 AI 客户端调用以驱动测试用例生成与执行。
- `app/agents` 存放基于 **LangGraph** 构建的多 Agent，编排"理解需求 → 生成用例 → 生成脚本 → 调用引擎执行 → 汇总结果"的多步骤工作流。

**待定：Agent 的部署形态**

多 Agent 协作的承载方式尚未最终确定，目前有两个候选方案，后续验证后再定：

1. **随后端打包进 Docker** — Agent 作为后端进程的一部分，随 `flask-app` 容器部署。优点是部署简单、与现有引擎同进程调用方便；缺点是耦合度高、横向扩展受限。
2. **独立注册表 / 服务** — Agent 作为独立可注册的服务（注册表模式），按需被发现和调用。优点是解耦、便于独立扩缩容与复用；缺点是需要额外的服务发现与通信机制。

> 此项为开放决策点，待执行引擎补全后结合实际负载再评估。

## 📚 文档

详细的技术文档和指南请查看 [doc 目录](doc/INDEX.md)。

### 快速链接
- [快速开始指南](doc/QUICK_START.md)
- [生产部署指南](doc/生产部署指南.md)


## 项目结构

```
auto_test_platform/
├── app/                      # 后端（Flask）
│   ├── flask_app.py          # Flask 应用工厂
│   ├── requirements.txt      # Python 依赖
│   ├── config/               # 配置模块
│   │   └── settings.py       # 数据库连接、环境配置
│   ├── models/               # 数据模型（ORM）
│   │   ├── base.py           # 基础模型（公共字段）
│   │   ├── user.py           # 用户模型
│   │   ├── project.py        # 项目模型
│   │   ├── project_member.py # 项目成员模型
│   │   ├── role.py           # 角色与权限模型
│   │   ├── api.py            # API 接口模型
│   │   ├── api_folder.py     # API 目录模型
│   │   ├── case.py           # API 测试用例模型
│   │   ├── test_case.py      # 测试用例管理模型
│   │   ├── bug.py            # Bug 模型
│   │   ├── sprint.py         # 冲刺（Sprint）模型
│   │   ├── requirement.py    # 需求模型与状态枚举
│   │   ├── tag.py            # 标签模型与需求-标签关联表
│   │   ├── operation_log.py  # 操作日志模型
│   │   ├── module.py         # 模块模型（树形结构）
│   │   ├── result.py         # 执行结果模型
│   │   ├── env_variable.py   # 环境变量模型
│   │   ├── ai_provider.py    # AI 提供商配置模型
│   │   └── ai_prompt.py      # AI 提示词模板模型
│   ├── routes/               # RESTful API 路由（全部基于 flask-smorest MethodView）
│   │   ├── auth.py           # 认证接口
│   │   ├── project.py        # 项目管理接口
│   │   ├── project_member.py # 项目成员接口
│   │   ├── role.py           # 角色管理接口
│   │   ├── api.py            # API 接口管理
│   │   ├── api_folder.py     # API 目录管理
│   │   ├── api_import.py     # API 导入（cURL / Swagger）
│   │   ├── case.py           # 用例管理接口
│   │   ├── test_case.py      # 测试用例管理接口
│   │   ├── bug.py            # Bug 管理接口
│   │   ├── sprint.py         # 冲刺管理接口
│   │   ├── requirement.py    # 需求管理、标签管理、操作日志接口
│   │   ├── execute.py        # 用例执行接口
│   │   ├── result.py         # 结果查询接口
│   │   ├── toolbox.py        # 工具箱接口
│   │   ├── dashboard.py      # 仪表盘接口
│   │   ├── env_variable.py   # 环境变量管理接口
│   │   ├── ai_provider.py    # AI 提供商配置接口
│   │   ├── ai_chat.py        # AI 对话接口（同步 + SSE 流式）
│   │   └── ai_prompt.py      # AI 提示词模板接口
│   ├── schemas/              # Marshmallow Schema（请求/响应定义）
│   │   ├── auth.py           # 认证相关 Schema
│   │   ├── project.py        # 项目相关 Schema
│   │   ├── member.py         # 项目成员 Schema
│   │   ├── common.py         # 通用 Schema
│   │   ├── case.py           # 用例 Schema
│   │   ├── execute.py        # 执行 Schema
│   │   ├── result.py         # 结果 Schema
│   │   ├── api_mgmt.py       # API 接口管理 Schema
│   │   ├── api_import.py     # API 导入 Schema（cURL / Swagger）
│   │   ├── bug.py            # Bug 管理 Schema
│   │   ├── requirement.py    # 需求/冲刺/标签/操作日志 Schema
│   │   ├── env_variable.py   # 环境变量 Schema
│   │   ├── ai.py             # AI 提供商/对话/提示词 Schema
│   │   └── test_case_mgmt.py # 测试用例管理 Schema
│   ├── services/             # 业务逻辑层
│   │   ├── executor.py       # 用例执行器
│   │   ├── request_factory.py # 请求构造器
│   │   ├── variable_replacer.py # 环境变量替换服务
│   │   ├── ai_service.py     # 统一 AI 调用服务
│   │   └── ai_adapters.py    # AI 提供商适配器（OpenAI / DashScope / Ollama）
│   ├── engine/               # 执行引擎（按测试类型拆分子引擎）
│   │   ├── api_engine/       # 接口自动化引擎（统一入口，单/多/自动化/用例 4 条路径都委托至此）
│   │   ├── ui_engine/        # Web UI 自动化引擎（Playwright）
│   │   ├── app_engine/       # 移动 App 自动化引擎（Appium，预留）
│   │   ├── perf_engine/      # 性能/压测引擎（规划中）
│   │   └── _legacy/          # 已归档：早期接口流水线（liu_shui_xian / test_factory 等 6 文件）
│   ├── agents/               # 基于 LangGraph 的多 Agent 协作
│   ├── tools/                # 工具模块
│   │   ├── toolbox/          # 工具箱（测试用例生成器等）
│   │   └── tool_excel_db/    # Excel-DB 对比工具
│   └── utils/                # 工具函数
│       ├── permission.py     # 权限装饰器
│       └── crypto.py         # API Key 加解密工具
├── client/                   # 前端（Vue 3）
│   ├── src/
│   │   ├── api/              # API 请求层
│   │   ├── components/       # 公共组件
│   │   ├── views/            # 页面视图
│   │   ├── router/           # 路由配置
│   │   └── main.js           # 入口文件
│   └── vite.config.js        # Vite 配置
├── doc/                      # 项目文档
├── run.py                    # 后端启动入口
└── README.md
```

## 数据库设计

| 表名 | 说明 |
|------|------|
| users | 用户表（登录认证） |
| projects | 项目表（组织管理） |
| project_members | 项目成员表（用户-项目-角色关联） |
| roles | 角色表（admin/owner/member/viewer） |
| permissions | 权限表（resource:action） |
| role_permissions | 角色权限关联表 |
| apis | API 接口表（请求配置；含 Phase 2 新增的 assertions / extracts / timeout 字段，对接 api_engine）|
| api_folders | API 目录表（树形结构） |
| test_cases | API 测试用例表（HTTP 请求、断言规则） |
| test_case_management | 测试用例管理表（功能用例） |
| test_case_api_bindings | 用例-接口绑定表 |
| bugs | Bug 表（缺陷跟踪） |
| modules | 模块表（树形结构） |
| sprints | 冲刺表（敏捷迭代管理） |
| requirements | 需求表（需求管理） |
| tags | 标签表 |
| requirement_tags | 需求-标签关联表 |
| operation_logs | 操作日志表 |
| test_results | 执行结果表（状态、响应、耗时） |
| environment_variables | 环境变量表（项目级变量管理） |
| ai_provider_configs | AI 提供商配置表（API Key 加密存储） |
| ai_prompt_templates | AI 提示词模板表（场景化提示词） |

## 本地项目初始化

### 后端初始化

```bash
# 克隆项目
git clone https://github.com/fangbujituan/auto_test_platform.git
cd auto_test_platform

# 创建并激活虚拟环境
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

创建数据库：

```sql
CREATE DATABASE business DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

配置环境变量（复制模板并修改）：

```bash
cp .env.example .env
# 修改 .env 中的数据库连接信息
```

`.env` 文件示例：
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=business
SECRET_KEY=dev-secret-key
AI_ENCRYPTION_KEY=your-fernet-key
```

启动后端服务：

```bash
# 启动服务（自动创建表）
python run.py

# 初始化用户和权限
python app/init_db.py
python -m app.init_permission
```

后端运行在 http://localhost:12048

### 前端初始化

```bash
cd client
npm install
npm run dev
```

前端运行在 http://localhost:5173

### 默认账号

| 用户名 | 密码 | 说明 |
|--------|------|------|
| admin | admin123 | 管理员 |
| test | test123 | 测试用户 |

## Swagger 接口文档

项目集成了 flask-smorest，自动生成 OpenAPI 3.0 规范的接口文档。启动后端服务后访问：

| 地址 | 说明 |
|------|------|
| http://localhost:12048/api/docs/swagger | Swagger UI（交互式文档，可直接调试接口） |
| http://localhost:12048/api/docs/redoc | ReDoc（阅读友好的文档） |
| http://localhost:12048/api/docs/openapi.json | OpenAPI JSON（可导入 Postman 等工具） |

所有 API 模块已全部迁移至 flask-smorest MethodView 模式，接口自动出现在 Swagger 文档中：
- 认证（auth）、项目（project）、项目成员（project_member）
- 角色（role）、API 接口（api）、API 目录（api_folder）
- 用例（case）、测试用例管理（test_case）、Bug（bug）
- 冲刺（sprint）、需求（requirement）、标签（tag）、操作日志（operation_log）
- 执行（execute）、结果（result）、工具箱（toolbox）、仪表盘（dashboard）
- API 导入（api_import）、环境变量（env_variable）
- AI 提供商（ai_provider）、AI 对话（ai_chat）、AI 提示词（ai_prompt）

> 完整接口列表请以 Swagger / ReDoc 在线文档为准，不再在此手动维护。

## 技术栈

### 后端
- Python 3.13+
- Flask 3.x — Web 框架
- Flask-SQLAlchemy — ORM
- Flask-Smorest — OpenAPI/Swagger 文档生成
- Marshmallow — 请求/响应 Schema 定义与校验
- Flask-CORS — 跨域支持
- PyMySQL — MySQL 驱动
- SQLAlchemy — SQL 工具包（Excel-DB 对比等场景直接使用）
- Cryptography — API Key 加密存储
- Requests — HTTP 客户端（AI 适配器、用例执行）
- Pandas + Openpyxl — Excel 数据处理
- python-dotenv — 环境变量加载
- Werkzeug — 密码哈希
- pytest — 单元测试

### 前端
- Vue 3 + Vite
- Element Plus — UI 组件库
- Axios — HTTP 客户端
- Vue Router — 路由管理
- WangEditor — 富文本编辑器

## 权限模型

采用 RBAC（基于角色的访问控制），分为项目级权限：

| 角色 | 说明 | 权限范围 |
|------|------|---------|
| admin | 平台管理员 | 所有权限 |
| owner | 项目负责人 | 项目内所有权限 |
| member | 项目成员 | 读写权限，不能删除项目和管理成员 |
| viewer | 只读用户 | 只能查看 |

## 功能模块

- 接口管理 — API 接口的增删改查、目录组织、在线测试
- API 导入 — 支持 cURL 命令和 Swagger/OpenAPI JSON 导入接口
- 测试用例 — 功能用例管理、用例-接口绑定
- Bug 管理 — 缺陷跟踪、状态流转、优先级/严重程度
- 需求管理 — 敏捷需求管理、冲刺迭代、标签分类、状态流转
- 用例执行 — 单个/批量/按项目执行，结果记录
- 环境变量 — 项目级变量管理，请求中 {{变量名}} 自动替换
- 仪表盘 — 项目统计、执行概览
- 工具箱 — 测试用例自动生成等辅助工具
- AI 助手 — 多提供商（OpenAI / 通义千问 / Ollama）对话、流式输出、提示词模板管理
- 权限管理 — RBAC 角色权限、项目成员管理
- 操作日志 — 用户操作行为记录与审计

## Docker 部署（生产环境）

**重要提示**：生产环境部署请务必阅读 **[生产环境部署指南](doc/生产环境部署指南.md)**，其中包含详细的安全配置、性能优化、监控维护和故障排除内容。

### 前置条件

- Ubuntu 服务器已安装 Docker 和 Docker Compose 插件
- 服务器已安装 Git

### 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/fangbujituan/auto_test_platform.git
cd auto_test_platform

# 2. 创建环境变量文件
cp .env.example .env

# 3. 修改 .env 中的配置（密码、密钥等）
vim .env
# 重点修改：
#   MYSQL_PASSWORD — 数据库密码
#   SECRET_KEY — Flask 密钥
#   AI_ENCRYPTION_KEY — AI 模块加密密钥
#   MYSQL_HOST=mysql-db（Docker 内部网络，不要改）

# 4. 构建并启动所有服务
docker compose up -d --build

# 5. 查看容器状态（确保全部 healthy）
docker compose ps

# 6. 初始化数据库数据（首次部署执行）
docker compose exec flask-app python -m app.init_db
docker compose exec flask-app python -m app.init_permission
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://服务器IP:1801 |
| 后端 API | http://服务器IP:12048 |
| Swagger 文档 | http://服务器IP:12048/api/docs/swagger |

### 日常运维

```bash
# 查看日志
docker compose logs -f flask-app
## 方式1：在宿主机直接查看（推荐）
# 查看日志文件
tail -f /opt/vplatform/auto_test_platform/logs/info.log
# 查看最近100行
tail -100 /opt/vplatform/auto_test_platform/logs/info.log

## 方式2：进入容器查看
# 进入容器
docker exec -it flask-app sh
# 查看日志
tail -f /app/logs/info.log

## 方式3：不进入容器直接查看
docker exec flask-app tail -f /app/logs/info.log


# 重启服务
docker compose restart flask-app

# 更新代码后重新部署
git pull
docker compose up -d --build

# 停止所有服务
docker compose down

# 停止并删除数据卷（慎用，会清除数据库数据）
docker compose down -v

# 重启
docker compose up -d

# 验证 Flask 时区
docker compose exec flask-app python -c "from datetime import datetime; print(datetime.now())"

# 验证 MySQL 时区
docker compose exec mysql-db mysql -uroot -p你的密码 -e "SELECT NOW();"
```

## 常见问题

### 端口被占用
```cmd
netstat -ano | findstr :12048
taskkill /F /PID <进程ID>
```

### 数据库连接失败
- 检查 MySQL 服务是否启动
- 确认数据库 `business` 已创建
- 验证 `app/config/settings.py` 中的连接信息

### 登录失败
- 确保已运行 `python app/init_db.py` 初始化用户数据
- 确保已运行 `python -m app.init_permission` 初始化权限

## 开发计划

> 优先级标注约定：**P0** 立即推进 / **P1** 下一批 / **P2** 待度量后启动 / **P3** 暂缓。
> 排序依据：度量先于优化、SQL 优先于 LLM、抽象优先于复制；优先做"零 token / 低 token"的工作以匹配 token 预算约束。

### 已完成

- [x] 用户登录认证
- [x] 项目管理（CRUD + 成员管理）
- [x] RBAC 权限系统
- [x] API 接口管理（目录树 + 在线测试）
- [x] 测试用例管理
- [x] Bug 管理
- [x] 用例执行与结果记录
- [x] 仪表盘基础统计（5 张总数卡片）
- [x] 工具箱（用例生成器）
- [x] Swagger 接口文档（flask-smorest）
- [x] 全部 API 模块迁移至 flask-smorest
- [x] 需求管理（冲刺、需求、标签、操作日志）
- [x] Swagger/OpenAPI 文件导入
- [x] cURL 命令导入
- [x] 环境变量管理（{{变量名}} 占位符替换）
- [x] AI 助手（多提供商适配、同步/流式对话、提示词模板）
- [x] Web UI 录制回放 Agent（基于 Playwright MCP，已生成可执行 TS 脚本）
- [x] UI 代码生成管线 P0–P3 主体优化（完成于 2026-03-24，详见 `ai-server/docs/coding/`）
- [x] Token 消耗统计 v1（接入 LangChain Callback，存 SQLite）
- [x] **接口测试统一执行引擎 `api_engine` 落地**（5 个 Phase 27 个任务，spec：`.kiro/specs/api-engine/`）
  - 单接口测试 / 多接口编排 / 自动化任务 / 用例执行 4 条路径全部收敛到同一引擎
  - 6 种内置断言（含 `json_subset` 部分匹配）+ 3 种内置抽取器，注册中心式可扩展
  - 链式抽取（前一接口响应字段可被后续接口 `{{var}}` 引用）
  - 失败策略可插拔（`continue` / `fail_fast`）
  - 老 `liu_shui_xian` / `test_factory` / `read_env` / `read_case` / `assertion_handler` / `report_generator` 已归档至 `app/engine/_legacy/`
  - `apis` 表新增 `assertions` / `extracts` / `timeout` 三列承载断言抽取规则

### P0 — 立即推进（基本零 token，是后续一切判断的基础）

- [ ] **Token 统计系统 v2 落地**（`ai-server/docs/coding/TS-P0-001 ~ TS-P1-001`）
  - [ ] 三张新表（threads / token_records / thread_events）建表与 v1→v2 迁移
  - [ ] TokenCounter 重构（thread_id 为核心维度）
  - [ ] TokenCallbackHandler 增加 on_llm_start / on_llm_error / latency 追踪
  - [ ] thread_id 通过 ContextVar 自动注入，去掉 agent 主动调用工具的依赖
  - [ ] v2 API 路由 `/api/v1/token-stats/*`
  - 价值：所有后续优化的"度量衡"，没有它无法判断 token 优化收益
- [ ] **质量数据看板后端骨架**（spec：`.kiro/specs/dashboard-quality-statistics/`）
  - [ ] `quality_dashboard_blp` 蓝图 + filter / cache / 权限隔离三件套
  - [ ] 60s TTL 缓存层 + `X-Cache: HIT/MISS` 头 + 10s 查询超时熔断
  - [ ] **首个主题：测试执行统计**（trend / by-project / duration-distribution）作为模板
  - [ ] 补 Alembic 索引迁移（详见 design.md 索引清单）
  - 价值：纯 SQL 聚合，零 token；模板跑通后剩余 6 个主题是复读机

### P1 — 下一批（Agent 通用化 + API 自动化首发）

- [x] **Agent 通用化重构（提炼通用测试流程骨架）** ✅ 2026-06
  - [x] 把 `tools/core/agent_factory.py` 的 `make_agent` 拆为「骨架 + 插件式 MCP/Prompt」（已迁入 `app/agents/orchestration` + `app/agents/business`）
  - [x] 统一流程：`意图解析 → 用例生成 → 审核 → 落库 → 执行 → 缺陷登记`（`app/agents/workflows/testcase_generation_workflow.py`）
  - [x] 拆分 `IntentAgent / TestcaseAgent / ReviewGateAgent / PersistenceAgent / UIScriptAgent / RecordingAgent / ResultAgent`，共享 BaseAgent + Orchestrator
  - 价值：扩展任意测试类型零边际成本，是后续 API/性能 agent 的前置条件
- [x] **atp-mcp（自建）—— 把 ATP 后端能力暴露为 MCP 工具** ✅ 2026-06
  - [x] 接口查询 / 用例查询 / Bug 查询 / 需求查询 / 执行结果查询 5 个 query 工具（含原有 ai_chat / 用例生成 / 用例执行）
  - [ ] 鉴权打通（沿用 `@login_required`，MCP 侧带 token） — 待后续接入
  - 价值：让 agent 能直接读写主平台，是「页面对话框驱动用例生成」的桥
- [x] **API 自动化 Agent + http-api-mcp** ✅ 2026-06
  - [x] 自建轻量 http-api-mcp（13 个工具：通用请求 / GET-POST 别名 / 加载 OpenAPI / 列端点 / 按 operationId 发请求 / 状态码-JSONPath-响应时间断言 / 会话变量管理）
  - [x] 基于通用骨架装配 `ApiScriptAgent`（产 pytest 风格脚本）
  - [x] 新增 `api_testing_workflow`（6 节点，非 api 意图自动短路）
- [ ] **质量看板剩余 6 个主题 + 前端**
  - [ ] Bug / 用例覆盖 / 需求 / 项目总览 / 团队效能 / 数据导出
  - [ ] 前端 `Dashboard.vue` 改造 + 接入 ECharts 5（按需引入）
  - [ ] Excel 导出（openpyxl）+ PDF 导出（reportlab，可选依赖降级 501）
- [ ] **swagger-mcp（自建小工具）**：解析 OpenAPI 自动生成 API case

### P2 — 待度量后启动

- [ ] **看板 AI 增强（默认关闭、按钮触发、结果缓存）**
  - [ ] AI 质量周报：把 7 大主题数据塞给 LLM 生成总结，单次 1K–3K token，缓存 24h
  - [ ] 异常诊断：通过率骤降 / Bug 突增时手动触发 LLM 解读
  - [ ] 智能筛选：自然语言转 Quality_Filter
- [ ] **性能自动化 Agent + k6-mcp / locust-mcp**
  - [ ] 自建 k6-mcp 或 locust-mcp（社区暂无成熟方案）
  - [ ] 装配 `perf_agent`，调引擎 `app/engine/perf_engine`
- [ ] **db-mcp 接入**（测试数据准备 / 断言数据落库，复用 mcp-server-mysql）
- [ ] **执行引擎增强与补全**
  - [x] API 引擎（api_engine）能力补全 ✅ 2026-06（详见已完成清单）
  - [ ] UI 引擎（ui_engine）补全（对接 recording_agent 产物）
  - [ ] 性能引擎（perf_engine）—— 性能用例 + 脚本自动生成与执行
- [ ] **页面对话框驱动的用例 + 脚本自动生成（UI / API / 性能）**

### P3 — 暂缓

- [ ] UI 代码生成管线 P3 系列锦上添花项（`ai-server/docs/coding/P3-*`）
- [ ] App 自动化（`app/engine/app_engine`，工具链最重）
- [ ] 定时任务支持
- [ ] 测试报告导出（与质量看板导出合并考量）
- [ ] LangGraph Agent 部署形态决策（随后端 Docker / 独立注册表）

### Token 经济性硬规则（写进 steering）

- 调用 agent 前先查 `recording_agent` 已有脚本，命中直接回放（已实现，持续保持）
- LLM 生成内容落库，相同 prompt-hash 走缓存
- 简单分类 / 路由用 `local/llama3.2-1b` 或 deepseek，重活才上 Claude/Opus
- 质量看板默认零 LLM，AI 增强独立 endpoint，绝不放进首屏自动加载

## Git 版本管理

### 首次推送到 GitHub

1. **初始化本地仓库**：
```bash
git init
git add .
git commit -m "Initial commit: Flask + Vue automation test platform"
```

2. **关联远程仓库**：
```bash
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
```

3. **推送到远程**：
```bash
git push -u origin main
```

### 日常开发提交

```bash
# 查看修改状态
git status

# 添加修改文件
git add .

# 提交修改
git commit -m "描述本次修改内容"

# 推送到远程
git push
```

### 拉取远程更新

```bash
git pull origin main
```