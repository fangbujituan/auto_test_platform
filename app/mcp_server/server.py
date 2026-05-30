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

from app.services.testcase_generator import (
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

    return mcp


__all__ = ["create_mcp_server"]
