"""
测试用例生成 Agent。

包装 :func:`app.services.testcase_generator.generate_test_cases_with_db_prompt`，
把它变成一个可以挂到 DAG 上的节点。

输入 / 输出契约
---------------

- ``state.input_data["requirement"]``    必填，需求描述
- ``state.input_data["test_type"]``      可选，由上游 IntentAgent 注入
- ``state.input_data["model"]``          可选，覆盖默认 LLM
- ``state.input_data["extra_context"]``  可选，附加上下文
- ``state.input_data["mock"]``           可选，True 时返回 1 条 fake 用例不烧 token
- ``state.output_data``                  ``{"cases": [...], "summary": str, "case_count": int}``

不在本 Agent 内做的事
---------------------
- **不落库**：本 Agent 只产出用例对象。落库通过 ``ResultAgent`` 或人工
  审核（ReviewGate）后由后续节点完成，避免审核未通过就脏数据写库。

作者: yandc
"""
from __future__ import annotations

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


class TestcaseAgent(BaseAgent):
    """测试用例生成 Agent。"""

    name = "testcase"
    output_schema = {
        "type": "object",
        "required": ["cases", "summary", "case_count"],
        "properties": {
            "case_count": {"type": "integer"},
            "summary": {"type": "string"},
            "cases": {"type": "array"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        requirement = (state.input_data.get("requirement") or "").strip()
        if not requirement:
            raise ValueError("testcase_agent: input_data['requirement'] is empty")

        # mock 模式
        if state.input_data.get("mock"):
            fake_case = {
                "title": f"{requirement[:30]}-正常流程",
                "precondition": "无",
                "steps": "1. 打开页面\n2. 提交",
                "expected_result": "操作成功",
                "priority": "P1",
                "case_type": "功能",
                "description": "",
            }
            state.output_data.update({
                "cases": [fake_case],
                "summary": f"mock 模式生成 1 条用例（{requirement[:30]}）",
                "case_count": 1,
            })
            state.metadata["model_used"] = "mock"
            logs.info(f"[testcase_agent] mock | requirement_len={len(requirement)}")
            return state

        # 真实调用：走 service
        from app.services.testcase_generator import (
            generate_test_cases_with_db_prompt,
        )

        result = generate_test_cases_with_db_prompt(
            requirement=requirement,
            model=state.input_data.get("model"),
            extra_context=state.input_data.get("extra_context"),
            agent_name=self.name,
        )

        state.output_data.update({
            "cases": [c.model_dump() for c in result.cases],
            "summary": result.summary,
            "case_count": result.case_count,
        })
        state.metadata["model_used"] = result.model
        logs.info(
            f"[testcase_agent] llm | requirement_len={len(requirement)} "
            f"-> {result.case_count} cases"
        )
        return state


__all__ = ["TestcaseAgent"]
