"""
测试用例执行器（薄壳）。

Phase 4 起内部委托给 ``app.engine.api_engine.ApiEngine.run_test_case``，
对外接口完全不变：

- ``TestExecutor(timeout=...)``      构造
- ``run_case(case) -> TestResult``   单条执行
- ``run_cases(cases) -> list[...]``  批量执行

历史的请求发送、响应解析、断言匹配等逻辑已被引擎吸收：
- 发请求/解析响应  → ``HttpClient``
- 状态码断言       → ``StatusCodeAssertion``（自动派生）
- 响应体部分匹配   → ``JsonSubsetAssertion``（自动派生）
- 写 ``test_results`` → ``TestResultDbReporter``
- 状态/错误消息映射 → 与 ``AutomationDbReporter`` 完全一致

作者: yandc
创建时间: 2026-01-13（Phase 4 重构）
"""
from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from app.engine.api_engine import LoaderError, get_api_engine
from app.models.base import db
from app.models.result import TestResult

if TYPE_CHECKING:
    from app.models.case import TestCase

logger = logging.getLogger(__name__)


class TestExecutor:
    """测试用例执行器（薄壳）。"""

    def __init__(self, timeout: int = 30):
        # 保留构造参数兼容老代码；超时实际由引擎默认 HttpClient 控制。
        self.timeout = timeout

    def run_case(self, case: TestCase) -> TestResult:
        """执行单个测试用例。

        与历史行为对齐：
        - 返回 ``TestResult`` 实体
        - 任何异常被吞，转 status="error" 落库

        Raises:
            从不抛出业务异常；engine 内部异常会兜底成 status=error 的 TestResult
        """
        try:
            engine = get_api_engine()
            return engine.run_test_case(case=case)

        except LoaderError as exc:
            # case 不存在/查不到；引擎已在 _to_spec 之前就检查
            return self._record_emergency_failure(
                case=case,
                error=f"Loader 错误: {exc.message}",
            )
        except Exception as exc:  # noqa: BLE001 顶层兜底
            # 引擎内部 reporter 已经做了多层 try/except；
            # 这里只对极端情况兜底，保证调用方能拿到一条 TestResult
            logger.exception(
                "[TestExecutor] 引擎执行未捕获异常 case_id=%s: %s",
                getattr(case, "id", None), exc,
            )
            return self._record_emergency_failure(
                case=case,
                error=traceback.format_exc(),
            )

    def run_cases(self, cases: list) -> list[TestResult]:
        """批量执行测试用例。

        返回与 ``cases`` 输入顺序对齐的 ``TestResult`` 列表。
        异常用例**不**中断整批；那条用例的 result 会带 status=error。
        """
        if not cases:
            return []

        try:
            engine = get_api_engine()
            return engine.run_test_cases(cases=cases)

        except Exception as exc:  # noqa: BLE001 顶层兜底
            logger.exception("[TestExecutor] 批量执行未捕获异常: %s", exc)
            # 极端兜底：每条用例落一条 emergency 失败行
            err = traceback.format_exc()
            return [self._record_emergency_failure(case=c, error=err) for c in cases]

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _record_emergency_failure(*, case, error: str) -> TestResult:
        """极端兜底：reporter 也崩了，手动写一条 status=error 行返回。

        与历史 ``run_case`` 异常分支行为一致（status=error + error_message）。
        """
        try:
            db.session.rollback()
        except Exception:  # pragma: no cover
            pass

        result = TestResult(
            case_id=getattr(case, "id", None),
            status="error",
            duration=0,
            error_message=error,
        )
        db.session.add(result)
        db.session.commit()
        return result
