"""
浏览器录制回放 Agent（业务层包装）。

> 命名说明
>
> - 根目录 ``app.agents.recording_agent`` 是底层 deepagents 工厂
>   （``make_recording_agent``，提供 LangGraph Pregel 实例）
> - 本文件 ``app.agents.business.recording_agent`` 是 BaseAgent 子类，
>   把那个工厂包装成 DAG 节点
>
> 两者通过完整包路径区分，调用方不会混淆。

输入 / 输出契约
---------------

- ``state.input_data["instruction"]``  必填，给录制 agent 的自然语言指令
- ``state.input_data["mock"]``         可选，True 时跳过 Playwright MCP 直接返回 fake
- ``state.output_data["status"]``      "success" | "failed"
- ``state.output_data["script_name"]``  保存的脚本名（如有）
- ``state.output_data["messages"]``    序列化后的消息流

作者: yandc
"""
from __future__ import annotations

from typing import Any

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


class RecordingAgent(BaseAgent):
    """浏览器录制 Agent（业务层）。"""

    name = "recording"
    output_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {
            "status": {"type": "string"},
            "script_name": {"type": "string"},
            "messages": {"type": "array"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        instruction = (state.input_data.get("instruction") or "").strip()
        if not instruction:
            raise ValueError("recording_agent: input_data['instruction'] is empty")

        if state.input_data.get("mock"):
            state.output_data.update({
                "status": "success",
                "script_name": "mock_recording",
                "messages": [],
            })
            state.metadata["model_used"] = "mock"
            logs.info(f"[recording_agent] mock | instruction_len={len(instruction)}")
            return state

        # 真实调用：使用根目录工厂打开 deepagents + Playwright MCP（带登录态）
        from app.agents.recording_agent import (
            make_recording_agent as _make_recording_agent,
        )

        max_iterations = state.input_data.get("max_iterations", 40)
        async with _make_recording_agent() as recording:
            logs.info(
                f"[recording_agent] running | "
                f"instruction_len={len(instruction)} max_iter={max_iterations}"
            )
            result: dict[str, Any] = await recording.ainvoke(
                {"messages": [{"role": "user", "content": instruction}]},
                config={"recursion_limit": max_iterations},
            )

        messages = result.get("messages", [])
        state.output_data.update({
            "status": "success",
            "script_name": _guess_script_name(messages),
            "messages": _serialize_messages(messages),
        })
        state.metadata["model_used"] = "recording_agent"
        logs.info(f"[recording_agent] done | total_messages={len(messages)}")
        return state


# ---------------------------------------------------------------------------
# 辅助：尝试从 agent 消息流里抠出脚本名（如有 save_current_recording 调用）
# ---------------------------------------------------------------------------
def _guess_script_name(messages: list[Any]) -> str:
    """从 agent 输出里找 save_current_recording 的脚本名。"""
    import re

    for msg in messages:
        text = (
            getattr(msg, "content", None)
            or (msg.get("content") if isinstance(msg, dict) else "")
            or ""
        )
        m = re.search(r"名称[:：]\s*([\w\-]+)", str(text))
        if m:
            return m.group(1)
    return ""


def _serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
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


__all__ = ["RecordingAgent"]
