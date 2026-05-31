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

    # 1) 零配置直接跑（用内置 MockLLM，不需要数据库 / AI 提供商）
    python -m app.agents.testcase_agent_demo

    # 2) 接真实大模型（走数据库里 is_default=True 的提供商）
    python -m app.agents.testcase_agent_demo --real

作者: yandc
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.llm import mock_llm

# 类型别名：一次"对话调用"，输入 messages，返回模型文本回复
LLMCallable = Callable[[list[dict]], str]


def _extract_json(text: str) -> dict:
    """从模型输出里抽出第一个 JSON 对象。

    1B 这种小模型经常在 JSON 前后塞解释性文字，直接 ``json.loads`` 会炸。
    这里允许有"前导/后缀文本"，找到第一个 ``{`` 到最后一个 ``}`` 之间的片段
    再解析。失败时返回空 dict 而不是抛错，避免 demo 因为模型一次抽风就挂掉。
    """
    # 优先尝试最严格的解析（理想情况）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


# ----------------------------------------------------------------------
# 0. LLM 槽位 —— 节点通过这个间接量调用模型，便于 mock / 真实切换
# ----------------------------------------------------------------------
# 默认是 MockLLM，``run_demo`` 可以通过参数注入 ``DBChatModel`` 这种
# 真实模型。节点函数本身只调用 ``_call_llm`` 不感知后端。
_LLM: LLMCallable = mock_llm


def _call_llm(messages: list[dict]) -> str:
    """统一调用入口：模板节点都走这条路，便于切换 LLM 实现。"""
    return _LLM(messages)


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
    user_prompt = (
        f"请为以下需求生成 1-2 条简短的测试用例，输出 JSON：\n"
        f"需求：{state['requirement']}\n\n"
        '严格按以下 JSON 格式输出，不要额外文字：\n'
        '{"cases":[{"title":"...","precondition":"...","steps":["..."],'
        '"expected":"...","priority":"P0"}]}'
    )
    if state.get("feedback"):
        user_prompt += f"\n\n上一轮评审反馈（请据此改进）：{state['feedback']}"

    messages = [
        {"role": "system", "content": "你是资深测试工程师，擅长设计测试用例。"},
        {"role": "user", "content": user_prompt},
    ]

    # 调用 LLM（demo 默认 mock_llm；通过 run_demo(llm=...) 注入真实模型）
    raw = _call_llm(messages)
    parsed = _extract_json(raw)
    cases = parsed.get("cases", [])
    if not cases:
        print(f"   ⚠️  模型输出未包含可解析的 cases，原始响应前 200 字: {raw[:200]!r}")
    else:
        print(f"   生成了 {len(cases)} 条用例：{[c.get('title', '?') for c in cases]}")

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

    raw = _call_llm(messages)
    review = _extract_json(raw)
    if not review:
        # 模型输出无法解析时不阻塞流程：判为"未通过 + 给个通用反馈"
        review = {
            "score": 0,
            "passed": False,
            "feedback": "模型评审输出无法解析为 JSON，请补全边界与异常用例。",
        }
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
def run_demo(
    requirement: str = "用户登录功能",
    max_attempts: int = 3,
    llm: LLMCallable | None = None,
) -> dict:
    """
    运行测试用例生成 agent，返回最终状态。

    Args:
        requirement: 需求描述
        max_attempts: 最大重试次数
        llm: 可选的 LLM 调用器，签名 ``(messages: list[dict]) -> str``。
             不传则使用模块默认的 ``mock_llm``。

    Returns:
        最终的 AgentState（dict）
    """
    global _LLM
    previous_llm = _LLM
    if llm is not None:
        _LLM = llm
    try:
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
        return app_graph.invoke(initial_state)
    finally:
        _LLM = previous_llm


def _make_db_chat_callable() -> LLMCallable:
    """把 ``DBChatModel`` 包成 ``LLMCallable``：吃 messages 列表，吐文本。

    数据库里的 prompt 我们这一步先不接（demo 的 prompt 是写死在节点里的），
    后续接库内 prompt 时再用 ``app.agents.prompts.render_messages``。
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from app.agents.llm import DBChatModel

    chat_model = DBChatModel(
        # 1B 小模型在 60s 默认超时下完成 2048 token 太勉强，
        # demo 实际产出只有几条 JSON 用例，600 完全够。
        max_tokens=600,
        temperature=0.3,
    )

    def _call(messages: list[dict]) -> str:
        # 把 [{role, content}] 转成 LangChain BaseMessage 列表
        cls_map = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
        lc_messages = [
            cls_map.get(m["role"], HumanMessage)(content=m["content"]) for m in messages
        ]
        return chat_model.invoke(lc_messages).content

    return _call


def _run_with_real_llm(requirement: str, max_attempts: int) -> dict:
    """在 Flask app context 内用 DBChatModel 跑一次。"""
    # 延迟导入，避免 mock 模式仍然必须装好 Flask / DB
    from app.flask_app import create_app

    app = create_app()
    with app.app_context():
        llm = _make_db_chat_callable()
        return run_demo(requirement=requirement, max_attempts=max_attempts, llm=llm)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph 测试用例生成 demo")
    parser.add_argument(
        "--real",
        action="store_true",
        help="使用数据库里默认的 AI 提供商（DBChatModel）而不是 MockLLM",
    )
    parser.add_argument(
        "--requirement",
        default="用户登录功能",
        help="需求描述（默认：用户登录功能）",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="评审循环最大次数（默认 3）",
    )
    args = parser.parse_args()

    print("=" * 60)
    title = "LangGraph Demo：测试用例生成 Agent（带评审循环）"
    if args.real:
        title += "  [DBChatModel · 真实模型]"
    else:
        title += "  [MockLLM · 零配置]"
    print(title)
    print("=" * 60)

    if args.real:
        result = _run_with_real_llm(args.requirement, args.max_attempts)
    else:
        result = run_demo(args.requirement, args.max_attempts)

    print("\n" + "=" * 60)
    print("✅ 流程结束，最终产出：")
    print("=" * 60)
    print(f"需求：{result['requirement']}")
    print(
        f"共尝试 {result['attempts']} 次，评审"
        f"{'通过' if result['review_passed'] else '未通过'}"
    )
    print(f"最终用例（{len(result['cases'])} 条）：")
    print(json.dumps(result["cases"], ensure_ascii=False, indent=2))
