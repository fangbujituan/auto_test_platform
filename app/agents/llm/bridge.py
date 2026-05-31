"""
LLM 桥接层（旧版兼容入口）。

> 历史模块：原本位于 ``app/agents/llm_bridge.py``，2026-06 整合时迁入
> ``app/agents/llm/bridge.py`` 与 ``DBChatModel`` 同居。
>
> ``call_real_llm()`` 的功能已被 :class:`app.agents.llm.DBChatModel` 完全
> 覆盖，新代码请直接用 ``DBChatModel().invoke(...)``。这里保留是为了让
> 老的 demo / 手册示例继续可跑。
>
> ``MockLLM`` 仍然有保留价值——零依赖、可以让 LangGraph 教学 demo
> 在没有数据库 / AI 提供商的环境下立刻跑起来。

作者: yandc
"""
from __future__ import annotations

import json
import re


# ----------------------------------------------------------------------
# 真实 LLM：复用项目现有 AIService
# ----------------------------------------------------------------------
def call_real_llm(messages: list[dict], provider_id: int | None = None) -> str:
    """
    调用项目现有的 AIService 完成一次对话。

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        provider_id: AI 提供商配置 ID，None 表示用默认提供商

    Returns:
        模型返回的纯文本内容

    Raises:
        RuntimeError: AIService 返回错误时抛出

    注意：此函数依赖 Flask app context（因为 AIService 要查数据库取配置），
    需要在 `with app.app_context():` 内调用。
    """
    # 延迟导入，避免在纯 demo（MockLLM）场景下强依赖 Flask / DB
    from app.services.ai_service import AIService

    result = AIService().chat(messages)
    if "error_code" in result:
        raise RuntimeError(
            f"LLM 调用失败: {result['error_code']} - {result.get('error_message')}"
        )
    return result.get("content", "")


# ----------------------------------------------------------------------
# Mock LLM：无需任何外部依赖，用于学习 / 单测
# ----------------------------------------------------------------------
class MockLLM:
    """
    一个假的"大模型"，根据 prompt 里的关键字返回预设的结构化结果。

    它的目的不是"聪明"，而是让 LangGraph 的流程（节点流转、状态更新、
    条件循环）能在零配置下完整跑通，便于理解图的运行机制。
    """

    def __call__(self, messages: list[dict], provider_id: int | None = None) -> str:
        # 用 system 消息判断当前节点意图，比在 user 文本里猜关键字更可靠
        # （否则评审反馈文本里的"评审/边界"等词会干扰生成节点的判断）
        system = ""
        last_user = ""
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content", "")
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break

        # 评审节点的 system 提示里含"评审"，返回打分 JSON
        if "评审" in system or "review" in system.lower():
            return self._mock_review(last_user)

        # 否则视为生成节点，返回一批测试用例 JSON
        return self._mock_generate(last_user)

    @staticmethod
    def _mock_generate(prompt: str) -> str:
        """模拟"生成测试用例"，从需求里抓取一个关键词点缀一下。"""
        feature = "登录"
        # 要求"需求"后紧跟冒号，且只取冒号后到行尾（避免吃进后续的反馈文本）
        m = re.search(r"需求[:：]\s*(.+)", prompt)
        if m:
            feature = m.group(1).splitlines()[0].strip()[:20]

        # 如果 prompt 里带了上一轮的评审反馈，就多生成一条"边界"用例，
        # 以此体现"根据反馈改进"的效果
        improved = "反馈" in prompt or "feedback" in prompt.lower()

        cases = [
            {
                "title": f"{feature}-正常流程",
                "precondition": "用户已注册且账号正常",
                "steps": ["输入正确的账号", "输入正确的密码", "点击提交"],
                "expected": "操作成功，进入主页",
                "priority": "P0",
            },
            {
                "title": f"{feature}-密码错误",
                "precondition": "用户已注册",
                "steps": ["输入正确的账号", "输入错误的密码", "点击提交"],
                "expected": "提示账号或密码错误",
                "priority": "P1",
            },
        ]
        if improved:
            cases.append({
                "title": f"{feature}-边界与异常（依据评审反馈补充）",
                "precondition": "无",
                "steps": ["账号/密码为空", "超长字符串", "特殊字符注入"],
                "expected": "系统给出明确校验提示，不发生异常",
                "priority": "P2",
            })
        return json.dumps({"cases": cases}, ensure_ascii=False)

    @staticmethod
    def _mock_review(prompt: str) -> str:
        """
        模拟"评审"：如果用例里已经包含'边界'相关内容就给高分通过，
        否则给低分并要求补充异常/边界用例（从而触发重新生成的循环）。
        """
        if "边界" in prompt or "异常" in prompt:
            return json.dumps({
                "score": 90,
                "passed": True,
                "feedback": "覆盖了正常、异常与边界场景，通过。",
            }, ensure_ascii=False)
        return json.dumps({
            "score": 60,
            "passed": False,
            "feedback": "缺少边界值和异常场景，请补充。",
        }, ensure_ascii=False)


# 默认导出一个 mock 实例，demo 直接用它
mock_llm = MockLLM()
