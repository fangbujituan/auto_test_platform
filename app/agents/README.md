# Agents 架构说明

> 本文档说明 `app/agents/` 的目录结构、设计决策与编码约定。
> 面向新成员快速理解"是什么、为什么、怎么用"。

---

## 一、整体定位（What）

`app/agents/` 是基于 **LangGraph** 的多 Agent 编排层，负责把一句自然语言需求
拆解为多步骤 DAG 工作流，自动完成"意图理解 → 用例生成 → 审核 → 落库 → 脚本生成 → 执行"等链路。

它**不重写**已有的 `app/services/` 业务逻辑，而是用统一的 Agent 骨架把 service 层
包装成可编排的节点。

---

## 二、目录结构（What）

```
app/agents/
├── orchestration/      # 编排引擎 + Agent 基类（运行时核心）
├── routing/            # 模型路由（按复杂度选 LLM）
├── review/             # 人工审核闸（HITL）
├── business/           # 业务 Agent（每个是 DAG 中的一个节点）
├── workflows/          # 工作流定义（把 Agent 串成 DAG）
├── llm/                # LLM 适配层（DB 配置 → LangChain ChatModel）
├── prompts/            # 提示词集合（代码内置 + 数据库托管）
├── tools/              # Agent 可调用的工具函数（MCP server 暴露的能力）
├── mcp_clients/        # 外部 MCP server 的客户端连接器
└── config/             # YAML 配置（路由规则、审核点）
```

---

## 三、各模块职责与设计理由（What + Why）

### `orchestration/` — 编排引擎

| 文件 | 是什么 | 为什么需要 |
|------|--------|-----------|
| `state.py` | `AgentState`：跨 Agent 流转的共享状态 | 所有节点读写同一个状态对象，避免参数爆炸 |
| `base_agent.py` | `BaseAgent`：模板方法基类 | 统一日志、计时、不可变字段保护、输出校验；子类只需实现 `_process()` |
| `orchestrator.py` | `LangGraphOrchestrator`：DAG 编排器 | 把多个 Agent 按 `WorkflowDefinition` 的边定义串起来执行 |
| `interfaces.py` | 抽象接口 | 面向接口编程，方便 mock 和替换实现 |
| `exceptions.py` | 统一异常类型 | 编排器可按异常类型决定重试 / 跳过 / 终止 |
| `correlation.py` | `correlation_id` 上下文 | 一次请求贯穿多个 Agent，用 contextvars 传递追踪 ID |

**设计决策**：用模板方法模式而非继承链，因为业务 Agent 之间没有层级关系，
只是"都需要日志 + 计时 + 校验"这套公共行为。

### `routing/` — 模型路由

| 文件 | 是什么 | 为什么需要 |
|------|--------|-----------|
| `routing_models.py` | `ModelTier` / `TaskComplexity` / `LLMRequest` / `LLMResponse` | 类型安全的数据结构 |
| `model_router.py` | `ModelRouter`：按复杂度分发到不同模型 | 简单任务用本地小模型省 token，复杂任务升级到云端大模型 |

**设计决策**：路由规则外置到 `config/routing_rules.yaml`，运维可热改而不动代码。

### `review/` — 人工审核闸

| 文件 | 是什么 | 为什么需要 |
|------|--------|-----------|
| `review_models.py` | `ReviewDecision` / `ReviewRequest` / `ReviewRecord` | 审核流程的数据结构 |
| `review_gate.py` | `HumanReviewGate`：HITL 决策点 | AI 生成的用例必须经人工确认才能落库，防止垃圾数据入库 |

**设计决策**：默认内存模式（开发/测试用），可选 DB 持久化（生产用）。

### `business/` — 业务 Agent

每个文件 = DAG 中的一个能力节点，继承 `BaseAgent`，只实现 `_process()`。

| Agent | 职责 |
|-------|------|
| `intent_agent.py` | 自然语言 → `{test_type, target, assertions}` |
| `testcase_agent.py` | 生成结构化测试用例（正常/边界/异常） |
| `review_gate_agent.py` | 在 DAG 中插入审核等待点 |
| `persistence_agent.py` | 审核通过后写入数据库 |
| `api_script_agent.py` | 生成 pytest 风格的 API 测试脚本 |
| `ui_script_agent.py` | 生成 UI 自动化脚本（包装 Playwright agent） |
| `recording_agent.py` | 浏览器录制回放 |
| `result_agent.py` | 执行结果解析 + 失败自动建 Bug |

**设计决策**：
- 零基础设施重写 — 业务能力已在 `app/services/` 实现，这里只是包一层 BaseAgent 壳。
- 支持 mock 模式 — `state.input_data["mock"] = True` 时跳过 LLM，便于零 token 测试。

### `workflows/` — 工作流定义

| 文件 | DAG 结构 |
|------|----------|
| `testcase_generation_workflow.py` | intent → testcase → review_gate → persistence → result |
| `api_testing_workflow.py` | intent → testcase → review_gate → persistence → api_script → result |

**设计决策**：工作流只描述"谁连谁"，不包含业务逻辑。新增工作流只需组合已有 Agent。

### `llm/` — LLM 适配层

| 文件 | 是什么 | 为什么需要 |
|------|--------|-----------|
| `chat_model.py` | `DBChatModel`：从数据库读配置的 LangChain ChatModel | 让 LangGraph 生态（tool calling、structured output）能直接消费 |
| `bridge.py` | `MockLLM` + `call_real_llm` | 旧版兼容入口；新代码用 `DBChatModel` |

**设计决策**：所有凭证和提供商配置存数据库，agent 层不持有任何 API Key。

### `prompts/` — 提示词

| 来源 | 适用场景 |
|------|----------|
| 代码内置（`recording.py` / `ui_automation.py`） | 稳定不变的系统提示词 |
| 数据库托管（`db_prompt.py`） | 需要前端编辑、热更新的业务提示词 |

### `tools/` — Agent 工具函数

MCP server 暴露给 Agent 的可调用能力（用例 CRUD、执行、AI 对话等）。

### `mcp_clients/` — 外部 MCP 客户端

Agent 作为 client 连接外部 MCP server（Playwright、Chrome DevTools、搜索引擎等），
获取 LangChain `Tool` 对象挂到 agent 上。

> ⚠️ 与 `app/mcp_server/` 方向相反：那边是"我们对外暴露 server"，这里是"我们消费别人的 server"。

### `config/` — YAML 配置

| 文件 | 控制什么 |
|------|----------|
| `routing_rules.yaml` | 每种 task_type 对应的模型层级、复杂度阈值 |
| `review_gates.yaml` | 哪些 Agent 执行后需要人工审核 |

---

## 四、编码约定（How）

### 4.1 `from __future__ import annotations`

每个文件顶部都加这一行。原因：

1. **避免循环导入** — 类型注解不会在 import 时求值，A 引用 B、B 引用 A 不会报错
2. **支持前向引用** — 可以引用还没定义的类名，不需要加引号
3. **Python 3.14 将成为默认行为** — 提前适配

### 4.2 文件命名

"职责 + 类型"双词命名，禁止 `utils.py` / `helper.py` 这类含糊词。

```
✅ model_router.py      （模型 + 路由器）
✅ routing_models.py    （路由 + 数据模型）
✅ review_gate.py       （审核 + 闸）
❌ utils.py
❌ helpers.py
```

### 4.3 `__init__.py` 规范

每个子包的 `__init__.py` 必须包含：
- 模块级 docstring（说明职责）
- 显式 import 所有公开符号
- `__all__` 列表

这样外部只需 `from app.agents.orchestration import BaseAgent`，不需要知道内部文件结构。

### 4.4 BaseAgent 子类写法

```python
from __future__ import annotations

from app.agents.orchestration import AgentState, BaseAgent


class MyAgent(BaseAgent):
    name = "my_agent"                    # 必须：唯一标识

    output_schema = {                    # 可选：输出校验
        "type": "object",
        "required": ["result"],
        "properties": {"result": {"type": "string"}},
    }

    async def _process(self, state: AgentState) -> AgentState:
        # 业务逻辑写这里
        result = await self._call_llm(messages=[...], state=state)
        state.output_data["result"] = result
        return state
```

### 4.5 依赖原则

- **延迟导入**：重型依赖（litellm、playwright）在函数内部 import，不阻塞模块加载
- **面向接口**：业务 Agent 依赖 `AgentInterface` / `ModelRouterInterface`，不直接依赖实现类
- **零外部强依赖**：骨架层（orchestration / routing / review）不依赖任何需要网络的第三方库

---

## 五、数据流（How it works）

```
用户请求
  │
  ▼
路由层 (Flask route)
  │  创建 AgentState，调用 orchestrator.run()
  ▼
LangGraphOrchestrator
  │  按 WorkflowDefinition 的边依次执行 Agent
  ▼
BaseAgent.execute()          ← 模板方法：日志 + 计时 + 校验
  │  调用子类 _process()
  ▼
业务 Agent._process()
  │  调用 self._call_llm() → ModelRouter → LLM
  │  或调用 app/services/ 的已有逻辑
  ▼
AgentState（更新 output_data）
  │  传给下一个 Agent
  ▼
最终结果返回给用户
```

---

## 六、扩展指南（Then）

| 想做什么 | 怎么做 |
|----------|--------|
| 新增一个业务 Agent | 在 `business/` 新建文件，继承 `BaseAgent`，实现 `_process()` |
| 新增一条工作流 | 在 `workflows/` 新建文件，用 `WorkflowDefinition` 组合已有 Agent |
| 调整模型路由策略 | 修改 `config/routing_rules.yaml` |
| 新增审核点 | 修改 `config/review_gates.yaml` |
| 接入新的外部 MCP server | 在 `mcp_clients/clients.py` 新增工厂函数 |
| 新增 Agent 工具 | 在 `tools/` 新增文件 |
