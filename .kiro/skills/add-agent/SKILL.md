---
name: add-agent
description: 在 app/agents/business/ 新增一个业务 Agent（继承 BaseAgent，含 name / output_schema / async _process / mock 模式），并在 business/__init__.py 导出，遵循双词命名 + from __future__ annotations + ModelRouter 路由约定。
---

# 新增业务 Agent

## 何时激活

用户说要"新增 / 加 / 写一个 Agent"，且 Agent 应当落在 `app/agents/business/`。
典型触发词：「加一个 xxx Agent」「写一个意图 / 用例 / 脚本生成 Agent」「新增 LangGraph 节点」。

## 必要输入

确认（缺哪个问哪个）：

- Agent 名称（snake_case，如 `data_seed_agent`）→ 既是 `name` 字段，也是 `routing_rules.yaml` 里的 task_type
- 职责一句话（决定 docstring 和 system prompt）
- 输入契约（`state.input_data` 必填字段）
- 输出契约（`state.output_data` 字段及类型，决定 `output_schema`）
- 是否需要调 LLM（不需要的纯 service 包装可以跳过 `_call_llm`）
- mock 模式产物（必须支持，否则单测烧 token）

## 项目硬约束

1. **文件名双词命名**：`<职责>_<类型>.py`，如 `intent_agent.py` / `api_script_agent.py`，禁止 `utils.py` / `helper.py`。
2. **首行必须** `from __future__ import annotations`（项目所有 agents 模块统一约定，见 `app/agents/README.md` § 4.1）。
3. 类继承 `BaseAgent`（`from app.agents.orchestration import AgentState, BaseAgent`）。
4. **必须实现**两个类属性 + 一个方法：
   - `name: str = "<snake_case>"`（唯一标识，与文件主名对齐）
   - `output_schema: dict[str, Any] = {...}`（轻量 JSON Schema，BaseAgent 会自动校验）
   - `async def _process(self, state: AgentState) -> AgentState`
5. **不要覆盖** `execute()` / `validate_output()` —— 模板方法，BaseAgent 已经处理日志 / 计时 / 不可变字段保护。
6. **必须支持 mock 模式**：`if state.input_data.get("mock"):` 直接返回 fake 数据 + `state.metadata["model_used"] = "mock"`，零 token。
7. 调 LLM 一律用 `await self._call_llm(...)`，**不要** 直连 litellm / openai / dashscope。`_call_llm` 会经过 `ModelRouter` 按 `routing_rules.yaml` 路由。
8. 日志用 `from app.utils.debug import logs`（不要用 `print` 不要用 `logging.getLogger`）。
9. 在 `app/agents/business/__init__.py` 显式 `import` 并加入 `__all__`，外部按 `from app.agents.business import XxxAgent` 引用。

## 实现步骤

### 1. 阅读相邻样例

强制读：
- `app/agents/orchestration/base_agent.py` —— 看模板方法和 `_call_llm` 签名
- `app/agents/business/intent_agent.py` —— 最小可参考实现（含 mock + LLM 双路径）
- `app/agents/business/api_script_agent.py` —— 含 OpenAPI 上下文 + 代码块清洗
- `app/agents/README.md` —— 项目级编码约定

### 2. 写 Agent

新建 `app/agents/business/<name>_agent.py`：

```python
"""
<一句话职责>。

输入 / 输出契约
---------------

- ``state.input_data["<key>"]``    必填，<说明>
- ``state.input_data["mock"]``     可选，True 时跳过 LLM 直接返回固定结构
- ``state.output_data``            {"<field>": ..., ...}

为什么独立成 Agent
------------------
<一两句话讲单一职责，方便后续接 RAG / 替换实现>

作者: yandc
"""
from __future__ import annotations

from typing import Any

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """你是<角色>。读完输入后，**只输出 JSON**，结构：

{
  "<field>": ...
}

判断规则：
- ...

不要输出任何解释、前后缀或 markdown 代码块。"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
class <Name>Agent(BaseAgent):
    """<一句话职责>。"""

    name = "<name>"
    output_schema = {
        "type": "object",
        "required": ["<field>"],
        "properties": {
            "<field>": {"type": "string"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        payload = (state.input_data.get("<key>") or "").strip()
        if not payload:
            raise ValueError("<name>_agent: input_data['<key>'] is empty")

        # mock：零 token，单测 / 烟雾测试用
        if state.input_data.get("mock"):
            state.output_data.update(_mock_result(payload))
            state.metadata["model_used"] = "mock"
            logs.info(f"[<name>_agent] mock | -> {state.output_data}")
            return state

        # 真实调用：走 ModelRouter（按 routing_rules.yaml 路由到合适层级）
        raw = await self._call_llm(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            task_type=self.name,
            context={"context_length": len(payload)},
            temperature=0.0,   # 分类 / 抽取类用 0；生成类用 0.2~0.7
            max_tokens=1024,
            state=state,        # 必传：让 _call_llm 把 model_used / token_count 写回 metadata
        )

        parsed = _parse(raw) or _mock_result(payload)
        state.output_data.update(parsed)
        logs.info(f"[<name>_agent] llm | -> {state.output_data}")
        return state


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def _mock_result(payload: str) -> dict[str, Any]:
    return {"<field>": "mock"}


def _parse(text: str) -> dict[str, Any] | None:
    """从 LLM 输出抠 JSON / 清洗代码块；解析失败返回 None。"""
    import json
    import re
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


__all__ = ["<Name>Agent"]
```

### 3. 在 `__init__.py` 导出

修改 `app/agents/business/__init__.py`：

```python
from app.agents.business.<name>_agent import <Name>Agent

__all__ = [
    # ...
    "<Name>Agent",
]
```

按字母序就近插入。

### 4.（可选）配 routing 规则

如果新 Agent 走 LLM 且复杂度与现有不同，在 `app/agents/config/routing_rules.yaml` 加一条：

```yaml
<name>:
  default_tier: small         # small / medium / large
  complexity_thresholds: ...
```

不配时使用 `routing_rules.yaml` 的 `default` 配置。

### 5. 单跑验证

写一段最小烟雾脚本（**不提交**，验证完删除）：

```python
import asyncio
from app.agents.business import <Name>Agent
from app.agents.orchestration import AgentState

state = AgentState(
    task_id="t1", correlation_id="c1", workflow_id="w1",
    input_data={"<key>": "test", "mock": True},
)
out = asyncio.run(<Name>Agent().execute(state))
print(out.output_data)
```

## 验证

1. mock 模式可跑 + `output_schema` 校验通过（BaseAgent 内部会做）。
2. `from app.agents.business import <Name>Agent` 能 import 不报错。
3. 文件首行是 `from __future__ import annotations`。
4. 不要主动加测试 —— 项目惯例：测试文件由用户明确要求时才补，由 `write-pytest` skill 完成。

## 反模式

- 在 `__init__` / 模块顶层执行重型 import（litellm / playwright）—— 必须延迟到 `_process` 内部。
- 直接 `import openai` 调 LLM —— 绕过 ModelRouter 等于让 `routing_rules.yaml` 失效。
- 修改 `state.task_id` / `state.correlation_id` / `state.workflow_id` —— 不可变字段，BaseAgent 会强制还原但不要主动写。
- 用 `print` —— 项目统一用 `app.utils.debug.logs`。
- 不写 mock 分支 —— 单测会因烧 token 被拒绝合并。
