# Agent 框架重构与强化任务清单（Reconstruction-task-all）

> 目标：把 `code-factory/` 参考项目里的精华三件套（DAG 编排、模型路由、HITL 审核）迁入主项目，并在其上重构现有 `app/agents/` 内的 UI / Recording / Testcase agent，最终形成"通用骨架 + 业务 Agent + MCP 工具"三层可扩展架构。
>
> 命名约定（用户硬要求："见名知意"）：
>
> - `orchestration` 编排（DAG + 基类） / `routing` 路由（模型选择） / `review` 审核（HITL）
> - `business` 业务 Agent（沿用现有，重命名继承） / `config` 配置（YAML）
> - 文件名按"职责 + 类型"双词命名，避免 `utils.py` `helper.py` 这类含糊词

---

## 状态图例

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 阻塞 / 待决策

---

## Step 1：搬骨架（≈0 token，纯代码）

> **目标**：把 code-factory 三件套核心代码迁入 `app/agents/` 子目录，**不动现有任何 agent**，让骨架编译通过、依赖最小化。
>
> **完工标准**：`from app.agents.orchestration import LangGraphOrchestrator, BaseAgent` 可成功导入，无外部不可用依赖告警。

### 目录最终形态

```
app/agents/
├── orchestration/                  # DAG 编排引擎与 Agent 基类（运行时核心）
│   ├── __init__.py
│   ├── correlation.py              # correlation_id 上下文（替代 structlog.contextvars）
│   ├── state.py                    # AgentState / WorkflowStatus / AgentInvocationLog
│   ├── interfaces.py               # AgentInterface / OrchestratorInterface
│   ├── exceptions.py               # AgentExecutionError / SchemaValidationError
│   ├── base_agent.py               # BaseAgent 模板方法基类
│   └── orchestrator.py             # LangGraphOrchestrator + WorkflowDefinition / WorkflowEdge
├── routing/                        # 模型路由（按复杂度路由 + 同层重试 + 跨层升级）
│   ├── __init__.py
│   ├── routing_models.py           # ModelTier / TaskComplexity / LLMRequest / LLMResponse
│   └── model_router.py             # LiteLLMModelRouter（_call_model 暂留 hook）
├── review/                         # 人工审核闸（HITL）
│   ├── __init__.py
│   ├── review_models.py            # ReviewDecision / ReviewRequest / ReviewRecord
│   └── review_gate.py              # HumanReviewGate（DB 部分先内存化）
└── config/                         # YAML 配置
    ├── routing_rules.yaml
    └── review_gates.yaml
```

### 任务清单

- [x] T1.1 新建 `app/agents/orchestration/correlation.py`（contextvars 实现的 correlation_id 上下文，替代 structlog 依赖）
- [x] T1.2 新建 `app/agents/orchestration/state.py`（AgentState / WorkflowStatus / AgentInvocationLog）
- [x] T1.3 新建 `app/agents/orchestration/exceptions.py`（AgentExecutionError / SchemaValidationError / ModelRoutingError / ModelTierExhaustedError）
- [x] T1.4 新建 `app/agents/orchestration/interfaces.py`（AgentInterface / OrchestratorInterface / ModelRouterInterface / ReviewGateInterface）
- [x] T1.5 新建 `app/agents/orchestration/base_agent.py`（BaseAgent 模板方法 + JSON Schema 校验，日志接 `app.utils.debug.logs`）
- [x] T1.6 新建 `app/agents/orchestration/orchestrator.py`（LangGraphOrchestrator + WorkflowDefinition / WorkflowEdge，最多 2 次重试 + 不可变字段保护）
- [x] T1.7 新建 `app/agents/orchestration/__init__.py`（暴露上述 6 个核心符号）
- [x] T1.8 新建 `app/agents/routing/routing_models.py`（ModelTier / TaskComplexity / LLMRequest / LLMResponse / RoutingRule）
- [x] T1.9 新建 `app/agents/routing/model_router.py`（LiteLLMModelRouter，复杂度分类 / 层级升级 / 同层重试逻辑齐全；`_call_model` 内部延迟导入 litellm，未安装时抛清晰错误，**不阻塞模块导入**）
- [x] T1.10 新建 `app/agents/routing/__init__.py`
- [x] T1.11 新建 `app/agents/review/review_models.py`（ReviewDecision / ReviewRequest / ReviewRecord）
- [x] T1.12 新建 `app/agents/review/review_gate.py`（HumanReviewGate，DB 接口保留但默认内存模式，asyncpg 延迟导入）
- [x] T1.13 新建 `app/agents/review/__init__.py`
- [x] T1.14 新建 `app/agents/config/routing_rules.yaml`（先按现有 llm_gateway 默认值填充：local / aiop / kiro / aiclient 网关名）
- [x] T1.15 新建 `app/agents/config/review_gates.yaml`（首批审核点：testcase_generator 后必审）
- [x] T1.16 烟雾测试：`python -c "from app.agents.orchestration import LangGraphOrchestrator, BaseAgent; from app.agents.routing import LiteLLMModelRouter; from app.agents.review import HumanReviewGate; print('ok')"`

---

## Step 2：包适配器（≈0 token，重构）

> **目标**：把现有的 `ui_automation_agent` / `recording_agent` 包成 BaseAgent 子类，沿用现有 graph 入口不破坏，新增 `business/` 目录承载业务 Agent。
>
> **完工标准**：能用 `LangGraphOrchestrator` 串起 IntentAgent → TestcaseAgent → UIScriptAgent 跑通一个 hello-world 流程。

### 目录新增

```
app/agents/
└── business/                       # 业务 Agent（沿用现有，重命名继承 BaseAgent）
    ├── __init__.py
    ├── intent_agent.py             # 意图理解 Agent（NL → 测试类型/目标/断言点）
    ├── testcase_agent.py           # 测试用例生成 Agent（包装 services/testcase_generator）
    ├── ui_script_agent.py          # UI 脚本 Agent（包装现有 ui_automation_agent）
    ├── recording_agent.py          # 录制回放 Agent（包装现有 recording_agent，注意命名冲突处理）
    └── result_agent.py             # 结果解析 + bug 自动登记
```

### 任务清单

- [x] T2.1 新建 `app/agents/business/__init__.py`
- [x] T2.2 新建 `business/intent_agent.py`（继承 BaseAgent；最简版：调 llm_gateway 把 NL 解析为 `{test_type, target, assertions}`）
- [x] T2.3 新建 `business/testcase_agent.py`（继承 BaseAgent；`_process` 内调用 `app/services/testcase_generator.generate_test_cases_with_db_prompt`）
- [x] T2.4 新建 `business/ui_script_agent.py`（继承 BaseAgent；`_process` 内 `async with app.agents.ui_automation_agent.make_agent() as agent: ...`，把现有上下文管理器作为内嵌工具）
- [x] T2.5 处理命名冲突：根 `app/agents/recording_agent.py` 保留作为底层工厂；`business/recording_agent.py` 通过完整包路径区分，包装为 BaseAgent 子类
- [x] T2.6 新建 `business/result_agent.py`（继承 BaseAgent；`_process` 包装 `app/services/case_runner.execute_cases`，失败用例自动建 bug）
- [x] T2.7 新建 `app/agents/workflows/`（新建目录）+ `testcase_generation_workflow.py`：用 WorkflowDefinition 把 IntentAgent → TestcaseAgent → ResultAgent 串起来
- [x] T2.8 在 `app/routes/agent_workflow.py` 暴露 `POST /api/agent/workflow/testcase-generation` 端点（支持 mock 参数，零 token 即可触发完整链路）

---

## Step 3：第一条工作流 e2e（少量 token）

> **目标**：跑通"一句需求 → 生成用例 → 审核 → 落库 → 触发执行 → 失败建 bug"一条完整链路。
>
> **完工标准**：用 mock 用户提交"BNP 登录功能"需求，系统自动产 3 条用例落库，触发已有 mcp_server 的 `run_test_cases`，失败的写入 bugs 表。

### 任务清单

- [x] T3.1 串通 IntentAgent 实际调用（用 `local/llama3.2-1b` 跑分类，省 token） — 完成路径：业务 Agent 直接走 `services/llm_gateway.get_model`，Step 4 会切到 ModelRouter
- [x] T3.2 串通 TestcaseAgent → ReviewGate（先 mock 自动通过，后续接前端审核 UI） — 落地为 `business/review_gate_agent.py`，并把编排器改为运行时驱动以支持条件边
- [x] T3.3 ResultAgent 写 bug 时复用 `app/services/case_runner.execute_cases` 已有的失败-建-bug 逻辑（落库由新增 `business/persistence_agent.py` 节点完成）
- [x] T3.4 把工作流升级为 5 节点 e2e（intent → testcase → review_gate → persistence → result），通过 `/api/agent/workflow/testcase-generation` 暴露
- [x] T3.5 在主 `README.md` 的开发计划里把"Agent 通用化重构"的 3 个子项打勾

---

## Step 4：模型路由收紧 token（持续节流）

> **目标**：所有 BaseAgent 子类改走 `LiteLLMModelRouter.route()`，按复杂度分发到不同模型。
>
> **完工标准**：`routing_rules.yaml` 配置的规则真正生效；e2e 跑一遍能在日志里看到不同任务命中不同模型。

### 任务清单

- [x] T4.1 在 `model_router.py` 内 `_call_model` 接桥到 `app/services/llm_gateway.get_model`（避免硬依赖 litellm）；保留 litellm 适配器作为可选实现
- [x] T4.2 修改 `routing_rules.yaml`，把 task_type 改为现有 agent 名称（intent / testcase / ui_script / api_script / result）— Step 1 时已经完成
- [x] T4.3 改造 `BaseAgent` 增加 `_call_llm(messages, task_type, complexity)` 便捷方法，内部走 `ModelRouter`
- [x] T4.4 把 IntentAgent 的 LLM 调用改为 `self._call_llm(...)`（其他 Agent 通过 service 层间接调用 llm_gateway，service 层 Step 5 再统一收紧）
- [x] T4.5 跑 Step 4 烟雾测试：ModelRouter 无 litellm 依赖、复杂度分类按规则工作、`_call_llm` 全链路 OK、e2e 工作流回归通过

---

## Step 5：MCP 横向扩展（按需）

> **目标**：自建 atp-mcp 与 http-api-mcp，让 agent 能够触达主平台数据 + 直接发起 API 测试。
>
> **完工标准**：API 自动化 agent 能从需求生成 API 用例并实际跑通。

### 任务清单

- [x] T5.1 补全 `app/mcp_server/server.py` 缺失的工具：`query_apis` / `query_test_cases` / `query_bugs` / `query_requirements` / `query_test_results`
- [x] T5.2 新建 `app/mcp_server/http_api_server.py`（独立 MCP server，13 个工具：发请求 / 断言 / 链式调用 / 读 OpenAPI / 环境变量替换…）
- [x] T5.3 新建 `business/api_script_agent.py`（继承 BaseAgent，通过 `_call_llm` 走 ModelRouter 产 pytest 风格 API 测试脚本）
- [x] T5.4 在 `workflows/` 新增 `api_testing_workflow.py`（6 节点：intent → testcase → review → persistence → api_script → result，并通过条件边短路非 api 意图）
- [x] T5.5 评估 k6-mcp / locust-mcp 自建必要性，落到 `doc/perf-mcp-evaluation.md`：当前不立即自建，等真实压测立项再启动 MVP（`PerfAgent` + `perf-mcp` 3 工具）

---

## 风险与对冲

| 风险 | 对冲方案 |
|---|---|
| 搬 code-factory 代码可能带入 PostgreSQL/PGVector/structlog 依赖 | Step 1 已严格裁剪：日志接 `app.utils.debug.logs`，DB 部分先内存化，RAG 全砍 |
| 现有 `make_agent` 是 LangGraph API 的 graph 入口，包装后入口路径变 | 保留 `make_agent` 不动作为底层工厂，BaseAgent 子类内部调用它，新老入口共存 |
| Step 1-2 完成后看不到立竿见影的业务效果 | 必须做完 Step 3（一条 e2e 跑通），它就是 demo |
| litellm 未安装阻塞 model_router 导入 | `_call_model` 内部延迟导入；Step 1 只测路由逻辑，Step 4 桥接 llm_gateway |

---

## 进度追踪

| 步骤 | 任务数 | 已完成 | 状态 |
|---|---:|---:|---|
| Step 1 搬骨架 | 16 | 16 | ✅ |
| Step 2 包适配器 | 8 | 8 | ✅ |
| Step 3 e2e 工作流 | 5 | 5 | ✅ |
| Step 4 模型路由收紧 | 5 | 5 | ✅ |
| Step 5 MCP 横向扩展 | 5 | 5 | ✅ |
| **总计** | **39** | **39** | **🎉 100%** |
