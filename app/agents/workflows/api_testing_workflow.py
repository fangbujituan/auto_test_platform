"""
API 测试工作流定义。

DAG
---

::

    intent ─► testcase ─► review_gate ─► persistence ─► api_script ─► result

- ``intent``        把需求分类到 ``api`` 类型
- ``testcase``      生成结构化用例（包含正常 / 边界 / 异常三类）
- ``review_gate``   人工审核
- ``persistence``   审核通过后落库
- ``api_script``    生成 Python pytest 风格的 API 测试脚本
- ``result``        触发执行 + 失败建 bug

与 testcase_generation_workflow 的差异
--------------------------------------
- 多了 ``api_script`` 节点：在落库后立即产出可执行脚本
- 通过条件边把"非 api 类型意图"导向直接结束（防止把 UI 任务塞到 API 流程）

Token 经济性
------------
对比 ``testcase_generation_workflow``，本工作流多消耗 1 次 LLM 调用
（``api_script``）。但因为 ``api_script`` 在 routing_rules.yaml 里走
**medium 复杂度**，并且没有 DOM/快照噪音，单次约 800–2000 token，
显著低于一次 UI Agent 的多轮交互。

作者: yandc
"""
from __future__ import annotations

from app.agents.business import (
    ApiScriptAgent,
    IntentAgent,
    PersistenceAgent,
    ResultAgent,
    ReviewGateAgent,
    TestcaseAgent,
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
def _is_api_intent(state: AgentState) -> bool:
    """只有意图为 api 时才继续生成用例（节流：UI / 性能任务直接停下）。"""
    return state.output_data.get("test_type") == "api"


def _approved(state: AgentState) -> bool:
    return state.output_data.get("review_decision") == "approved"


def _should_run_result(state: AgentState) -> bool:
    return not state.input_data.get("skip_result", False)


# ---------------------------------------------------------------------------
# 工作流定义
# ---------------------------------------------------------------------------
api_testing_workflow = WorkflowDefinition(
    name="api_testing",
    entry_point="intent",
    edges={
        "intent": [WorkflowEdge(target="testcase", condition=_is_api_intent)],
        "testcase": [WorkflowEdge(target="review_gate")],
        "review_gate": [WorkflowEdge(target="persistence", condition=_approved)],
        "persistence": [WorkflowEdge(target="api_script")],
        "api_script": [WorkflowEdge(target="result", condition=_should_run_result)],
    },
)


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
def build_api_testing_orchestrator() -> LangGraphOrchestrator:
    """构造一个已经注册好 6 个 Agent + API 测试工作流的编排器。"""
    orch = LangGraphOrchestrator()
    orch.register_agent("intent", IntentAgent())
    orch.register_agent("testcase", TestcaseAgent())
    orch.register_agent("review_gate", ReviewGateAgent())
    orch.register_agent("persistence", PersistenceAgent())
    orch.register_agent("api_script", ApiScriptAgent())
    orch.register_agent("result", ResultAgent())
    orch.register_workflow(api_testing_workflow)
    return orch


__all__ = [
    "api_testing_workflow",
    "build_api_testing_orchestrator",
]
