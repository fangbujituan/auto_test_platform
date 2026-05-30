"""
执行用例 / 报 bug 相关的 Agent 工具。

把 ``app.services.case_runner`` 包成 LangChain ``@tool``：
- UI Agent / 录制 Agent 内部可装载（"刚生成的用例顺便跑一下"）
- MCP Server 转发为 MCP tool（外部 IDE Agent 触发回归）
"""

from __future__ import annotations

from typing import List, Optional

from langchain_core.tools import tool

from app.services.case_runner import execute_cases


@tool
def run_test_cases(
    case_ids: List[int],
    project_id: int,
    create_bug_on_failure: bool = True,
    reporter_id: Optional[int] = None,
    environment: Optional[str] = None,
    version: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """执行一批测试用例，失败自动建 bug。

    用例由 LLM 当裁判判断 pass/fail（飞轮 v1 实现）。失败用例会自动写入
    ``bugs`` 表，并把 ``related_test_cases`` 关联回用例 id。

    Args:
        case_ids: 待执行的用例 id 列表（``test_case_management.id``）
        project_id: 落 bug 的项目 id
        create_bug_on_failure: 失败时是否自动建 bug（默认是）
        reporter_id: 自动 bug 的报告人 id（可选）
        environment: 测试环境名（写入 bug 字段）
        version: 发现版本号（写入 bug 字段）
        model: 裁判 LLM 模型（如 ``local/llama3.2-1b``）

    Returns:
        ``{"total","passed","failed","blocked","skipped","bug_ids","results":[...]}``
    """
    # 工具被 Agent 调用时仍需要 Flask app context（落库）
    from app import create_app

    app = create_app()
    with app.app_context():
        report = execute_cases(
            case_ids=case_ids,
            project_id=project_id,
            create_bug_on_failure=create_bug_on_failure,
            reporter_id=reporter_id,
            environment=environment or "",
            version=version or "",
            model=model,
        )
    return report.to_dict()


RUN_TOOLS = [run_test_cases]


__all__ = ["run_test_cases", "RUN_TOOLS"]
