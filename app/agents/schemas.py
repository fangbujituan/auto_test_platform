"""
Agent 结构化输出 Schema。

把 LLM 返回的 JSON 强制对齐到 Pydantic 模型，避免 "AI 自由发挥" 导致下游
落库失败。每个 Agent 的输出都应该有一个对应的 Schema。

设计原则：
1. 字段命名与数据库 model 一致（``TestCaseManagement``、``Bug``），方便直接落库
2. 字段都加 ``description``，会自动注入到 prompt 里教 LLM 怎么填
3. 枚举值用 ``Literal``，约束 LLM 不要乱写
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# 测试用例生成
# ============================================================================

# 与 TestCaseManagement.priority 对齐
PriorityLevel = Literal["P0", "P1", "P2", "P3"]
# 与 TestCaseManagement.case_type 对齐
CaseType = Literal["功能", "性能", "安全", "兼容性", "易用性", "边界", "异常"]


class GeneratedTestCase(BaseModel):
    """单条测试用例的结构化输出。

    字段对齐 ``app.models.test_case.TestCaseManagement``，可直接落库。
    """

    title: str = Field(
        ...,
        description="用例标题，必须简洁明确，能一眼看出测什么场景，不超过 50 字",
        max_length=200,
    )
    description: str = Field(default="", description="用例描述（可选）")
    precondition: str = Field(
        default="",
        description="执行该用例前必须满足的前置条件，没有可写'无'",
    )
    steps: str = Field(
        ...,
        description=(
            "测试步骤，逐步描述用户操作。每步独立成行，"
            "形如 '1. 打开登录页\\n2. 输入用户名\\n3. 点击登录'"
        ),
    )
    expected_result: str = Field(
        ...,
        description="预期结果，必须可验证，描述操作后系统应有的反应",
    )
    priority: PriorityLevel = Field(
        default="P2",
        description="优先级。P0=核心主流程；P1=重要功能；P2=常规；P3=边缘",
    )
    case_type: CaseType = Field(
        default="功能",
        description="用例类型。功能/性能/安全/兼容性/易用性/边界/异常",
    )


class GeneratedTestCaseList(BaseModel):
    """生成测试用例的批量输出。"""

    cases: List[GeneratedTestCase] = Field(
        ...,
        description="测试用例列表。覆盖正常流程、边界条件、异常场景三类",
        min_length=1,
    )
    summary: str = Field(default="", description="本次生成的整体说明")


# ============================================================================
# 用例执行 / Bug 报告
# ============================================================================

ExecutionStatus = Literal["passed", "failed", "blocked", "skipped"]
"""
- passed:  通过（实际结果与预期相符）
- failed:  失败（实际结果与预期不符 → 自动建 bug）
- blocked: 阻塞（前置条件不满足 / 环境不可用）
- skipped: 跳过
"""


class CaseExecutionResult(BaseModel):
    """单条用例的执行结果。

    ``_execute_one`` 输出此结构，再交给 ``executor`` 决定是否建 bug。
    """

    case_id: int = Field(..., description="对应 ``test_case_management.id``")
    case_no: str = Field(..., description="用例编号，如 TC-1-001")
    title: str = Field(..., description="用例标题")
    status: ExecutionStatus = Field(..., description="执行状态")
    actual_result: str = Field(
        default="",
        description="实际结果（失败时会成为 bug 的 actual_result）",
    )
    error_message: str = Field(default="", description="异常信息")
    duration_seconds: float = Field(default=0.0, description="执行耗时（秒）")
    bug_id: Optional[int] = Field(
        default=None,
        description="若失败并自动建了 bug，这里是 ``bugs.id``",
    )


class AIVerdict(BaseModel):
    """AI 充当裁判时的结构化输出。

    把用例的 ``steps`` 与 ``expected_result`` 喂给 LLM，让它判断本轮执行是
    pass 还是 fail，并给出实际观察到的结果。这是飞轮 v1 用的最便宜的"执行"
    方式——等接入真的 Playwright/API 执行，把这块换掉即可。
    """

    status: ExecutionStatus = Field(..., description="执行结论")
    actual_result: str = Field(..., description="实际观察到的结果")
    reasoning: str = Field(default="", description="结论理由（AI 自我说明）")


__all__ = [
    "PriorityLevel",
    "CaseType",
    "GeneratedTestCase",
    "GeneratedTestCaseList",
    "ExecutionStatus",
    "CaseExecutionResult",
    "AIVerdict",
]
