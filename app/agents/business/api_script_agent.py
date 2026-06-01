"""
API 测试脚本 Agent。

把"OpenAPI 文档 / 接口需求"转成可执行的 API 测试脚本。**Step 5 阶段**给
出最简实现：直接调 LLM 生成 Python pytest 风格脚本，下游可挂到执行
引擎跑。

为什么不像 UI 那样跑 deepagents
-------------------------------
API 测试**不需要多轮交互、不需要 DOM 快照**，最经济的方式是一次性 LLM
生成完整脚本然后丢给执行引擎跑。token 消耗约为 UI Agent 的 1/10–1/20，
这正是 token 紧张时优先扩张 API 自动化的核心理由。

输入 / 输出契约
---------------

- ``state.input_data["instruction"]``    必填，自然语言任务描述
- ``state.input_data["openapi_url"]``    可选，目标接口的 OpenAPI 文档 URL
- ``state.input_data["sample_endpoint"]`` 可选，提供给 LLM 的示例端点
- ``state.input_data["mock"]``           True 时返回壳脚本，零 token
- ``state.output_data["script"]``        生成的 Python 脚本字符串
- ``state.output_data["language"]``      ``"python"``（未来支持 typescript）
- ``state.output_data["status"]``        "success" | "failed"

作者: yandc
"""
from __future__ import annotations

import re

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


_SYSTEM_PROMPT = """你是 API 自动化测试专家。你只输出可直接 ``python -m pytest`` 运行的脚本，
不要任何说明文字、不要 markdown 代码块标记。

## 脚本结构要求

```
import pytest
import requests

BASE_URL = "..."

def test_<场景名>():
    resp = requests.<method>(...)
    assert resp.status_code == ...
    body = resp.json()
    assert body[...] == ...
```

## 设计原则

- 每个测试场景一个 ``test_`` 函数；正常 + 边界 + 异常各一条
- 状态码、关键字段值都要断言；不要只断 200
- 用 ``BASE_URL`` 常量便于切环境
- 不引入除 ``requests`` / ``pytest`` 之外的第三方依赖
"""


_MOCK_SCRIPT = '''import pytest
import requests

BASE_URL = "http://example.com"

def test_mock_normal():
    """MOCK: {instruction}"""
    resp = requests.get(BASE_URL)
    assert resp.status_code == 200
'''


class ApiScriptAgent(BaseAgent):
    """API 自动化脚本生成 Agent。"""

    name = "api_script"
    output_schema = {
        "type": "object",
        "required": ["status", "script", "language"],
        "properties": {
            "status": {"type": "string"},
            "script": {"type": "string"},
            "language": {"type": "string"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        # 兼容两种入参：
        # - 单跑场景：``input_data["instruction"]``
        # - 工作流场景：``input_data["requirement"]``（与 IntentAgent 共享）
        instruction = (
            state.input_data.get("instruction")
            or state.input_data.get("requirement")
            or ""
        ).strip()
        if not instruction:
            raise ValueError(
                "api_script_agent: 需要 input_data['instruction'] 或 input_data['requirement']"
            )

        if state.input_data.get("mock"):
            state.output_data.update({
                "status": "success",
                "script": _MOCK_SCRIPT.format(instruction=instruction[:60]),
                "language": "python",
            })
            state.metadata["model_used"] = "mock"
            logs.info(f"[api_script_agent] mock | instruction_len={len(instruction)}")
            return state

        # 真实调用：组装上下文 -> _call_llm（按 routing_rules.yaml 路由）
        user_message_parts = [f"任务：{instruction}"]
        if openapi_url := state.input_data.get("openapi_url"):
            user_message_parts.append(f"\nOpenAPI 文档：{openapi_url}")
        if sample := state.input_data.get("sample_endpoint"):
            user_message_parts.append(f"\n示例端点：\n{sample}")
        user_message = "\n".join(user_message_parts)

        raw = await self._call_llm(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            task_type=self.name,
            context={"context_length": len(user_message)},
            temperature=0.2,
            max_tokens=2048,
            state=state,
        )
        script = _strip_code_fence(raw)

        state.output_data.update({
            "status": "success",
            "script": script,
            "language": "python",
        })
        logs.info(
            f"[api_script_agent] llm | instruction_len={len(instruction)} "
            f"-> script_len={len(script)}"
        )
        return state


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def _strip_code_fence(text: str) -> str:
    """如果 LLM 仍然套了 markdown 代码块，去掉外面那层。"""
    if not text:
        return ""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


__all__ = ["ApiScriptAgent"]
