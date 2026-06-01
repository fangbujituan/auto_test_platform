"""
测试用例生成工作流定义（e2e 5 节点版）。

DAG
---

::

    intent ─► testcase ─► review_gate ─► persistence ─► result

- ``intent``        把用户需求解析为 ``test_type / target / assertions``
- ``testcase``      把需求转成结构化用例列表（**纯 LLM，无副作用**）
- ``review_gate``   人工审核闸；不通过则编排器把工作流标记为 failed
- ``persistence``   审核通过后批量落库到 ``test_case_management``
- ``result``        触发执行 + 失败建 bug（依赖 ``case_ids``，由 persistence 注入）

::

    state.input_data 必填字段
    --------------------------
    requirement   str   需求描述
    project_id    int   落 bug / 落用例的项目 id

    可选字段
    --------
    mock              bool   全链路 mock，不烧 token、不写 DB
    mock_review       bool   只走"审核闸 mock"，其它真实跑
    review_decision   str    "approved" / "rejected"，强制注入决策
    model             str    LLM 模型标识
    extra_context     str    附加上下文
    module_id, folder_id, environment, version, reporter_id

跳过 result 的"轻量模式"
------------------------
当 ``state.input_data["skip_result"] = True`` 时，编排器在 ``persistence``
后停下，不触发执行。用于"只生成不执行"的场景，路由层根据是否需要执行
来决定要不要传入这个开关。

为什么把审核闸放在 persistence 之前
-----------------------------------
**审核未通过的用例不应进入数据库**。先审后落库，把脏数据风险降到 0。

作者: yandc
"""
from __future__ import annotations

from app.agents.business import (
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
# 条件边：审核通过才往下走；persistence 后是否触发执行可由 state 控制
# ---------------------------------------------------------------------------
def _approved(state: AgentState) -> bool:
    """审核闸输出为 approved 时才让 persistence 继续。"""
    return state.output_data.get("review_decision") == "approved"


def _should_run_result(state: AgentState) -> bool:
    """``skip_result`` 开关；默认 True（即默认会执行）。"""
    return not state.input_data.get("skip_result", False)


# ---------------------------------------------------------------------------
# 工作流定义
# ---------------------------------------------------------------------------
testcase_generation_workflow = WorkflowDefinition(
    name="testcase_generation",
    entry_point="intent",
    edges={
        "intent": [WorkflowEdge(target="testcase")],
        "testcase": [WorkflowEdge(target="review_gate")],
        "review_gate": [WorkflowEdge(target="persistence", condition=_approved)],
        "persistence": [WorkflowEdge(target="result", condition=_should_run_result)],
    },
)


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
def build_testcase_generation_orchestrator() -> LangGraphOrchestrator:
    """构造一个已经注册好 5 个 Agent + 工作流的编排器。

    Returns:
        :class:`LangGraphOrchestrator` 实例。
    """
    orch = LangGraphOrchestrator()
    orch.register_agent("intent", IntentAgent())
    orch.register_agent("testcase", TestcaseAgent())
    orch.register_agent("review_gate", ReviewGateAgent())
    orch.register_agent("persistence", PersistenceAgent())
    orch.register_agent("result", ResultAgent())
    orch.register_workflow(testcase_generation_workflow)
    return orch


__all__ = [
    "testcase_generation_workflow",
    "build_testcase_generation_orchestrator",
]
