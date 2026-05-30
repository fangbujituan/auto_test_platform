"""
AI Agent API 路由。

为前端 / 外部调用方提供 LangGraph Agent 与 AI Service 的 HTTP 入口：

- ``POST /api/ai/agent/ui``           UI 自动化主 Agent
- ``POST /api/ai/agent/recording``    录制回放 Agent
- ``POST /api/ai/agent/generate-cases`` 测试用例生成（飞轮起点）
- ``GET  /api/ai/agent/info``          Agent 元信息

每次 Agent 请求会启动一组全新的 Playwright MCP 会话，处理完毕自动释放。
单次 ``invoke`` 同步返回（不做流式），如需流式后续可挂 SSE。

作者: yandc
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from app.agents.recording_agent import make_recording_agent
from app.agents.ui_automation_agent import make_agent as make_ui_agent
from app.schemas.common import MessageResponseSchema
from app.services.case_runner import execute_cases
from app.services.testcase_generator import (
    ai_chat,
    generate_test_cases_with_db_prompt,
    save_generated_cases,
)
from app.utils.debug.readlog import logs
from app.utils.permission import login_required


ai_agent_blp = Blueprint(
    "ai_agent",
    __name__,
    url_prefix="/api/ai/agent",
    description="AI Agent（基于 LangGraph + deepagents）执行接口",
)


# ============================================================================
# 请求 / 响应 Schema
# ============================================================================

class AgentMessageSchema(Schema):
    """单条对话消息。"""

    role = fields.String(
        required=True,
        validate=validate.OneOf(["system", "user", "assistant", "tool"]),
        metadata={"description": "消息角色"},
    )
    content = fields.String(required=True, metadata={"description": "消息内容"})


class AgentInvokeRequestSchema(Schema):
    """Agent 调用请求体。"""

    messages = fields.List(
        fields.Nested(AgentMessageSchema),
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "对话消息列表（至少一条 user 消息）"},
    )
    thread_id = fields.String(
        load_default=None,
        metadata={"description": "LangGraph thread_id，用于跨调用追踪（可选）"},
    )
    recursion_limit = fields.Integer(
        load_default=50,
        validate=validate.Range(min=1, max=200),
        metadata={"description": "Agent 单次执行的最大递归步数，默认 50"},
    )


# ============================================================================
# 辅助函数
# ============================================================================

def _validate_messages(messages: List[Dict[str, Any]]) -> bool:
    """校验消息列表至少有一条非空内容。"""
    return bool(messages) and any(
        (msg.get("content") or "").strip() for msg in messages
    )


def _serialize_messages(raw_messages: Any) -> List[Dict[str, Any]]:
    """把 LangChain BaseMessage 序列化为前端友好的字典列表。"""
    out: List[Dict[str, Any]] = []
    for msg in raw_messages or []:
        # LangChain 1.x 的 BaseMessage 有 .type 与 .content
        msg_type = getattr(msg, "type", None) or getattr(msg, "role", None) or "unknown"
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            msg_type = msg.get("role") or msg.get("type") or "unknown"
            content = msg.get("content")

        item: Dict[str, Any] = {"role": msg_type, "content": content}

        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            item["tool_calls"] = tool_calls

        name = getattr(msg, "name", None)
        if name:
            item["name"] = name
        out.append(item)
    return out


async def _run_agent(agent_factory, payload: Dict[str, Any]) -> Dict[str, Any]:
    """统一执行 Agent 的入口。负责会话生命周期与序列化。"""
    state_input = {"messages": payload["messages"]}
    config: Dict[str, Any] = {
        "recursion_limit": payload.get("recursion_limit", 50),
    }
    if payload.get("thread_id"):
        config["configurable"] = {"thread_id": payload["thread_id"]}

    async with agent_factory() as agent:
        final_state = await agent.ainvoke(state_input, config=config)

    messages = _serialize_messages(final_state.get("messages") if isinstance(final_state, dict) else None)
    return {
        "messages": messages,
        "message_count": len(messages),
    }


def _execute(agent_factory, json_data: Dict[str, Any]):
    """同步包装：让 Flask 视图能调用异步 Agent。"""
    if not _validate_messages(json_data.get("messages", [])):
        return jsonify({"code": 400, "message": "messages 不能为空"}), 400

    try:
        result = asyncio.run(_run_agent(agent_factory, json_data))
    except Exception as e:
        logs.error(f"[ai_agent] Agent 执行失败: {e}", exc_info=True)
        return jsonify({"code": 500, "message": f"Agent 执行失败: {e}"}), 500

    return jsonify({"code": 0, "message": "success", "data": result})


# ============================================================================
# 视图
# ============================================================================

@ai_agent_blp.route("/ui")
class UIAutomationAgentView(MethodView):
    """UI 自动化主 Agent（Playwright + Chart MCP）。"""

    @ai_agent_blp.arguments(AgentInvokeRequestSchema)
    @ai_agent_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """触发一次 UI 自动化 Agent 执行。"""
        return _execute(make_ui_agent, json_data)


@ai_agent_blp.route("/recording")
class RecordingAgentView(MethodView):
    """录制回放 Agent（含脚本生成 / 保存 / 列表能力）。"""

    @ai_agent_blp.arguments(AgentInvokeRequestSchema)
    @ai_agent_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """触发一次录制回放 Agent 执行。"""
        return _execute(make_recording_agent, json_data)


@ai_agent_blp.route("/info")
class AgentInfoView(MethodView):
    """返回当前可用的 Agent 信息（用于前端展示与健康检查）。"""

    @ai_agent_blp.response(200, MessageResponseSchema)
    def get(self):
        """获取 Agent 信息。"""
        return jsonify({
            "code": 0,
            "message": "success",
            "data": {
                "agents": [
                    {
                        "name": "ui_automation",
                        "endpoint": "/api/ai/agent/ui",
                        "description": "UI 自动化主 Agent，集成 Playwright MCP 和 Chart MCP",
                        "tools": ["browser_*", "chart_*"],
                    },
                    {
                        "name": "recording",
                        "endpoint": "/api/ai/agent/recording",
                        "description": "录制回放 Agent，可生成并保存可复用的 Playwright 脚本",
                        "tools": [
                            "browser_*",
                            "save_current_recording",
                            "list_scripts",
                            "delete_script",
                            "reset_recording",
                            "get_current_code",
                            "check_script",
                            "create_script_with_auth",
                            "save_playwright_script",
                            "run_playwright_script",
                            "parse_test_results",
                        ],
                    },
                    {
                        "name": "ai_chat",
                        "endpoint": "/api/ai/agent/chat",
                        "description": "极简 LLM 转发，问什么答什么。流程验证 / 通用问答用",
                        "tools": ["ai_chat_simple"],
                    },
                    {
                        "name": "testcase_generator",
                        "endpoint": "/api/ai/agent/generate-cases",
                        "description": "AI 测试用例生成（结构化输出，覆盖正常/边界/异常）",
                        "tools": ["ai_generate_test_cases"],
                    },
                    {
                        "name": "case_runner",
                        "endpoint": "/api/ai/agent/run-cases",
                        "description": "批量执行测试用例，失败自动建 bug（飞轮第二齿轮）",
                        "tools": ["run_test_cases"],
                    },
                ],
            },
        })


# ============================================================================
# 测试用例生成（飞轮起点，不依赖 Playwright/MCP，纯 LCEL，便宜且快）
# ============================================================================

class AIChatRequestSchema(Schema):
    """极简 LLM 转发请求体（流程验证用，问什么答什么）。"""

    prompt = fields.String(
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "用户问题（必填）"},
    )
    model = fields.String(
        load_default=None,
        metadata={"description": "LLM 模型标识，如 local/llama3.2-1b。不传走默认网关"},
    )
    system = fields.String(
        load_default=None,
        metadata={"description": "自定义 system 提示词（可选）"},
    )


@ai_agent_blp.route("/chat")
class AIChatSimpleView(MethodView):
    """极简 LLM 转发：流程验证 / 通用问答。"""

    @ai_agent_blp.arguments(AIChatRequestSchema)
    @ai_agent_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """问什么答什么，不做结构化约束。用于验证 LLM 链路。"""
        try:
            answer = ai_chat(
                prompt=json_data["prompt"],
                model=json_data.get("model"),
                system=json_data.get("system"),
                agent_name="ai_chat_endpoint",
            )
        except ValueError as e:
            return jsonify({"code": 400, "message": str(e)}), 400
        except RuntimeError as e:
            logs.error(f"[ai_agent] LLM 调用失败: {e}")
            return jsonify({"code": 500, "message": str(e)}), 500

        return jsonify({
            "code": 0,
            "message": "success",
            "data": {
                "answer": answer,
                "model": json_data.get("model") or "default",
            },
        })


# ============================================================================
# 测试用例生成
# ============================================================================

class GenerateCasesRequestSchema(Schema):
    """生成测试用例请求体。"""

    requirement = fields.String(
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "需求描述文本（必填）"},
    )
    project_id = fields.Integer(
        load_default=None,
        metadata={"description": "落库的项目 ID。不传则只返回不落库"},
    )
    module_id = fields.Integer(
        load_default=None,
        metadata={"description": "所属模块 ID（可选）"},
    )
    folder_id = fields.Integer(
        load_default=None,
        metadata={"description": "所属目录 ID（可选）"},
    )
    model = fields.String(
        load_default=None,
        metadata={"description": "LLM 标识（如 local/llama3.2-1b）。不传走默认网关"},
    )
    extra_context = fields.String(
        load_default=None,
        metadata={"description": "附加上下文（如已有用例、API 字段定义）"},
    )
    save = fields.Boolean(
        load_default=True,
        metadata={"description": "是否落库（仅在传 project_id 时生效）"},
    )


@ai_agent_blp.route("/generate-cases")
class GenerateCasesView(MethodView):
    """AI 测试用例生成。"""

    @ai_agent_blp.arguments(GenerateCasesRequestSchema)
    @ai_agent_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """根据需求文本生成结构化测试用例，可选自动落库到 ``test_case_management``。"""
        try:
            result = generate_test_cases_with_db_prompt(
                requirement=json_data["requirement"],
                model=json_data.get("model"),
                extra_context=json_data.get("extra_context"),
                agent_name="testcase_generator",
            )
        except ValueError as e:
            return jsonify({"code": 400, "message": str(e)}), 400
        except RuntimeError as e:
            logs.error(f"[ai_agent] 用例生成失败: {e}")
            return jsonify({"code": 500, "message": str(e)}), 500

        cases_dict = [c.model_dump() for c in result.cases]
        data: Dict[str, Any] = {
            "case_count": result.case_count,
            "summary": result.summary,
            "model": result.model,
            "cases": cases_dict,
            "saved": False,
        }

        # 如果指定了 project_id 且 save=True，自动落库
        project_id: Optional[int] = json_data.get("project_id")
        if project_id and json_data.get("save", True):
            try:
                saved = save_generated_cases(
                    result.cases,
                    project_id=project_id,
                    module_id=json_data.get("module_id"),
                    folder_id=json_data.get("folder_id"),
                )
                data["saved"] = True
                data["saved_cases"] = saved
            except (ValueError, RuntimeError) as e:
                logs.error(f"[ai_agent] 用例落库失败: {e}")
                # 生成已成功，落库失败不阻塞返回，明确告知前端
                data["save_error"] = str(e)

        return jsonify({"code": 0, "message": "success", "data": data})


# ============================================================================
# 飞轮第二齿轮：执行用例 + 失败自动建 bug
# ============================================================================

class RunCasesRequestSchema(Schema):
    """执行用例请求体。"""

    case_ids = fields.List(
        fields.Integer(),
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "待执行的用例 id 列表（test_case_management.id）"},
    )
    project_id = fields.Integer(
        required=True,
        metadata={"description": "落 bug 的项目 id"},
    )
    create_bug_on_failure = fields.Boolean(
        load_default=True,
        metadata={"description": "失败时是否自动建 bug，默认是"},
    )
    reporter_id = fields.Integer(
        load_default=None,
        metadata={"description": "自动 bug 的报告人 id（可选，未传则用当前登录用户）"},
    )
    environment = fields.String(
        load_default=None,
        metadata={"description": "测试环境名（写入 bug.environment）"},
    )
    version = fields.String(
        load_default=None,
        metadata={"description": "发现版本号（写入 bug.version）"},
    )
    model = fields.String(
        load_default=None,
        metadata={"description": "裁判 LLM 模型（如 local/llama3.2-1b）"},
    )


@ai_agent_blp.route("/run-cases")
class RunCasesView(MethodView):
    """执行测试用例，失败自动建 bug。"""

    @ai_agent_blp.arguments(RunCasesRequestSchema)
    @ai_agent_blp.response(200, MessageResponseSchema)
    @login_required
    def post(self, json_data):
        """触发批量执行。"""
        from flask import g

        # 默认用当前登录用户作为 bug 的 reporter
        reporter_id = json_data.get("reporter_id")
        if reporter_id is None:
            current_user = g.get("current_user")
            if current_user:
                reporter_id = current_user.id

        try:
            report = execute_cases(
                case_ids=json_data["case_ids"],
                project_id=json_data["project_id"],
                create_bug_on_failure=json_data.get("create_bug_on_failure", True),
                reporter_id=reporter_id,
                environment=json_data.get("environment") or "",
                version=json_data.get("version") or "",
                model=json_data.get("model"),
            )
        except ValueError as e:
            return jsonify({"code": 400, "message": str(e)}), 400
        except Exception as e:
            logs.error(f"[ai_agent] 用例执行失败: {e}")
            return jsonify({"code": 500, "message": str(e)}), 500

        return jsonify({"code": 0, "message": "success", "data": report.to_dict()})


__all__ = ["ai_agent_blp"]
