# API 执行引擎（api_engine）需求文档

> 项目位置：`app/engine/api_engine/`
> 关联参考实现：`app/engine/liu_shui_xian.py`、`app/engine/test_factory.py`（仅作参考，不直接复用代码）
> 关联现有件：`app/services/request_factory.py`、`app/services/variable_replacer.py`、`app/services/executor.py`、`app/services/automation_executor.py`

---

## 1. 背景

当前接口测试能力分散在三处，互相独立、概念不统一：

1. `services/executor.py`（TestExecutor）—— 跑 `test_cases` 表的单条用例，落 `test_results`。
2. `services/automation_executor.py`（AutomationExecutor）—— 跑 `automation_tasks` 关联用例，落 `task_executions`。
3. `engine/liu_shui_xian.py` + `engine/test_factory.py` —— 早期"用例 → 步骤"流水线实现，**未接入业务路由**，独立运行。

三者面向不同数据源、不同表结构、不同执行语义，**断言、变量、报告各写一套**，扩展和维护成本高。

随着业务对接口测试的诉求接近 Postman / Apifox（单接口调试 → 多接口编排 → 数据驱动 → 链式调用），需要一个**统一的执行引擎**作为底层，把上述三处的执行能力收敛到同一抽象。

---

## 2. 目标

构建 `app/engine/api_engine/`，作为**所有接口执行场景**的唯一引擎层，对外提供清晰、稳定、可扩展的 API。

### 2.1 必须满足

- **单接口执行**：给定一个接口 ID 或临时 JSON，能解析变量、发请求、断言、产出结果。
- **多接口顺序执行**：给定一组接口 ID（或 CollectionSpec），按顺序执行，支持失败策略。
- **链式调用**：前一个请求的响应字段可被抽取到上下文，供后续请求引用（解决登录拿 token 给后续请求用的场景）。
- **变量解析**：复用现有的全局变量、环境变量、前置 URL、全局参数能力，不重写。
- **断言扩展**：状态码、JSON Path、文本包含、响应耗时、Header；扩展只加文件不动核心。
- **多种报告**：控制台摘要 + 数据库明细，多 reporter 同时挂；不生成 JSON 报告文件。
- **不破坏现有路由**：`routes/api.py`（单接口测试）、`routes/execute.py`（用例执行）、`routes/automation.py`（自动化任务）三个入口的对外契约保持不变。

### 2.2 不在本期范围

- Pre-request JS 沙箱（Postman 的 `pm.test`）—— 用声明式抽取规则替代。
- 数据驱动迭代（CSV/JSON 喂参）—— DTO 预留 `iterations` 字段，本期不实现。
- 并行执行 —— 顺序执行优先，DAG 与并发留待后续。
- Mock 模式 —— HttpClient 留接口口子，不实现 MockClient。

---

## 3. 用户故事与验收标准

### Story 1：单接口调试（前端"点击发送"）

**作为** 测试人员，**我希望** 在 Apifox 风格的接口详情页点"发送"，**以便** 立即看到这个接口的真实响应和断言结果。

#### 验收标准

1. WHEN 调用 `POST /api/projects/{project_id}/apis/{api_id}/test` 携带可选 `environment_id` 与字段覆盖参数 THEN 系统 SHALL 通过 `ApiEngine.run_api(...)` 执行并返回包含 `request`、`response`、`assertions`、`extracted`、`duration` 的 `RequestResult`。
2. WHEN 接口的 url、headers、params、body 中含 `{{var}}` 占位符 THEN 系统 SHALL 按"环境变量 > 全局变量"优先级解析；未解析的占位符 SHALL 原样保留并在 `RequestResult.warnings` 中提示。
3. WHEN `base_url` 为空且接口配置了 `prefix_url_id` 或 `module/service` THEN 系统 SHALL 解析出最终 URL（行为与现 `variable_replacer.resolve_prefix_url` 一致）。
4. WHEN 项目下配置了 `GlobalParam`（Header 类型）且请求 Header 没有同名键 THEN 系统 SHALL 自动合并到请求 Header。
5. WHEN HTTP 请求超时、连接失败、或解析异常 THEN `RequestResult.passed` SHALL 为 `false`，`error` SHALL 包含错误类型与消息，**不应**抛出未捕获异常到路由层。
6. WHEN 接口响应在断言通过的前提下返回非 2xx 状态码 THEN `RequestResult.passed` 由断言结果决定，**不**因状态码隐式判失败。

### Story 2：多接口编排执行（前端"批量运行"或"用例集"）

**作为** 测试人员，**我希望** 选择一组接口按顺序运行，前一个请求的响应能传给后一个，**以便** 构造业务流（登录 → 创建订单 → 查询订单）。

#### 验收标准

1. WHEN 调用 `ApiEngine.run_apis(api_ids, project_id, environment_id)` THEN 系统 SHALL 按 `api_ids` 顺序执行，返回 `CollectionResult`，包含 `total/passed/failed/error` 与每条 `RequestResult`。
2. WHEN 某个请求配置了 `extracts`（如 `{name: token, type: json_path, expression: $.data.token}`）THEN 抽取出的值 SHALL 写入 `ExecutionContext.variables`，后续请求中 `{{token}}` 占位符 SHALL 被替换为该值。
3. WHEN `fail_strategy = "fail_fast"` 且某请求失败 THEN 后续请求 SHALL 不再执行，已执行的结果照常返回。
4. WHEN `fail_strategy = "continue"`（默认）且某请求失败 THEN 引擎 SHALL 继续执行剩余请求。
5. WHEN 某请求配置了 `delay_ms > 0` THEN 引擎 SHALL 在该请求执行后、下一请求开始前等待对应毫秒数。
6. WHEN 整批执行完成 THEN `run_id`（uuid）SHALL 贯穿所有 RequestResult，便于报告聚合。

### Story 3：临时 JSON 调试（前端未保存接口）

**作为** 测试人员，**我希望** 不创建接口、直接传一段 JSON 就能跑，**以便** 快速验证想法。

#### 验收标准

1. WHEN 调用 `ApiEngine.run_ad_hoc(payload, project_id, environment_id)` 携带 `{method, url, headers, params, body, body_type, assertions, extracts}` THEN 引擎 SHALL 直接执行，**不**触碰任何数据库写操作。
2. WHEN payload 缺少必填字段（`method`、`url`）THEN 引擎 SHALL 抛 `InvalidRequestSpecError`，包含具体缺失字段名。

### Story 4：自动化任务执行（接调度器/Webhook）

**作为** 系统，**我希望** 现有的 `AutomationExecutor` 能委托给新引擎，**以便** 调度器与 Webhook 不感知底层实现变化。

#### 验收标准

1. WHEN `AutomationExecutor.execute_task(task_id, environment_id, trigger_source)` 被调用 THEN 内部 SHALL 委托给 `ApiEngine.run_automation_task(...)`，**对外签名与返回值（`TaskExecution`）保持完全不变**。
2. WHEN 引擎执行过程中产生 `RequestResult` THEN `PersistenceReporter` SHALL 在每条请求完成后写入 `TaskExecutionDetail`，与现有数据结构一致。
3. WHEN 任务执行整体失败（异常）THEN `TaskExecution.status` SHALL 置为 `failed`，`error_message` 包含 traceback，与现有行为一致。
4. WHEN 重复触发同一未完成任务 THEN SHALL 抛 `DuplicateExecutionError`（沿用现状）。

### Story 5：单测试用例执行（沿用 test_cases 表）

**作为** 老路径用户，**我希望** `routes/execute.py` 走的 `TestExecutor` 在引擎接管后，对外 API 不变。

#### 验收标准

1. WHEN `POST /api/execute/case/{case_id}` 被调用 THEN 内部 SHALL 通过 `ApiEngine.run_test_case(case_id)` 执行；返回 JSON 结构与现有 `test_results.to_dict()` 一致。
2. WHEN 用例的 `expected_status` / `expected_response` 字段非空 THEN 引擎 SHALL 自动转换为对应的 `AssertionRule`（status_code 与 json_contains），无需用户手动配置断言。

### Story 6：可扩展性

**作为** 维护者，**我希望** 新增一种断言类型/抽取类型/报告器只需加一个文件，不改核心代码。

#### 验收标准

1. WHEN 新增断言（如 `response_time` < N ms）THEN SHALL 仅需在 `assertions/builtin.py` 加一个继承 `BaseAssertion` 的子类并在 `AssertionRegistry` 注册。
2. WHEN 新增抽取（如 `xpath`）THEN SHALL 仅需在 `extractors/` 加文件并注册。
3. WHEN 新增报告器（如 HTML、Allure）THEN SHALL 仅需实现 `Reporter` 协议并在引擎构造时传入。

### Story 7：影响面可控

**作为** 项目负责人，**我希望** 这次大改造不破坏任何现有功能。

#### 验收标准

1. WHEN api_engine 包未被引用 THEN 现有所有接口、自动化任务、用例执行 SHALL 完全不受影响（兼容期共存）。
2. WHEN 切换 `routes/api.py` 的 `/test` 端点到新引擎 THEN 该端点的请求/响应 JSON 结构 SHALL 保持向后兼容（字段同名、类型同构）。
3. WHEN 老 `engine/liu_shui_xian.py` 与 `engine/test_factory.py` 仍在仓库中 THEN 它们 SHALL 不被任何业务路径引用（仅留作参考与历史归档），可在迁移完成后单独 PR 删除。

---

## 4. 数据模型增强需求

经评审现有 `Api`、`TestCase`、`AutomationTask` 等模型，发现以下能力需要补充。**所有新增字段一律可空且向后兼容**，不破坏旧数据。

### 4.1 `apis` 表新增字段（核心）

| 字段 | 类型 | 说明 | 必要性 |
|------|------|------|--------|
| `assertions` | JSON | 断言规则数组：`[{type, config}]` | **必须** —— 当前接口没有断言能力，单接口测试只能靠状态码 |
| `extracts` | JSON | 响应抽取规则：`[{name, type, expression}]` | **必须** —— 链式调用必需 |
| `pre_actions` | JSON | 预处理动作（v2 预留）：`[{type, config}]` | 可选 |
| `timeout` | Integer | 单接口超时秒数（覆盖默认 30s） | 可选 |

### 4.2 新增 `api_collections` 与 `api_collection_items` 表（多接口编排持久化）

当前 `automation_tasks` 表面向"调度任务"，绑定 cron / webhook，过重。前端"批量运行" / "Apifox 集合"应有更轻的实体：

```
api_collections
├── id
├── project_id
├── name
├── description
├── fail_strategy        VARCHAR(20)  fail_fast | continue
├── default_environment_id
├── created_at / updated_at

api_collection_items
├── id
├── collection_id
├── api_id               指向 apis 表
├── sort_order
├── overrides            JSON  本次执行的局部覆盖（可空）
├── on_failure           VARCHAR(20)  inherit | stop | continue
├── delay_ms             INT  执行后等待
```

> 这一对表是为 Story 2 持久化用例集准备的。如果首期前端不做持久化，仅做"勾选一批 api_id 临时跑"，**这两张表可以推迟到二期**，引擎本期只通过 `run_apis(api_ids, ...)` 接收临时列表即可。

### 4.3 新增 `engine_executions` 与 `engine_execution_steps`（统一执行记录）

现状 `task_executions` 仅服务 `automation_tasks`，`test_results` 仅服务 `test_cases`。引擎层希望有**一张统一的执行表**，承载所有引擎调用的轨迹：

```
engine_executions
├── id
├── run_id               UUID  对外暴露的执行 ID
├── project_id
├── source_type          api | apis | ad_hoc | test_case | automation_task | collection
├── source_ref           VARCHAR  起源标识（api_id/task_id/collection_id...）
├── environment_id
├── status               pending | running | completed | failed | cancelled
├── total / passed / failed / error / skipped
├── started_at / finished_at / duration
├── trigger_source       manual | cron | webhook | api
├── error_message        TEXT

engine_execution_steps
├── id
├── execution_id
├── step_index
├── name
├── api_id               可空（ad_hoc 没有）
├── method / url
├── status               passed | failed | error | skipped
├── request_payload      JSON
├── response_payload     JSON
├── assertions           JSON  执行后的 AssertionResult 列表
├── extracted            JSON
├── duration
├── error_message        TEXT
```

> 设计取舍：本期**不强制**新增这两张表。`automation_executor` 走原有 `task_executions` 路径，`PersistenceReporter` 写老表保持兼容。若决定引入，需迁移脚本，是另一个 PR。需求阶段先把它列出来作为后续演进锚点。

### 4.4 数据模型增强结论

本期**只必须**新增 `apis.assertions`、`apis.extracts`（4.1 前两项）。其余的 4.2、4.3 列为后续可选增强，spec 文档中标注但不强制实现。

---

## 5. 非功能需求

| 维度 | 要求 |
|------|------|
| 性能 | 单接口执行总耗时（除网络外）开销 ≤ 50ms |
| 可测试性 | 引擎核心（runner/assertions/extractors）SHALL 可在无 Flask app context、无数据库的情况下进行单元测试 |
| 可观测性 | 每次执行 SHALL 产出唯一 `run_id`，日志全程携带；关键阶段（render/send/extract/assert）SHALL 有 INFO 级日志 |
| 兼容性 | 现有路由、模型、数据库表 SHALL 不发生破坏性变更（仅增字段） |
| 命名 | 所有目录、文件、类、方法、属性命名 SHALL 见名知意；不使用中文命名（除 docstring）；不使用 `liu_shui_xian` 这类隐喻 |

---

## 6. 范围边界

**做：** api_engine 包、单/多接口运行、变量与抽取、断言、报告、与现有路由衔接、`apis` 表加两字段。

**不做：** 前端实现、Pre-request JS 沙箱、数据驱动迭代、并行/DAG、Mock 模式、删除老的 `liu_shui_xian.py` / `test_factory.py`（仅停止引用）。

---

## 7. 关键风险与对策

| 风险 | 对策 |
|------|------|
| 老路径切到新引擎后行为不一致（断言更严/更松） | 切换前后跑同一组用例对比 JSON 结构与状态字段；保留老代码以便回滚 |
| `apis` 表加字段对存量项目影响 | 字段允许 NULL；引擎读取时空值视为无断言/无抽取 |
| 链式调用变量在并发执行时串台 | `ExecutionContext` 严格按 `run_id` 隔离，禁止使用全局可变状态 |
| 重构波及面过大无法 review | 按阶段拆分多个 PR：① 引擎骨架 ② `/apis/{id}/test` 切流 ③ `automation_executor` 委托 ④ `TestExecutor` 委托 |
