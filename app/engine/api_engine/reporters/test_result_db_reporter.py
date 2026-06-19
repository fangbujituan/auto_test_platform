"""
TestResultDbReporter：把引擎执行结果写入 ``test_results`` 表。

替代老 ``TestExecutor.run_case`` 的写库逻辑：每跑完一个 step 立即 commit
一行 ``TestResult``，与历史"按用例独立记录"的语义一致。

外部访问入口：
- ``last_result_id``  最近一次 ``on_step_completed`` 写入的 result.id（``run_test_case`` 取实体用）
- ``result_ids``      整批写入的所有 result.id（按 step 顺序）

设计要点：
- ``test_results`` 没有"父执行"的概念（不像 ``task_executions/details``），
  因此 reporter **不**需要 ``on_collection_started`` / ``on_collection_finished`` 写库
- 每行独立 commit，单条失败不影响后续步骤
- 字段映射与 ``AutomationDbReporter`` 共享 ``_step_mapping``，确保口径一致

作者: yandc
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.engine.api_engine.reporters._step_mapping import (
    compose_error_message,
    map_step_status,
)

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.results import CollectionResult, StepResult
    from app.engine.api_engine.specs import CollectionSpec

logger = logging.getLogger(__name__)


class TestResultDbReporter:
    """写 ``test_results`` 表的 Reporter。"""

    def __init__(self) -> None:
        self.result_ids: list[int] = []

    @property
    def last_result_id(self) -> int | None:
        """最近一次写入的 ``TestResult.id``（无写入时返回 None）。"""
        return self.result_ids[-1] if self.result_ids else None

    # ------------------------------------------------------------------
    # Reporter Protocol 实现
    # ------------------------------------------------------------------

    def on_collection_started(
        self,
        spec: CollectionSpec,  # noqa: ARG002
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> None:
        # test_results 没有父执行行，跳过
        return None

    def on_step_completed(
        self,
        step: StepResult,
        ctx: ExecutionContext,
    ) -> None:
        if step.case_id is None:
            logger.warning(
                "[api_engine] TestResultDbReporter 跳过：step.case_id 为空 "
                "run_id=%s step=%d name=%s（仅 test_cases 来源会写 test_results）",
                ctx.run_id, step.step_index, step.name,
            )
            return

        try:
            from app.models.base import db
            from app.models.result import TestResult

            result = TestResult(
                case_id=step.case_id,
                status=map_step_status(step),
                actual_status=(step.response.status_code if step.response else None),
                actual_response=(step.response.body if step.response else None),
                duration=step.duration,
                error_message=compose_error_message(step),
            )
            db.session.add(result)
            db.session.commit()
            self.result_ids.append(result.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[api_engine] TestResultDbReporter 写入 test_results 失败 case_id=%s: %s",
                step.case_id, exc,
            )
            self._safe_rollback()

    def on_collection_finished(
        self,
        result: CollectionResult,  # noqa: ARG002
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> None:
        # 不需要更新汇总；test_results 是独立行
        return None

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_rollback() -> None:
        try:
            from app.models.base import db
            db.session.rollback()
        except Exception:  # pragma: no cover
            pass
