"""
意图理解 Agent。

职责：把一句用户自然语言（"帮我测一下登录功能"）解析为结构化的测试意图：

::

    {
        "test_type": "ui" | "api" | "performance",
        "target":    "<被测对象，如 BNP 登录页 / /api/users 接口>",
        "assertions": ["<断言点1>", "<断言点2>", ...],
    }

为什么独立成 Agent
------------------
意图解析是所有后续 Agent 的"分流路标"——决定下一步是调 ``UIScriptAgent``
还是 ``ApiScriptAgent`` 还是 ``PerfAgent``。把它独立出来既是单一职责，
也方便后续接 RAG（按项目历史用例 + Bug 库做更准的意图分类）。

输入 / 输出契约
---------------

- ``state.input_data["requirement"]``  必填，用户原始需求文本
- ``state.input_data["mock"]``         可选，True 时跳过 LLM 直接返回固定结构
- ``state.output_data``                {"test_type", "target", "assertions"}

作者: yandc
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """你是测试意图分析助手。读完用户需求后，**只输出 JSON**，结构如下：

{
  "test_type": "ui" | "api" | "performance",
  "target": "被测对象的精炼描述",
  "assertions": ["断言点1", "断言点2", "..."]
}

判断规则：
- 涉及"页面/按钮/点击/登录界面/表单"→ ui
- 涉及"接口/API/请求/响应/状态码/JSON"→ api
- 涉及"压测/性能/并发/RPS/吞吐"→ performance
- 模糊时默认 ui

不要输出任何解释、前后缀或 markdown 代码块。"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
class IntentAgent(BaseAgent):
    """意图理解 Agent。"""

    name = "intent"
    output_schema = {
        "type": "object",
        "required": ["test_type", "target", "assertions"],
        "properties": {
            "test_type": {"type": "string"},
            "target": {"type": "string"},
            "assertions": {"type": "array"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        requirement = (state.input_data.get("requirement") or "").strip()
        if not requirement:
            raise ValueError("intent_agent: input_data['requirement'] is empty")

        # mock 模式：零 token，方便单测 / 烟雾测试
        if state.input_data.get("mock"):
            state.output_data.update(
                _heuristic_intent(requirement),
            )
            state.metadata["model_used"] = "mock"
            logs.info(
                f"[intent_agent] mock | requirement_len={len(requirement)} "
                f"-> {state.output_data}"
            )
            return state

        # 真实调用：走 ModelRouter（按 routing_rules.yaml 路由到合适层级）
        raw = await self._call_llm(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": requirement},
            ],
            task_type=self.name,
            context={"context_length": len(requirement)},
            temperature=0.0,  # 意图分类要稳定
            max_tokens=512,
            state=state,
        )
        parsed = _extract_json(raw) or _heuristic_intent(requirement)

        state.output_data.update(parsed)
        logs.info(
            f"[intent_agent] llm | requirement_len={len(requirement)} "
            f"-> test_type={parsed.get('test_type')}"
        )
        return state


# ---------------------------------------------------------------------------
# 辅助：JSON 解析 + 关键词兜底
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> dict[str, Any] | None:
    """从 LLM 输出里抠出第一个 JSON 对象，失败返回 None。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _heuristic_intent(requirement: str) -> dict[str, Any]:
    """关键词兜底分类。LLM 不可用时也能给个合理结果。"""
    text = requirement.lower()
    if any(kw in text for kw in ("压测", "性能", "并发", "rps", "吞吐", "performance")):
        test_type = "performance"
    elif any(kw in text for kw in ("接口", "api", "请求", "响应", "状态码")):
        test_type = "api"
    else:
        test_type = "ui"
    return {
        "test_type": test_type,
        "target": requirement[:80],
        "assertions": [],
    }


__all__ = ["IntentAgent"]
