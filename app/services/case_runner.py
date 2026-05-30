"""
飞轮第二齿轮：测试用例自动执行 + 失败自动建 bug。

设计要点：
1. **可插拔的执行器**：``execute_cases`` 通过参数 ``executor`` 接受任何符合
   ``CaseExecutorProtocol`` 的实现。v1 内置 ``AIVerdictExecutor``——把用例
   交给 LLM 当裁判，零外部依赖最便宜，先把"生成→执行→失败建 bug"的流程
   跑通；v2 接入 Playwright/HTTP 真实执行只需替换执行器即可。
2. **失败即建 bug**：``status == 'failed'`` 时自动写入 ``bugs`` 表，
   ``related_test_cases`` 关联用例 id，``steps_to_reproduce`` 抄用例 steps，
   ``expected_result`` / ``actual_result`` 直接落上。
3. **批量执行**：传入用例 id 列表，依次执行；并发与分布式留给 v2，
   v1 顺序跑保证流程稳定。
4. **三层解耦**：``CaseExecutorProtocol`` 接口 + ``execute_cases`` orchestrator
   + ``BugReporter`` 副作用，三者独立可替换、可测试。

作者: yandc
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Protocol

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser

from app.agents.schemas import AIVerdict, CaseExecutionResult, ExecutionStatus
from app.services.llm_gateway import get_model

logger = logging.getLogger(__name__)


# ============================================================================
# 执行器协议（任何符合此协议的对象都能塞进 execute_cases）
# ============================================================================

class CaseExecutorProtocol(Protocol):
    """单条用例执行器接口。

    实现类需要拿到一条 ``TestCaseManagement`` 用例，返回 ``(status,
    actual_result, error_message)``。
    """

    def execute(
        self,
        case: "TestCaseManagement",  # type: ignore[name-defined]  # 运行时由调用方传入
    ) -> tuple[ExecutionStatus, str, str]:
        ...


# ============================================================================
# v1 内置执行器：AI 当裁判
# ============================================================================

DEFAULT_VERDICT_SYSTEM_PROMPT = """你是一名资深的测试执行助手。给你一条测试用例（含步骤和预期结果），
你需要在没有真实环境的情况下，**判断这条用例如果按步骤执行，是否会达到预期结果**。

## 判定原则

- **passed**：步骤合理、可执行，且预期结果与一般系统行为相符
- **failed**：步骤会导致实际结果与预期明显不符（例如：预期跳转主页，但步骤实际导致登录失败）
- **blocked**：步骤含有不可执行项（前置条件缺失、依赖不存在的资源）
- **skipped**：用例被明确标记为跳过（一般不会主动判定）

请基于"步骤逻辑 + 一般系统行为常识"做判断，**不要过度乐观**。如果用例本身设计
得就是"测错误情况"（比如"输入错误密码 → 提示密码错误"），那应该判 passed，因为
预期就是错误提示。
"""


@dataclass
class AIVerdictExecutor:
    """v1 内置执行器：让 LLM 当裁判。

    适合飞轮流程验证。生产替换为真实 Playwright/HTTP 执行器即可。
    """

    model: Optional[str] = None
    agent_name: str = "case_runner"
    system_prompt: str = DEFAULT_VERDICT_SYSTEM_PROMPT

    def execute(self, case) -> tuple[ExecutionStatus, str, str]:  # type: ignore[no-untyped-def]
        llm = get_model(model=self.model, agent_name=self.agent_name)
        parser = PydanticOutputParser(pydantic_object=AIVerdict)

        user_message = (
            f"用例编号: {case.case_no}\n"
            f"用例标题: {case.title}\n"
            f"前置条件: {case.precondition or '无'}\n"
            f"测试步骤:\n{case.steps}\n"
            f"预期结果: {case.expected_result}\n"
        )

        sys_with_schema = (
            self.system_prompt
            + "\n\n## 输出格式（严格遵守）\n"
            + parser.get_format_instructions()
            + "\n**只输出 JSON，不要任何解释性文字、不要 markdown 代码块标记。**"
        )

        try:
            response = llm.invoke([
                SystemMessage(content=sys_with_schema),
                HumanMessage(content=user_message),
            ])
            raw_text = response.content if hasattr(response, "content") else str(response)
            try:
                verdict = parser.parse(raw_text)
            except OutputParserException:
                # 兜底：从可能的 markdown 块里抠 JSON
                import re as _re
                m = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
                if not m:
                    raise
                verdict = parser.parse(m.group(0))
        except Exception as e:
            logger.error("[case_runner] AI 裁决失败 case_no=%s: %s", case.case_no, e)
            return "blocked", "", f"AI 裁决调用失败: {e}"

        return verdict.status, verdict.actual_result, ""


# ============================================================================
# Bug 自动报告器
# ============================================================================

@dataclass
class BugReporter:
    """失败用例 → bugs 表的自动写入器。

    抽出来是为了：
    - 单元测试时可以塞个假的 BugReporter 验证逻辑
    - 想换更复杂的报告策略（去重、合并）只动这里
    """

    project_id: int
    reporter_id: Optional[int] = None
    environment: str = ""
    version: str = ""

    def report(
        self,
        case,  # type: ignore[no-untyped-def]  # TestCaseManagement
        actual_result: str,
        error_message: str = "",
    ) -> int:
        """写 bug，返回 bug.id。"""
        from app.models.base import db
        from app.models.bug import Bug
        from app.models.user import User

        # 优先级映射用例优先级
        priority_map = {"P0": "critical", "P1": "high", "P2": "medium", "P3": "low"}

        # bug.reporter_id 是 NOT NULL：调用方未指定时回退到第一个 user
        # 这样飞轮能继续转动，事后可由人工 reassign
        reporter_id = self.reporter_id
        if reporter_id is None:
            fallback_user = User.query.order_by(User.id.asc()).first()
            if fallback_user is None:
                raise RuntimeError(
                    "无法自动建 bug：未指定 reporter_id 且系统中无任何 user 可作为兜底"
                )
            reporter_id = fallback_user.id
            logger.info(
                "[case_runner] 自动 bug 未指定 reporter_id，回退到 user_id=%d", reporter_id
            )

        title = f"[自动检测] {case.title}"
        description_lines = [
            f"用例编号：{case.case_no}",
            f"用例类型：{case.case_type}",
            f"用例优先级：{case.priority}",
        ]
        if error_message:
            description_lines.append(f"\n执行错误：{error_message}")
        description = "\n".join(description_lines)

        bug = Bug(
            title=title[:200],
            description=description,
            project_id=self.project_id,
            status="open",
            priority=priority_map.get(case.priority, "medium"),
            severity="normal",
            category="自动检测",
            reporter_id=reporter_id,
            environment=self.environment or None,
            version=self.version or None,
            steps_to_reproduce=case.steps,
            expected_result=case.expected_result,
            actual_result=actual_result or error_message or "用例执行未通过",
            related_test_cases=[case.id],
        )
        db.session.add(bug)
        db.session.flush()
        bug_id = bug.id
        db.session.commit()

        logger.info("[case_runner] 失败用例 → 已建 bug | case=%s bug_id=%d", case.case_no, bug_id)
        return bug_id


# ============================================================================
# 批量执行 orchestrator
# ============================================================================

@dataclass
class CaseRunReport:
    """整批执行结果汇总。"""

    project_id: int
    total: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    bug_ids: List[int] = field(default_factory=list)
    results: List[CaseExecutionResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "bug_ids": self.bug_ids,
            "results": [r.model_dump() for r in self.results],
        }


def execute_cases(
    case_ids: Iterable[int],
    *,
    project_id: int,
    executor: Optional[CaseExecutorProtocol] = None,
    create_bug_on_failure: bool = True,
    reporter_id: Optional[int] = None,
    environment: str = "",
    version: str = "",
    model: Optional[str] = None,
) -> CaseRunReport:
    """批量执行测试用例，失败自动建 bug。

    需要 Flask app context（要查 ``test_case_management`` 和写 ``bugs``）。

    Args:
        case_ids: 待执行的用例 id 列表（``test_case_management.id``）
        project_id: 落 bug 的项目 id
        executor: 单条执行器，默认 ``AIVerdictExecutor``
        create_bug_on_failure: 失败时是否自动建 bug（默认是）
        reporter_id: 自动 bug 的报告人 id（不传则为空，留待人工指派）
        environment / version: 写到 bug 的环境和版本字段
        model: 默认执行器使用的 LLM 模型

    Returns:
        ``CaseRunReport``，包含每条用例的执行结果与 bug id 列表
    """
    from app.models.test_case import TestCaseManagement

    case_ids = list(case_ids)
    if not case_ids:
        raise ValueError("case_ids 不能为空")
    if not project_id:
        raise ValueError("project_id 不能为空")

    runner = executor or AIVerdictExecutor(model=model)
    reporter = (
        BugReporter(
            project_id=project_id,
            reporter_id=reporter_id,
            environment=environment,
            version=version,
        )
        if create_bug_on_failure
        else None
    )

    cases = (
        TestCaseManagement.query.filter(TestCaseManagement.id.in_(case_ids))
        .filter(TestCaseManagement.project_id == project_id)
        .all()
    )
    found_ids = {c.id for c in cases}
    missing = set(case_ids) - found_ids
    if missing:
        logger.warning(
            "[case_runner] 部分用例不存在或不属于该项目，将忽略: %s", sorted(missing)
        )

    results: List[CaseExecutionResult] = []
    counters = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0}
    bug_ids: List[int] = []

    for case in cases:
        start = time.time()
        try:
            status, actual_result, error_message = runner.execute(case)
        except Exception as e:
            logger.error(
                "[case_runner] 执行器抛出异常 case=%s: %s", case.case_no, e, exc_info=True
            )
            status = "blocked"
            actual_result = ""
            error_message = f"执行器异常: {e}"

        duration = round(time.time() - start, 3)
        counters[status] = counters.get(status, 0) + 1

        bug_id: Optional[int] = None
        if status == "failed" and reporter is not None:
            try:
                bug_id = reporter.report(case, actual_result, error_message)
                bug_ids.append(bug_id)
            except Exception as e:
                logger.error(
                    "[case_runner] 失败用例建 bug 失败 case=%s: %s", case.case_no, e, exc_info=True
                )

        result = CaseExecutionResult(
            case_id=case.id,
            case_no=case.case_no,
            title=case.title,
            status=status,
            actual_result=actual_result,
            error_message=error_message,
            duration_seconds=duration,
            bug_id=bug_id,
        )
        results.append(result)
        logger.info(
            "[case_runner] case=%s | %s | %.2fs%s",
            case.case_no,
            status,
            duration,
            f" | bug_id={bug_id}" if bug_id else "",
        )

    return CaseRunReport(
        project_id=project_id,
        total=len(results),
        passed=counters["passed"],
        failed=counters["failed"],
        blocked=counters["blocked"],
        skipped=counters["skipped"],
        bug_ids=bug_ids,
        results=results,
    )


__all__ = [
    "CaseExecutorProtocol",
    "AIVerdictExecutor",
    "BugReporter",
    "CaseRunReport",
    "execute_cases",
]
