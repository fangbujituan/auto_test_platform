"""
平台 MCP Server 实现。

把核心能力封装成 MCP tool，供外部 Agent 调用。

当前已暴露的能力：
- ``ai_generate_test_cases``  从需求生成测试用例（不落库）
- ``ai_generate_and_save_test_cases``  生成并落库到指定项目
- ``ping``  健康检查

后续可继续追加：``run_test_case``、``create_bug``、``query_test_result`` 等。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from app.services.case_runner import execute_cases
from app.services.testcase_generator import (
    ai_chat,
    generate_test_cases_with_db_prompt,
    save_generated_cases,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 平台 MCP Server 工厂
# ============================================================================

def create_mcp_server(name: str = "auto-test-platform") -> FastMCP:
    """构建平台 MCP Server 实例。

    Args:
        name: MCP Server 名称，外部 Agent 看到的服务名

    Returns:
        ``FastMCP`` 实例，调用方可继续 ``.run(transport=...)``
    """
    mcp = FastMCP(name)

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    @mcp.tool(description="健康检查，返回 MCP Server 运行状态")
    def ping() -> Dict[str, Any]:
        """检查 MCP Server 是否在线。"""
        return {"status": "ok", "server": name}

    # ------------------------------------------------------------------
    # 极简 LLM 转发（流程验证 / 通用问答）
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "最简单的 LLM 问答工具：问什么答什么，不做结构化约束。"
            "适用场景：流程验证（如 1+1=?）、简单代码探讨、给外部 Agent 借用本平台 LLM。"
            "不需要数据库、不需要 Flask app context。"
        )
    )
    def ai_chat_simple(
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """问答转发。

        Args:
            prompt: 用户问题（必填）
            model: LLM 模型标识，如 ``local/llama3.2-1b``
            system: 自定义 system 提示词（可选）
        """
        answer = ai_chat(prompt=prompt, model=model, system=system, agent_name="mcp_chat")
        return {"answer": answer, "model": model or "default"}

    # ------------------------------------------------------------------
    # 测试用例生成（不落库）
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "根据需求描述生成结构化测试用例列表。"
            "用例覆盖正常流程 / 边界条件 / 异常场景三类，"
            "每条包含 title / precondition / steps / expected_result / priority / case_type。"
            "**仅返回**生成结果，不写数据库。需要落库请用 ai_generate_and_save_test_cases。"
        )
    )
    def ai_generate_test_cases(
        requirement: str,
        model: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成测试用例。

        Args:
            requirement: 需求描述（必填）
            model: LLM 模型，如 ``local/llama3.2-1b`` / ``aiop/azure/gpt-5.4``
            extra_context: 附加上下文
        """
        result = generate_test_cases_with_db_prompt(
            requirement=requirement,
            model=model,
            extra_context=extra_context,
            agent_name="mcp_server",
        )
        return {
            "case_count": result.case_count,
            "summary": result.summary,
            "model": result.model,
            "cases": [c.model_dump() for c in result.cases],
        }

    # ------------------------------------------------------------------
    # 测试用例生成 + 落库（飞轮闭环关键）
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "根据需求描述生成测试用例，并自动落库到指定项目的 test_case_management 表。"
            "返回值中的 saved_cases 包含每条用例的 id 和 case_no（如 TC-1-001），"
            "外部 Agent 可用这些 ID 触发后续的执行 / bug 跟踪流程。"
        )
    )
    def ai_generate_and_save_test_cases(
        requirement: str,
        project_id: int,
        module_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        model: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成并落库测试用例。

        Args:
            requirement: 需求描述（必填）
            project_id: 项目 ID（必填，对应 ``projects`` 表）
            module_id: 模块 ID（可选）
            folder_id: 目录 ID（可选）
            model: LLM 模型
            extra_context: 附加上下文
        """
        # 落库需要 Flask app context（ORM）
        from app import create_app

        result = generate_test_cases_with_db_prompt(
            requirement=requirement,
            model=model,
            extra_context=extra_context,
            agent_name="mcp_server",
        )

        app = create_app()
        with app.app_context():
            saved = save_generated_cases(
                result.cases,
                project_id=project_id,
                module_id=module_id,
                folder_id=folder_id,
            )

        return {
            "case_count": result.case_count,
            "summary": result.summary,
            "model": result.model,
            "saved_cases": saved,
        }

    # ------------------------------------------------------------------
    # 飞轮第二齿轮：执行用例 + 失败建 bug
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "批量执行测试用例（按 id），失败自动建 bug 写入 bugs 表。"
            "v1 由 LLM 当裁判判断 pass/fail；后续可替换为真实 Playwright/HTTP 执行器。"
            "返回每条用例的执行结果与生成的 bug id，外部 Agent 可据此触发后续流转。"
        )
    )
    def run_test_cases(
        case_ids: List[int],
        project_id: int,
        create_bug_on_failure: bool = True,
        reporter_id: Optional[int] = None,
        environment: Optional[str] = None,
        version: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行用例并按需建 bug。"""
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

    # ------------------------------------------------------------------
    # 平台数据查询工具（让外部 Agent 能直接读 ATP 数据，无需走 HTTP）
    # ------------------------------------------------------------------
    @mcp.tool(
        description=(
            "查询某项目下的接口（API）列表。"
            "返回每个接口的 id / name / method / path / module / service / "
            "headers / params / body 等完整定义，"
            "供外部 Agent 生成 API 测试脚本或做覆盖度分析时使用。"
        )
    )
    def query_apis(
        project_id: int,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按项目 + 关键字分页查询接口。"""
        from app import create_app
        from app.models.api import Api

        app = create_app()
        with app.app_context():
            query = Api.query.filter_by(project_id=project_id, status=1)
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(
                    (Api.name.like(like))
                    | (Api.path.like(like))
                    | (Api.description.like(like))
                )
            total = query.count()
            items = (
                query.order_by(Api.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [a.to_dict() for a in items],
            }

    @mcp.tool(
        description=(
            "查询某项目下的测试用例列表。"
            "返回每条用例的 case_no / title / steps / expected_result / "
            "priority / case_type / case_status 等。"
            "外部 Agent 可用于复用已有用例、做覆盖度盘点或基于历史用例生成新用例。"
        )
    )
    def query_test_cases(
        project_id: int,
        keyword: Optional[str] = None,
        priority: Optional[str] = None,
        case_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按项目 + 关键字 + 优先级 + 状态分页查询用例。"""
        from app import create_app
        from app.models.test_case import TestCaseManagement

        app = create_app()
        with app.app_context():
            query = TestCaseManagement.query.filter_by(project_id=project_id, status=1)
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(
                    (TestCaseManagement.title.like(like))
                    | (TestCaseManagement.case_no.like(like))
                )
            if priority:
                query = query.filter(TestCaseManagement.priority == priority)
            if case_status:
                query = query.filter(TestCaseManagement.case_status == case_status)
            total = query.count()
            items = (
                query.order_by(TestCaseManagement.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [c.to_dict() for c in items],
            }

    @mcp.tool(
        description=(
            "查询某项目下的 Bug 列表。"
            "返回每条 bug 的 title / status / severity / priority / "
            "steps_to_reproduce / actual_result / expected_result 等。"
            "外部 Agent 可用于做缺陷分析、回归测试设计、质量评估等。"
        )
    )
    def query_bugs(
        project_id: int,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按项目 + 状态 + 严重度 + 关键字分页查询 bug。"""
        from app import create_app
        from app.models.bug import Bug

        app = create_app()
        with app.app_context():
            query = Bug.query.filter_by(project_id=project_id)
            if status:
                query = query.filter(Bug.status == status)
            if severity:
                query = query.filter(Bug.severity == severity)
            if keyword:
                like = f"%{keyword}%"
                query = query.filter(
                    (Bug.title.like(like)) | (Bug.description.like(like))
                )
            total = query.count()
            items = (
                query.order_by(Bug.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [b.to_dict() for b in items],
            }

    @mcp.tool(
        description=(
            "查询某项目下的需求列表。"
            "返回每条需求的 title / description / status / priority / "
            "sprint_id / tags 等。"
            "外部 Agent 可用于做需求 -> 用例 -> bug 的串联分析。"
        )
    )
    def query_requirements(
        project_id: int,
        status: Optional[str] = None,
        sprint_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按项目 + 状态 + 冲刺分页查询需求。"""
        from app import create_app
        from app.models.requirement import Requirement

        app = create_app()
        with app.app_context():
            query = Requirement.query.filter_by(project_id=project_id)
            if status:
                query = query.filter(Requirement.status == status)
            if sprint_id is not None:
                query = query.filter(Requirement.sprint_id == sprint_id)
            total = query.count()
            items = (
                query.order_by(Requirement.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [r.to_dict() for r in items],
            }

    @mcp.tool(
        description=(
            "查询某项目下的执行结果列表。"
            "返回每条结果的 case_id / status / actual_result / "
            "duration / executed_at 等。"
            "外部 Agent 可用于做质量趋势分析、回归判定等。"
        )
    )
    def query_test_results(
        project_id: int,
        case_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按项目 + 用例 + 状态分页查询执行结果。"""
        from app import create_app
        from app.models.result import TestResult

        app = create_app()
        with app.app_context():
            query = TestResult.query
            if hasattr(TestResult, "project_id"):
                query = query.filter(TestResult.project_id == project_id)
            if case_id is not None:
                query = query.filter(TestResult.case_id == case_id)
            if status:
                query = query.filter(TestResult.status == status)
            total = query.count()
            items = (
                query.order_by(TestResult.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            # TestResult 不一定有 to_dict，做最小兼容
            def _to_dict(r):
                if hasattr(r, "to_dict"):
                    return r.to_dict()
                return {
                    "id": getattr(r, "id", None),
                    "case_id": getattr(r, "case_id", None),
                    "status": getattr(r, "status", None),
                    "actual_result": getattr(r, "actual_result", None),
                }

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_to_dict(r) for r in items],
            }

    return mcp


__all__ = ["create_mcp_server"]
