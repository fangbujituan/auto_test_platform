"""
执行结果解析 + 自动建 bug Agent。

包装 :func:`app.services.case_runner.execute_cases`，把"用例 id 列表 → 执行
报告 + bug id 列表"封装成一个 DAG 节点。

输入 / 输出契约
---------------

- ``state.input_data["case_ids"]``               必填，待执行用例 id 列表
- ``state.input_data["project_id"]``             必填
- ``state.input_data["create_bug_on_failure"]``  可选，默认 True
- ``state.input_data["reporter_id"]``            可选，自动 bug 报告人
- ``state.input_data["environment"]``            可选
- ``state.input_data["version"]``                可选
- ``state.input_data["mock"]``                   可选，True 时跳过实际执行
- ``state.output_data``                          ``CaseRunReport.to_dict()`` 结果

作者: yandc
"""
from __future__ import annotations

from app.agents.orchestration import AgentState, BaseAgent
from app.utils.debug import logs


class ResultAgent(BaseAgent):
    """执行 + 结果解析 + 自动建 bug Agent。"""

    name = "result"
    output_schema = {
        "type": "object",
        "required": ["project_id", "total", "passed", "failed"],
        "properties": {
            "project_id": {"type": "integer"},
            "total": {"type": "integer"},
            "passed": {"type": "integer"},
            "failed": {"type": "integer"},
            "blocked": {"type": "integer"},
            "skipped": {"type": "integer"},
            "bug_ids": {"type": "array"},
            "results": {"type": "array"},
        },
    }

    async def _process(self, state: AgentState) -> AgentState:
        case_ids = state.input_data.get("case_ids") or []
        project_id = state.input_data.get("project_id")

        if not case_ids:
            raise ValueError("result_agent: input_data['case_ids'] is empty")
        if not project_id:
            raise ValueError("result_agent: input_data['project_id'] is required")

        if state.input_data.get("mock"):
            state.output_data.update({
                "project_id": project_id,
                "total": len(case_ids),
                "passed": len(case_ids),
                "failed": 0,
                "blocked": 0,
                "skipped": 0,
                "bug_ids": [],
                "results": [
                    {
                        "case_id": cid,
                        "case_no": f"MOCK-{cid}",
                        "title": "mock",
                        "status": "passed",
                        "actual_result": "",
                        "error_message": "",
                        "duration_seconds": 0.0,
                        "bug_id": None,
                    }
                    for cid in case_ids
                ],
            })
            state.metadata["model_used"] = "mock"
            logs.info(f"[result_agent] mock | case_count={len(case_ids)}")
            return state

        # 真实执行：要求调用方已经在 Flask app context 内
        from app.services.case_runner import execute_cases

        report = execute_cases(
            case_ids=case_ids,
            project_id=project_id,
            create_bug_on_failure=state.input_data.get(
                "create_bug_on_failure", True
            ),
            reporter_id=state.input_data.get("reporter_id"),
            environment=state.input_data.get("environment", ""),
            version=state.input_data.get("version", ""),
            model=state.input_data.get("model"),
        )

        state.output_data.update(report.to_dict())
        state.metadata["model_used"] = state.input_data.get("model") or "default"
        logs.info(
            f"[result_agent] done | total={report.total} "
            f"passed={report.passed} failed={report.failed} "
            f"bugs={len(report.bug_ids)}"
        )
        return state


__all__ = ["ResultAgent"]
