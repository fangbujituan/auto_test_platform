"""
用例落库 Agent。

作用：把 :class:`TestcaseAgent` 产出的结构化用例列表批量写入
``test_case_management`` 表，并把生成的 ``case_ids`` 注入到
``state.input_data['case_ids']``，供下游 :class:`ResultAgent` 使用。

为什么独立成节点
----------------
- TestcaseAgent 只做"生成"（纯 LLM，无 IO 副作用），便于审核闸前
  审核纯净的用例对象
- 审核通过后，由本节点做"落库"（DB 写入，副作用），失败可独立重试
- 把"生成"与"落库"分开，对应 Code Factory 设计文档里"agent 应单一
  职责"的原则

输入 / 输出契约
---------------

- ``state.input_data["project_id"]``    必填，落到哪个项目
- ``state.input_data["module_id"]``     可选
- ``state.input_data["folder_id"]``     可选
- ``state.input_data["mock"]``          True 时跳过实际落库，伪造 case_ids
- ``state.output_data["cases"]``        来自 TestcaseAgent 的用例列表（dict）
- 写出：
  - ``state.output_data["saved_cases"]``  数据库返回的落库结果
  - ``state.output_data["case_ids"]``     批量产生的用例 id 列表
  - ``state.input_data["case_ids"]``      同步注入，供 ResultAgent 直接使用

作者: yandc
"""
from __future__ import annotations

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


class PersistenceAgent(BaseAgent):
    """用例批量落库 Agent。"""

    name = "persistence"
    output_schema = {
        "type": "object",
        "required": ["case_ids", "saved_cases"],
        "properties": {
            "case_ids": {"type": "array"},
            "saved_cases": {"type": "array"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        cases = state.output_data.get("cases") or []
        if not cases:
            raise ValueError("persistence_agent: state.output_data['cases'] 为空")

        project_id = state.input_data.get("project_id")
        if not project_id:
            raise ValueError("persistence_agent: input_data['project_id'] 必填")

        if state.input_data.get("mock"):
            fake_ids = list(range(900_001, 900_001 + len(cases)))
            state.output_data["case_ids"] = fake_ids
            state.output_data["saved_cases"] = [
                {"id": i, "case_no": f"MOCK-{i}", "title": cases[idx].get("title", "")}
                for idx, i in enumerate(fake_ids)
            ]
            state.input_data["case_ids"] = fake_ids
            state.metadata["model_used"] = "mock"
            logs.info(
                f"[persistence_agent] mock | project_id={project_id} "
                f"-> {len(fake_ids)} fake case_ids"
            )
            return state

        # 真实落库：需要 Flask app context + GeneratedTestCase 对象
        from app.services.schemas import GeneratedTestCase
        from app.services.testcase_generator import save_generated_cases

        case_objs = [GeneratedTestCase(**c) for c in cases]
        saved = save_generated_cases(
            case_objs,
            project_id=project_id,
            module_id=state.input_data.get("module_id"),
            folder_id=state.input_data.get("folder_id"),
        )
        case_ids = [s["id"] for s in saved]

        state.output_data["case_ids"] = case_ids
        state.output_data["saved_cases"] = saved
        # 同步注入 input_data，下游 ResultAgent 直接读
        state.input_data["case_ids"] = case_ids
        state.metadata["model_used"] = "db_write"

        logs.info(
            f"[persistence_agent] saved | project_id={project_id} "
            f"-> {len(case_ids)} case_ids"
        )
        return state


__all__ = ["PersistenceAgent"]
