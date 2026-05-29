"""
LangGraph 入门 Demo —— 测试用例生成 Agent（带评审循环）。

==============================================================================
这是一个用来"一起研究 LangGraph"的最小可运行示例。
它实现了自动化测试平台里最典型的一个场景：

    输入一句需求  →  生成测试用例  →  自动评审  →  不合格就带着反馈重新生成
                                              →  合格就结束并产出结果

==============================================================================
LangGraph 的三个核心概念（看完这个文件你就懂了）：

1. State（状态）
   一个贯穿整个流程的"共享数据包"。每个节点读它、改它、再传给下一个节点。
   这里用 TypedDict 定义，见 `AgentState`。

2. Node（节点）
   就是普通的 Python 函数：`def node(state) -> dict`。
   它接收当前 state，返回"要更新到 state 的字段"。
   这里有两个节点：`generate_node`（生成）、`review_node`（评审）。

3. Edge（边）
   连接节点的"流向"。
   - 普通边：A 做完一定走 B。
   - 条件边：根据 state 的内容决定下一步去哪（这就是实现"循环/分支"的关键）。
   本 demo 用条件边实现了"评审不通过就回到生成节点重做"的循环。

==============================================================================
运行方式：
    # 零配置直接跑（用内置 MockLLM，不需要数据库 / AI 提供商）
    python -m app.agents.testcase_agent_demo

作者: yandc
"""
from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app.agents.llm_bridge import mock_llm


# ----------------------------------------------------------------------
# 1. 定义 State —— 流程中所有节点共享的数据
# ----------------------------------------------------------------------
class AgentState(TypedDict):
    """
    在整张图里流动的状态。

    每个节点拿到它，按需读取/更新其中的字段。
    """
    requirement: str        # 输入：用户的需求描述
    cases: list             # 生成的测试用例列表
    review_passed: bool     # 评审是否通过
    feedback: str           # 评审反馈（不通过时用于指导下一轮生成）
    attempts: int           # 已尝试生成的次数（防止无限循环）
    max_attempts: int       # 最大允许尝试次数


# ----------------------------------------------------------------------
# 2. 定义 Node —— 每个节点是一个函数，输入 state，输出要更新的字段
# ----------------------------------------------------------------------
def generate_node(state: AgentState) -> dict:
    """
    生成节点：根据需求（以及上一轮的评审反馈）生成测试用例。
    """
    attempt = state["attempts"] + 1
    print(f"\n🟦 [生成节点] 第 {attempt} 次生成测试用例...")

    # 拼接 prompt：如果上一轮有反馈，就带上，引导模型改进
    user_prompt = f"请为以下需求生成测试用例。\n需求：{state['requirement']}"
    if state.get("feedback"):
        user_prompt += f"\n\n上一轮评审反馈（请据此改进）：{state['feedback']}"

    messages = [
        {"role": "system", "content": "你是资深测试工程师，擅长设计测试用例。"},
        {"role": "user", "content": user_prompt},
    ]

    # 调用 LLM（demo 用 mock_llm；接真实模型见文件末尾说明）
    raw = mock_llm(messages)
    cases = json.loads(raw).get("cases", [])
    print(f"   生成了 {len(cases)} 条用例：{[c['title'] for c in cases]}")

    # 返回要更新到 state 的字段
    return {"cases": cases, "attempts": attempt}


def review_node(state: AgentState) -> dict:
    """
    评审节点：对生成的用例打分，决定是否通过。
    """
    print("🟨 [评审节点] 正在评审用例质量...")

    cases_text = json.dumps(state["cases"], ensure_ascii=False)
    messages = [
        {"role": "system", "content": "你是测试评审专家。"},
        {"role": "user", "content": f"请评审以下测试用例的完整性：\n{cases_text}"},
    ]

    raw = mock_llm(messages)
    review = json.loads(raw)
    passed = review.get("passed", False)
    print(f"   评审得分 {review.get('score')}，"
          f"{'✅ 通过' if passed else '❌ 不通过'}：{review.get('feedback')}")

    return {
        "review_passed": passed,
        "feedback": review.get("feedback", ""),
    }


# ----------------------------------------------------------------------
# 3. 定义条件边的"路由函数" —— 决定评审之后往哪走
# ----------------------------------------------------------------------
def route_after_review(state: AgentState) -> str:
    """
    评审之后的分支决策：

    - 评审通过           → 结束（END）
    - 没通过但还有尝试次数 → 回到生成节点（形成循环）
    - 没通过且用尽次数    → 也结束，避免无限循环

    返回值是字符串，对应下面 add_conditional_edges 里映射的目标节点。
    """
    if state["review_passed"]:
        return "accept"
    if state["attempts"] >= state["max_attempts"]:
        print("\n⚠️  已达最大尝试次数，停止重试。")
        return "accept"
    print("   ↩️  评审未通过，带着反馈回到生成节点重做。")
    return "retry"


# ----------------------------------------------------------------------
# 4. 组装 Graph —— 把节点和边连起来
# ----------------------------------------------------------------------
def build_graph():
    """
    构建并编译 LangGraph 状态图。

    图的形状：
        START → generate → review → (条件)
                  ▲                    │
                  └──── retry ─────────┤
                                       └── accept → END
    """
    graph = StateGraph(AgentState)

    # 注册两个节点
    graph.add_node("generate", generate_node)
    graph.add_node("review", review_node)

    # 普通边：入口 → 生成 → 评审
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "review")

    # 条件边：评审之后根据 route_after_review 的返回值决定去向
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "retry": "generate",  # 返回 "retry" → 回到生成节点
            "accept": END,        # 返回 "accept" → 结束
        },
    )

    # compile() 把"图的定义"变成"可执行的对象"
    return graph.compile()


# ----------------------------------------------------------------------
# 5. 对外入口：跑一次完整流程
# ----------------------------------------------------------------------
def run_demo(requirement: str = "用户登录功能", max_attempts: int = 3) -> dict:
    """
    运行测试用例生成 agent，返回最终状态。

    Args:
        requirement: 需求描述
        max_attempts: 最大重试次数

    Returns:
        最终的 AgentState（dict）
    """
    app_graph = build_graph()

    # 初始状态
    initial_state: AgentState = {
        "requirement": requirement,
        "cases": [],
        "review_passed": False,
        "feedback": "",
        "attempts": 0,
        "max_attempts": max_attempts,
    }

    # invoke 会从 START 一路执行到 END，期间自动在节点间流转 state
    final_state = app_graph.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    print("=" * 60)
    print("LangGraph Demo：测试用例生成 Agent（带评审循环）")
    print("=" * 60)

    result = run_demo(requirement="用户登录功能")

    print("\n" + "=" * 60)
    print("✅ 流程结束，最终产出：")
    print("=" * 60)
    print(f"需求：{result['requirement']}")
    print(f"共尝试 {result['attempts']} 次，评审"
          f"{'通过' if result['review_passed'] else '未通过'}")
    print(f"最终用例（{len(result['cases'])} 条）：")
    print(json.dumps(result["cases"], ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------
    # 想接真实大模型？把 testcase_agent_demo 里的 mock_llm 换成：
    #
    #     from app.agents.llm_bridge import call_real_llm
    #     raw = call_real_llm(messages)
    #
    # 并在 Flask app context 内运行（因为要查数据库取 AI 提供商配置）：
    #
    #     from app.flask_app import create_app
    #     app = create_app()
    #     with app.app_context():
    #         run_demo("用户登录功能")
    # ------------------------------------------------------------------
