---
name: add-workflow
description: 在 app/agents/workflows/ 新增一条 LangGraph 风格工作流（WorkflowDefinition + WorkflowEdge + 条件边 + build_xxx_orchestrator 工厂），仅组合现有业务 Agent，不写业务逻辑。
---

# 新增 LangGraph 工作流

## 何时激活

用户说要"新增 / 加 / 编一条 workflow / 工作流 / DAG / 流程图"，串联多个业务 Agent。
典型触发词：「加一个 xx 测试工作流」「编一条 DAG 把 a/b/c 串起来」「再加一个流程跑 xxx」。

## 必要输入

确认（缺哪个问哪个）：

- 工作流名（snake_case，如 `regression_workflow` / `perf_testing`）
- 包含哪些 Agent（按执行顺序列出，必须都已经在 `app/agents/business/` 注册过）
- 边上是否有条件（如"意图为 ui 才继续"、"审核通过才落库"），具体函数签名 `(state) -> bool`
- 是否需要"短路"开关（参考 `skip_result` 用法：`state.input_data["skip_xxx"] = True` 时跳过末端节点）

## 项目硬约束

1. **首行** `from __future__ import annotations`，与 agent 层一致。
2. 工作流文件 **只描述 DAG，不写业务逻辑**，业务必须放在 Agent 里。
3. **必须导出三件套**：
   - `<name>_workflow: WorkflowDefinition` —— 顶层定义
   - `build_<name>_orchestrator() -> LangGraphOrchestrator` —— 注册 Agent + workflow 的工厂
   - `__all__` 列表
4. 条件边函数命名 `_xxx`（下划线前缀，模块私有），签名 `(state: AgentState) -> bool`，**只读 state，不副作用**。
5. 用现成的 Agent 实例，**不要在 workflow 文件里 import 第三方库**或定义新 Agent 子类。
6. **DAG 不能成环**：`LangGraphOrchestrator` 检测到环会停下报警告，但不要依赖兜底，自己保证。
7. 工作流的 token 经济性 **写进 docstring**：列出每个节点的近似 token 范围 + 总成本，参考 `api_testing_workflow.py` 的"Token 经济性"段落。

## 实现步骤

### 1. 阅读相邻样例

强制读：
- `app/agents/workflows/testcase_generation_workflow.py` —— 5 节点（intent → testcase → review_gate → persistence → result）
- `app/agents/workflows/api_testing_workflow.py` —— 6 节点 + 多重条件边
- `app/agents/orchestration/orchestrator.py` —— `WorkflowDefinition` / `WorkflowEdge` 字段

### 2. 写 Workflow 文件

新建 `app/agents/workflows/<name>_workflow.py`：

```python
"""
<工作流中文名>定义。

DAG
---

::

    a ─► b ─► c ─► d

- ``a``  <职责>
- ``b``  <职责>
- ...

输入契约
--------

::

    state.input_data 必填字段
    --------------------------
    requirement   str   <说明>
    project_id    int   <说明>

    可选字段
    --------
    mock              bool   全链路 mock，零 token
    skip_<node>       bool   跳过末端节点

Token 经济性
------------
| 节点 | tier  | 单次 token | 备注 |
|------|-------|-----------|------|
| a    | small | 200–500   | 分类 |
| b    | medium| 1k–2k     | 生成 |
| ...

总成本估算：约 X–Y token / 次。

作者: yandc
"""
from __future__ import annotations

from app.agents.business import (
    AAgent,
    BAgent,
    CAgent,
    DAgent,
)
from app.agents.orchestration import (
    AgentState,
    LangGraphOrchestrator,
    WorkflowDefinition,
    WorkflowEdge,
)


# ---------------------------------------------------------------------------
# 条件边
# ---------------------------------------------------------------------------
def _is_target_intent(state: AgentState) -> bool:
    """只有意图为 <xxx> 时才继续（节流：其他类型直接停下）。"""
    return state.output_data.get("test_type") == "<xxx>"


def _approved(state: AgentState) -> bool:
    return state.output_data.get("review_decision") == "approved"


def _should_run_d(state: AgentState) -> bool:
    """``skip_d`` 开关；默认走完。"""
    return not state.input_data.get("skip_d", False)


# ---------------------------------------------------------------------------
# 工作流定义
# ---------------------------------------------------------------------------
<name>_workflow = WorkflowDefinition(
    name="<name>",
    entry_point="a",
    edges={
        "a": [WorkflowEdge(target="b", condition=_is_target_intent)],
        "b": [WorkflowEdge(target="c", condition=_approved)],
        "c": [WorkflowEdge(target="d", condition=_should_run_d)],
    },
)


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
def build_<name>_orchestrator() -> LangGraphOrchestrator:
    """构造一个已经注册好 N 个 Agent + <工作流中文名>的编排器。"""
    orch = LangGraphOrchestrator()
    orch.register_agent("a", AAgent())
    orch.register_agent("b", BAgent())
    orch.register_agent("c", CAgent())
    orch.register_agent("d", DAgent())
    orch.register_workflow(<name>_workflow)
    return orch


__all__ = [
    "<name>_workflow",
    "build_<name>_orchestrator",
]
```

### 3. 在 `__init__.py` 导出

修改 `app/agents/workflows/__init__.py`：

```python
from app.agents.workflows.<name>_workflow import (
    <name>_workflow,
    build_<name>_orchestrator,
)

__all__ = [
    # ...
    "<name>_workflow",
    "build_<name>_orchestrator",
]
```

### 4.（可选）暴露给路由层

如果用户希望前端能触发该工作流，需在 `app/routes/agent_workflow.py`（或新建路由）里调 `build_<name>_orchestrator()`。这一步不属于 add-workflow 本身，建议触发后让用户走 `add-route` skill。

### 5. 烟雾测试（一次性脚本，不提交）

```python
import asyncio
import uuid
from app.agents.orchestration import AgentState
from app.agents.workflows import build_<name>_orchestrator

orch = build_<name>_orchestrator()
state = AgentState(
    task_id=str(uuid.uuid4()),
    correlation_id=str(uuid.uuid4()),
    workflow_id="<name>",
    input_data={"requirement": "测一个登录接口", "project_id": 1, "mock": True},
)
final = asyncio.run(orch.run_workflow("<name>", state))
print(final.metadata.get("workflow_status"))
print(final.output_data)
```

## 验证

1. `from app.agents.workflows import build_<name>_orchestrator` 能 import。
2. mock 模式跑通，`workflow_status == "completed"`。
3. 在 docstring 顶部画了 ASCII DAG 图，列出 token 经济性表。

## 反模式

- 在工作流文件里 **新建 Agent 子类** —— Agent 必须在 `business/` 中由 `add-agent` 完成。
- 条件边函数有副作用（写 DB / 调 LLM）—— 必须只读 state。
- 边目标 Agent 没注册 —— `register_agent` 必须先于 `register_workflow`。
- 缺 `entry_point` —— 必填字段。
- 不写 token 经济性段落 —— 项目 README 的"Token 经济性硬规则"写过，新工作流必须自报家门。
