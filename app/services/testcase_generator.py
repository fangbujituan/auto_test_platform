"""
AI 测试用例生成 Service。

飞轮起点：把"需求描述"转换为"结构化测试用例列表"，可直接落库或返回。

设计原则：
1. **极简依赖**：只依赖 ``llm_gateway`` 和 LangChain LCEL，**不**用 deepagents
   /SubAgent/MCP，因为用例生成不需要工具调用，纯 LLM 输出最便宜最快。
2. **结构化输出**：通过 ``with_structured_output(GeneratedTestCaseList)`` 强制
   LLM 输出符合 Pydantic 契约的 JSON。失败的 token 浪费降到最低。
3. **Prompt 来源可切换**：可读取数据库里 ``ai_prompt_templates`` 表的
   ``test_case_generation`` 模板（产品/测试可在前端编辑），也支持直接传入
   自定义 system prompt。
4. **三个调用入口共享同一份逻辑**：
   - HTTP 路由（前端按钮）
   - LangChain ``@tool``（UI Agent 内部调用）
   - MCP Server tool（外部 IDE Agent 调用）

作者: yandc
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException

from app.agents.schemas import GeneratedTestCase, GeneratedTestCaseList
from app.services.llm_gateway import get_model

logger = logging.getLogger(__name__)


# ============================================================================
# 默认 Prompt（无数据库时的兜底）
# ============================================================================

DEFAULT_SYSTEM_PROMPT = """你是一位资深的软件测试专家，擅长根据需求设计全面的测试用例。

## 核心要求

为给定的需求设计一组**高覆盖度**的测试用例，必须按以下三类组织：

1. **正常流程**：典型用户路径，验证主功能可用
2. **边界条件**：边界值、空值、最大/最小值、临界数量等
3. **异常场景**：错误输入、网络异常、权限不足、并发冲突等

## 字段填写规范

- **title**：一句话描述测试场景，禁止使用模糊词如"测试 XXX"
- **steps**：逐步可执行，每步独立成行；不要混入预期结果
- **expected_result**：必须可验证（可观察、可断言），不要写"系统正常运行"这种不具体的描述
- **priority**：P0=登录/支付等主链路；P1=重要业务；P2=常规功能；P3=边缘
- **case_type**：根据用例性质从 [功能/性能/安全/兼容性/易用性/边界/异常] 中选择

## 数量建议

简单需求 3-5 条，中等 6-10 条，复杂 10-20 条。**优先质量，不为凑数**。
"""

DEFAULT_USER_PROMPT_TEMPLATE = """请根据以下需求生成测试用例：

{requirement}

请按照三类（正常流程 / 边界条件 / 异常场景）组织输出。"""


# ============================================================================
# 输出策略
# ============================================================================
# 两种模式：
# - "structured": 使用 with_structured_output（依赖模型支持 tool calling/JSON schema）
#                 对 GPT-4 / Claude / DeepSeek-Chat 这类大模型最稳
# - "parser":     使用 PydanticOutputParser，把 JSON schema 注入到 prompt 里，
#                 模型自由输出后再解析。对 Llama-1B 这类小模型必须用这个
# 通过环境变量 TESTCASE_GEN_MODE 切换，默认 "parser"（兼容性最好）

import os as _os
_OUTPUT_MODE = _os.getenv("TESTCASE_GEN_MODE", "parser").lower()


# ============================================================================
# Service 入口
# ============================================================================

@dataclass
class TestCaseGenerationResult:
    """生成结果。"""
    cases: List[GeneratedTestCase]
    summary: str
    requirement: str
    model: str
    case_count: int


def generate_test_cases(
    requirement: str,
    *,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_prompt_template: Optional[str] = None,
    extra_context: Optional[str] = None,
    agent_name: str = "testcase_generator",
) -> TestCaseGenerationResult:
    """根据需求生成测试用例。

    Args:
        requirement: 需求描述文本（必填）
        model: LLM 模型标识（如 ``local/llama3.2-1b``、``aiop/azure/gpt-5.4``）。
            为 ``None`` 时使用 ``DEFAULT_MODEL`` 环境变量
        system_prompt: 自定义系统提示词。为 ``None`` 时使用内置 ``DEFAULT_SYSTEM_PROMPT``
        user_prompt_template: 自定义 user prompt 模板，需含 ``{requirement}`` 占位
        extra_context: 附加上下文（如已有用例、相关 API 列表等），会拼到 user prompt 之后
        agent_name: token 统计用的 agent 名

    Returns:
        ``TestCaseGenerationResult``

    Raises:
        ValueError: requirement 为空
        RuntimeError: LLM 输出无法解析为合法的 ``GeneratedTestCaseList``
    """
    if not (requirement and requirement.strip()):
        raise ValueError("requirement 不能为空")

    sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    usr_template = user_prompt_template or DEFAULT_USER_PROMPT_TEMPLATE

    # 组装 user message
    try:
        user_message = usr_template.format(requirement=requirement)
    except KeyError as e:
        raise ValueError(f"user_prompt_template 占位符不识别: {e}") from e

    if extra_context and extra_context.strip():
        user_message = f"{user_message}\n\n## 附加上下文\n{extra_context}"

    # 走 llm_gateway，统一 token 统计 + 多网关支持
    llm = get_model(model=model, agent_name=agent_name)

    logger.info(
        "[testcase_generator] 开始生成 | model=%s | mode=%s | requirement_len=%d",
        model or "default",
        _OUTPUT_MODE,
        len(requirement),
    )

    try:
        if _OUTPUT_MODE == "structured":
            # 大模型走 tool calling / JSON schema，最稳
            structured_llm = llm.with_structured_output(GeneratedTestCaseList)
            result: GeneratedTestCaseList = structured_llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_message),
            ])
        else:
            # 小模型走 prompt 注入 + 文本解析（不依赖 tool calling）
            parser = PydanticOutputParser(pydantic_object=GeneratedTestCaseList)
            sys_with_schema = (
                sys_prompt
                + "\n\n## 输出格式（严格遵守）\n"
                + parser.get_format_instructions()
                + "\n**只输出 JSON，不要任何解释性文字、不要 markdown 代码块标记。**"
            )
            response = llm.invoke([
                SystemMessage(content=sys_with_schema),
                HumanMessage(content=user_message),
            ])
            raw_text = response.content if hasattr(response, "content") else str(response)
            try:
                result = parser.parse(raw_text)
            except OutputParserException as e:
                # 尝试从可能的 markdown 代码块里抠 JSON 出来
                import re as _re
                m = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
                if not m:
                    raise
                result = parser.parse(m.group(0))
    except Exception as e:
        logger.error("[testcase_generator] LLM 调用失败: %s", e, exc_info=True)
        raise RuntimeError(f"用例生成失败: {e}") from e

    if not result or not result.cases:
        raise RuntimeError("LLM 返回了空的用例列表")

    logger.info(
        "[testcase_generator] 生成完成 | %d 条用例",
        len(result.cases),
    )

    return TestCaseGenerationResult(
        cases=result.cases,
        summary=result.summary,
        requirement=requirement,
        model=model or "default",
        case_count=len(result.cases),
    )


# ============================================================================
# 数据库辅助：从 AIPromptTemplate 表读取 prompt
# ============================================================================

def load_prompt_from_db(scene: str = "test_case_generation") -> tuple[Optional[str], Optional[str]]:
    """从 ``ai_prompt_templates`` 表读取指定场景的 prompt。

    需要 Flask app context（因为查 ORM）。

    Args:
        scene: 场景标识，对应表里的 ``scene`` 字段

    Returns:
        ``(system_prompt, user_prompt_template)``。表中无对应记录时返回 ``(None, None)``。
    """
    try:
        from app.models.ai_prompt import AIPromptTemplate

        template = AIPromptTemplate.query.filter_by(scene=scene).first()
        if not template:
            logger.warning("[testcase_generator] 未找到 prompt 模板: scene=%s", scene)
            return None, None
        return template.system_prompt, template.user_prompt_template
    except Exception as e:
        # 没 app context、或数据库连不上时返回 None，让调用方走默认
        logger.warning("[testcase_generator] 读取 prompt 模板失败，将使用默认值: %s", e)
        return None, None


def generate_test_cases_with_db_prompt(
    requirement: str,
    *,
    scene: str = "test_case_generation",
    model: Optional[str] = None,
    extra_context: Optional[str] = None,
    agent_name: str = "testcase_generator",
) -> TestCaseGenerationResult:
    """读 DB prompt 后再生成（如果 DB 里没配置就用默认 prompt）。"""
    sys_p, usr_p = load_prompt_from_db(scene)
    return generate_test_cases(
        requirement=requirement,
        model=model,
        system_prompt=sys_p,
        user_prompt_template=usr_p,
        extra_context=extra_context,
        agent_name=agent_name,
    )


__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_USER_PROMPT_TEMPLATE",
    "TestCaseGenerationResult",
    "generate_test_cases",
    "generate_test_cases_with_db_prompt",
    "load_prompt_from_db",
]



# ============================================================================
# 落库辅助：把 GeneratedTestCase 列表批量写入 TestCaseManagement 表
# ============================================================================

def save_generated_cases(
    cases: List[GeneratedTestCase],
    *,
    project_id: int,
    module_id: Optional[int] = None,
    folder_id: Optional[int] = None,
) -> List[dict]:
    """把生成的用例批量落库到 ``test_case_management`` 表。

    需要 Flask app context（执行 ORM 写入）。

    Args:
        cases: ``generate_test_cases()`` 返回的用例列表
        project_id: 落到哪个项目
        module_id: 所属模块（可选）
        folder_id: 所属目录（可选）

    Returns:
        每条用例落库后的 ``to_dict()`` 列表（含 id、case_no）

    Raises:
        ValueError: project_id 缺失或项目不存在
        RuntimeError: 数据库写入失败
    """
    from app.models.base import db
    from app.models.project import Project
    from app.models.test_case import TestCaseManagement
    from app.routes.test_case import generate_case_no

    if not project_id:
        raise ValueError("project_id 不能为空")
    if not Project.query.get(project_id):
        raise ValueError(f"项目不存在: project_id={project_id}")

    saved: List[dict] = []
    try:
        for case in cases:
            tc = TestCaseManagement(
                case_no=generate_case_no(project_id),
                project_id=project_id,
                module_id=module_id,
                folder_id=folder_id,
                title=case.title,
                description=case.description or None,
                precondition=case.precondition or None,
                steps=case.steps,
                expected_result=case.expected_result,
                priority=case.priority,
                case_type=case.case_type,
                case_status="草稿",
                status=1,
            )
            db.session.add(tc)
            db.session.flush()  # 拿 id / case_no
            saved.append(tc.to_dict())
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("[testcase_generator] 落库失败: %s", e, exc_info=True)
        raise RuntimeError(f"落库失败: {e}") from e

    logger.info("[testcase_generator] 已落库 %d 条用例 → project_id=%d", len(saved), project_id)
    return saved



# ============================================================================
# 极简 LLM 转发（流程级验证用）
# ============================================================================

def ai_chat(
    prompt: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    agent_name: str = "ai_chat",
) -> str:
    """最简单的 LLM 转发：问什么，答什么。

    用途：
    - 流程级验证（不在乎答案质量，只验证调用链是通的）
    - 给外部 Agent / IDE Agent 一个"借用平台 LLM"的极简入口
    - 是 ``generate_test_cases`` 的反面教材：那个要求结构化输出，对小模型不友好；
      这个无任何强制约束，1B 模型也扛得住

    Args:
        prompt: 用户问题
        model: LLM 模型标识，不传走默认网关
        system: 自定义 system 提示词（可选）
        agent_name: token 统计名

    Returns:
        LLM 返回的纯文本
    """
    if not (prompt and prompt.strip()):
        raise ValueError("prompt 不能为空")

    llm = get_model(model=model, agent_name=agent_name)

    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))

    logger.info(
        "[ai_chat] model=%s | prompt_len=%d",
        model or "default",
        len(prompt),
    )

    try:
        response = llm.invoke(messages)
    except Exception as e:
        logger.error("[ai_chat] LLM 调用失败: %s", e, exc_info=True)
        raise RuntimeError(f"LLM 调用失败: {e}") from e

    return response.content if hasattr(response, "content") else str(response)
