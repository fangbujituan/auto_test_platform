"""
UI 脚本生成 Agent。

包装根目录 :func:`app.agents.ui_automation_agent.make_agent`（deepagents +
Playwright MCP + Chart MCP）作为内嵌工具。本 Agent 把"打开 deepagents
浏览器自动化"变成 BaseAgent 模板下的一个节点，从而能挂到 DAG 上、获得
统一日志 / 重试 / 状态保护。

输入 / 输出契约
---------------

- ``state.input_data["instruction"]``   必填，给浏览器自动化 agent 的自然语言指令
- ``state.input_data["mock"]``          可选，True 时跳过 MCP 启动直接返回 fake
- ``state.input_data["max_iterations"]`` 可选，限制 deepagents 内部最大轮数
- ``state.output_data["script"]``        生成的 TypeScript 脚本（如有）
- ``state.output_data["messages"]``      deepagents 完整消息流（用于审计）
- ``state.output_data["status"]``        "success" | "failed"

特别说明
--------
``make_agent`` 是异步上下文管理器（要在 ``async with`` 里 yield），本 Agent
负责管理它的生命周期，不让它泄漏 MCP session。

作者: yandc
"""
from __future__ import annotations

from typing import Any

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


class UIScriptAgent(BaseAgent):
    """UI 自动化脚本生成 Agent。"""

    name = "ui_script"
    output_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {
            "status": {"type": "string"},
            "script": {"type": "string"},
            "messages": {"type": "array"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        instruction = (state.input_data.get("instruction") or "").strip()
        if not instruction:
            raise ValueError("ui_script_agent: input_data['instruction'] is empty")

        # mock 模式：不启动 Playwright MCP，直接返回壳
        if state.input_data.get("mock"):
            state.output_data.update({
                "status": "success",
                "script": _MOCK_SCRIPT_TEMPLATE.format(instruction=instruction[:60]),
                "messages": [],
            })
            state.metadata["model_used"] = "mock"
            logs.info(f"[ui_script_agent] mock | instruction_len={len(instruction)}")
            return state

        # 真实调用：启动 deepagents + Playwright MCP
        from app.agents.ui_automation_agent import make_agent as _make_ui_agent

        max_iterations = state.input_data.get("max_iterations", 30)
        async with _make_ui_agent() as ui_agent:
            logs.info(
                f"[ui_script_agent] running deepagents | "
                f"instruction_len={len(instruction)} max_iter={max_iterations}"
            )
            result: dict[str, Any] = await ui_agent.ainvoke(
                {"messages": [{"role": "user", "content": instruction}]},
                config={"recursion_limit": max_iterations},
            )

        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None
        last_text = (
            getattr(last_message, "content", None)
            or (last_message.get("content") if isinstance(last_message, dict) else "")
            or ""
        )

        state.output_data.update({
            "status": "success",
            "script": _extract_typescript(last_text),
            "messages": _serialize_messages(messages),
        })
        state.metadata["model_used"] = "ui_automation_agent"
        logs.info(
            f"[ui_script_agent] done | total_messages={len(messages)} "
            f"script_len={len(state.output_data['script'])}"
        )
        return state


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
_MOCK_SCRIPT_TEMPLATE = """import {{ test, expect }} from '@playwright/test';

// MOCK 脚本：{instruction}
test('mock', async ({{ page }}) => {{
  await page.goto('about:blank');
}});
"""


def _extract_typescript(text: str) -> str:
    """从 LLM 输出里抠出第一段 ```typescript ... ``` 代码块；找不到就原文返回。"""
    import re

    if not text:
        return ""
    m = re.search(r"```(?:typescript|ts)\s*\n(.*?)\n```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def _serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """把 LangChain BaseMessage 列表序列化为可 JSON 化的 dict 列表，便于审计落库。"""
    out: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, dict):
            out.append(msg)
            continue
        out.append({
            "type": getattr(msg, "type", msg.__class__.__name__),
            "content": str(getattr(msg, "content", ""))[:1000],
        })
    return out


__all__ = ["UIScriptAgent"]
