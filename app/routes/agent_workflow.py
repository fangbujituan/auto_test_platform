"""
Agent 工作流 API 路由。

把 ``app.agents.workflows`` 下的工作流暴露为 HTTP 端点。**Step 3 阶段**
开放完整 e2e：测试用例生成（intent → testcase → review_gate →
persistence → result）。

为什么不直接调 service
----------------------
路由层只做"工作流调度入口"，不感知 Agent 内部细节，便于：
- 工作流定义升级（加节点 / 加审核闸）时路由零改动
- 统一从 BaseAgent + Orchestrator 拿到调用日志、不可变字段保护、重试

作者: yandc
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from flask import g, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from app.agents.orchestration import AgentState
from app.agents.workflows import build_testcase_generation_orchestrator
from app.schemas.common import MessageResponseSchema
from app.utils.debug import logs
from app.utils.permission import login_required


agent_workflow_blp = Blueprint(
    "agent_workflow",
    __name__,
    url_prefix="/api/agent/workflow",
    description="Agent 工作流执行接口（DAG 编排 + Human-in-the-Loop）",
)


# ============================================================================
# Schema
# ============================================================================

class TestcaseWorkflowRunSchema(Schema):
    """``POST /api/agent/workflow/testcase-generation`` 请求体。"""

    requirement = fields.String(
        required=True,
        metadata={"description": "需求描述（必填）"},
    )
    project_id = fields.Integer(
        required=False,
        load_default=None,
        metadata={"description": "项目 ID（落库 + 落 bug 必填；不传时强制 mock 模式）"},
    )
    module_id = fields.Integer(
        required=False, load_default=None,
        metadata={"description": "落库时的模块 id（可选）"},
    )
    folder_id = fields.Integer(
        required=False, load_default=None,
        metadata={"description": "落库时的目录 id（可选）"},
    )
    skip_result = fields.Boolean(
        required=False, load_default=False,
        metadata={"description": "True 表示只生成 + 落库，不触发执行"},
    )
    create_bug_on_failure = fields.Boolean(
        required=False, load_default=True,
        metadata={"description": "失败用例是否自动建 bug，默认 True"},
    )
    environment = fields.String(
        required=False, load_default=None,
        metadata={"description": "测试环境名（写入 bug.environment）"},
    )
    version = fields.String(
        required=False, load_default=None,
        metadata={"description": "发现版本号（写入 bug.version）"},
    )
    model = fields.String(
        required=False, load_default=None,
        metadata={"description": "LLM 模型标识，覆盖默认模型"},
    )
    extra_context = fields.String(
        required=False, load_default=None,
        metadata={"description": "附加上下文"},
    )
    # 审核相关
    mock_review = fields.Boolean(
        required=False, load_default=True,
        metadata={
            "description": (
                "True 时审核闸自动通过；前端审核 UI 接通后改为 False，"
                "由 review_decision 显式决定"
            ),
        },
    )
    review_decision = fields.String(
        required=False, load_default=None,
        metadata={"description": "审核决策（approved / rejected），优先级高于 mock_review"},
    )
    # 调试
    mock = fields.Boolean(
        required=False, load_default=False,
        metadata={"description": "True 时整条链路 mock，零 token + 不写 DB"},
    )


# ============================================================================
# Routes
# ============================================================================

@agent_workflow_blp.route("/testcase-generation")
class TestcaseWorkflowView(MethodView):
    """测试用例生成 e2e 工作流：intent → testcase → review → persist → result。"""

    @agent_workflow_blp.arguments(TestcaseWorkflowRunSchema)
    @agent_workflow_blp.response(200, MessageResponseSchema)
    @agent_workflow_blp.alt_response(
        500, schema=MessageResponseSchema, description="工作流执行失败"
    )
    @login_required
    def post(self, args: dict[str, Any]):
        """启动用例生成 + 执行的完整工作流。"""
        requirement = (args.get("requirement") or "").strip()
        if not requirement:
            return jsonify({"code": 1, "message": "requirement 不能为空"}), 400

        # 没传 project_id 时强制 mock，避免 persistence/result 阶段报错
        project_id = args.get("project_id")
        is_mock = bool(args.get("mock") or not project_id)

        # 自动 bug 报告人 = 当前登录用户
        reporter_id = None
        current_user = g.get("current_user")
        if current_user is not None:
            reporter_id = getattr(current_user, "id", None)

        correlation_id = f"wf-{uuid.uuid4().hex[:12]}"
        state = AgentState(
            task_id=f"task-{int(time.time() * 1000)}",
            correlation_id=correlation_id,
            workflow_id=f"testcase_generation-{correlation_id}",
            input_data={
                "requirement": requirement,
                "project_id": project_id,
                "module_id": args.get("module_id"),
                "folder_id": args.get("folder_id"),
                "model": args.get("model"),
                "extra_context": args.get("extra_context"),
                "mock": is_mock,
                "mock_review": args.get("mock_review", True),
                "review_decision": args.get("review_decision"),
                "skip_result": args.get("skip_result", False),
                "create_bug_on_failure": args.get("create_bug_on_failure", True),
                "reporter_id": reporter_id,
                "environment": args.get("environment") or "",
                "version": args.get("version") or "",
            },
        )

        try:
            orch = build_testcase_generation_orchestrator()
            final_state = asyncio.run(
                orch.run_workflow("testcase_generation", state)
            )

            return jsonify({
                "code": 0,
                "data": {
                    "correlation_id": correlation_id,
                    "workflow_status": final_state.metadata.get("workflow_status"),
                    "output": final_state.output_data,
                    "history": final_state.history,
                    "invocation_logs": [
                        {
                            "agent_name": log.agent_name,
                            "status": log.status,
                            "model_used": log.model_used,
                            "token_count": log.token_count,
                            "latency_ms": log.latency_ms,
                        }
                        for log in orch.get_invocation_logs()
                    ],
                },
            })

        except Exception as e:  # noqa: BLE001
            logs.error(
                f"[agent_workflow] testcase_generation failed | "
                f"correlation_id={correlation_id} error={e}"
            )
            return jsonify({"code": 1, "message": f"工作流执行失败: {e}"}), 500
