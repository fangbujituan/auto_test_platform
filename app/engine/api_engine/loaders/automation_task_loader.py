"""
AutomationTaskLoader：``automation_tasks`` + ``automation_task_cases`` → CollectionSpec。

把一个自动化任务展开成一组按 ``sort_order`` 排序的 ``RequestSpec``，
通过 ``ApiModelLoader`` / ``TestCaseLoader`` 完成"接口/用例 → spec"的具体转换。

设计要点：
- 找不到任务抛 ``LoaderError``
- 关联用例不存在时**不**报错，而是产出一个标记"loader_missing"的 step（与老
  ``AutomationExecutor`` 行为一致：用例不存在记录为 error 但不中断整体）
- 支持三种关联方式（同一行只取一种，按 case_mgmt > case > api 优先级解析）：
    * ``api_id``       → 走 ApiModelLoader（直接挂接口）
    * ``case_id``      → 走 TestCaseLoader（接口测试用例）
    * ``case_mgmt_id`` → 当前 Phase 不处理
- ``loop_count`` / ``fail_strategy`` / ``interval_seconds`` 从 task 读取并写入
  CollectionSpec / 每个 RequestSpec：
    * loop_count       → CollectionSpec.iterations
    * fail_strategy    → CollectionSpec.fail_strategy（"stop" → "fail_fast"）
    * interval_seconds → 每个 RequestSpec.delay_ms

作者: yandc
"""
from __future__ import annotations

import logging
from typing import Any

from app.engine.api_engine.exceptions import LoaderError
from app.engine.api_engine.loaders.api_model_loader import ApiModelLoader
from app.engine.api_engine.loaders.base import BaseLoader
from app.engine.api_engine.loaders.test_case_loader import TestCaseLoader
from app.engine.api_engine.specs import (
    AssertionRule,
    CollectionSpec,
    RequestSpec,
)

logger = logging.getLogger(__name__)

# 当关联用例不存在时使用的占位 spec 名（reporter 会把它落 status=error）
_MISSING_CASE_PREFIX = "missing-case"


class AutomationTaskLoader(BaseLoader):
    """``automation_tasks`` → ``CollectionSpec``。"""

    def __init__(
        self,
        test_case_loader: TestCaseLoader | None = None,
        api_loader: ApiModelLoader | None = None,
    ):
        self._case_loader: TestCaseLoader = test_case_loader or TestCaseLoader()
        self._api_loader: ApiModelLoader = api_loader or ApiModelLoader()

    # ------------------------------------------------------------------
    # 单条转换（不实现）
    # ------------------------------------------------------------------

    def load_request(self, **kwargs: Any) -> RequestSpec:  # noqa: ARG002
        raise NotImplementedError(
            "AutomationTaskLoader 没有单条语义，请使用 load_collection"
        )

    # ------------------------------------------------------------------
    # 批量转换：task → CollectionSpec
    # ------------------------------------------------------------------

    def load_collection(
        self,
        *,
        task_id: int,
        environment_id: int | None = None,
        fail_strategy: str | None = None,
        initial_variables: dict[str, Any] | None = None,
    ) -> CollectionSpec:
        """根据 ``task_id`` 取出关联用例（按 sort_order）→ CollectionSpec。

        Args:
            task_id:        ``automation_tasks.id``
            environment_id: 调用方传入；为 None 时使用 ``task.environment_id``
            fail_strategy:  调用方覆盖；为 None 时使用 ``task.fail_strategy``
            initial_variables: 初始变量

        Raises:
            LoaderError: task_id 不存在
        """
        task = self._fetch_task(task_id)

        # environment_id 优先级：参数 > task.environment_id
        effective_env = environment_id if environment_id is not None else task.environment_id

        # fail_strategy 优先级：参数 > task.fail_strategy（"stop"/"continue"，需翻译）
        raw_strategy = fail_strategy if fail_strategy is not None else (
            task.fail_strategy or "continue"
        )
        translated_strategy = self._translate_fail_strategy(raw_strategy)

        # 循环次数 / 步骤间隔
        iterations = max(1, int(task.loop_count or 1))
        interval_seconds = float(task.interval_seconds or 0)
        delay_ms = max(0, int(interval_seconds * 1000))

        task_cases = self._fetch_task_cases(task_id)
        specs: list[RequestSpec] = []

        for tc in task_cases:
            spec = self._build_spec_for_task_case(tc, project_id=task.project_id)
            # 把任务级间隔写到每个 spec 的 delay_ms（覆盖 loader 本地默认）
            if delay_ms > 0:
                spec.delay_ms = delay_ms
            specs.append(spec)

        logger.info(
            "[api_engine] AutomationTaskLoader 加载完成 task_id=%s name=%s "
            "步骤数=%d iterations=%d fail_strategy=%s interval_ms=%d",
            task_id, task.name, len(specs), iterations,
            translated_strategy, delay_ms,
        )

        return CollectionSpec(
            name=f"automation-task:{task_id}",
            project_id=task.project_id,
            environment_id=effective_env,
            requests=specs,
            fail_strategy=translated_strategy,
            iterations=iterations,
            initial_variables=dict(initial_variables or {}),
        )

    # ------------------------------------------------------------------
    # 数据访问
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_task(task_id: int):
        try:
            from app.models.automation import AutomationTask
        except Exception as exc:  # pragma: no cover
            raise LoaderError(
                "无法导入 AutomationTask 模型；需要 Flask 上下文",
                details={"reason": str(exc)},
            ) from exc

        task = AutomationTask.query.get(task_id)
        if task is None:
            raise LoaderError(
                f"自动化任务不存在: task_id={task_id}",
                details={"task_id": task_id},
            )
        return task

    @staticmethod
    def _fetch_task_cases(task_id: int):
        from app.models.automation import AutomationTaskCase
        return (
            AutomationTaskCase.query
            .filter_by(task_id=task_id)
            .order_by(AutomationTaskCase.sort_order.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # 单步构造
    # ------------------------------------------------------------------

    def _build_spec_for_task_case(self, task_case, *, project_id: int) -> RequestSpec:
        """单条 ``automation_task_cases`` 行 → ``RequestSpec``。

        引用类型解析优先级：case_mgmt > case > api。

        关联资源不存在时返回占位 spec（method=GET, url=""），让引擎在执行时产出
        一个明确失败的 step，由 reporter 落 status=error，行为与老路径对齐。
        """
        # 1. case_mgmt：当前 Phase 暂不支持
        if task_case.case_mgmt_id:
            return self._missing_spec(
                reason=(
                    f"任务用例项 #{task_case.id} 关联的是 case_mgmt_id="
                    f"{task_case.case_mgmt_id}（本期暂不支持）"
                ),
            )

        # 2. case_id：走 TestCaseLoader
        if task_case.case_id:
            try:
                return self._case_loader.load_request(case_id=task_case.case_id)
            except LoaderError as exc:
                return self._missing_spec(
                    reason=f"关联用例不存在: case_id={task_case.case_id}",
                    case_id=task_case.case_id,
                    detail=exc.message,
                )

        # 3. api_id：走 ApiModelLoader
        if task_case.api_id:
            try:
                return self._api_loader.load_request(
                    api_id=task_case.api_id,
                    project_id=project_id,
                )
            except LoaderError as exc:
                return self._missing_spec(
                    reason=f"关联接口不存在: api_id={task_case.api_id}",
                    case_id=task_case.api_id,
                    detail=exc.message,
                )

        # 4. 三种引用都没填
        return self._missing_spec(
            reason=f"任务用例项 #{task_case.id} 未关联任何接口或用例",
        )

    @staticmethod
    def _translate_fail_strategy(raw: str) -> str:
        """DB 存储值 → 引擎使用值。

        DB 用业务语义 ``continue`` / ``stop``；引擎用 ``continue`` / ``fail_fast``。
        ``make_strategy`` 内部已经支持 "stop"，但我们在 loader 层显式翻译，
        让 CollectionSpec 的字段值对齐 ``FailStrategyName`` Literal。
        """
        key = (raw or "").strip().lower()
        if key in ("stop", "fail_fast", "failfast"):
            return "fail_fast"
        return "continue"

    @staticmethod
    def _missing_spec(*, reason: str, case_id: int | None = None,
                      detail: str | None = None) -> RequestSpec:
        """构造一个"用例缺失"的占位 spec。

        - method/url 都给最小可执行值，但 ``url=""`` 会让 HttpClient 直接报错
        - ``assertions`` 添加一条恒失败断言，确保 step.passed=false
        - 名字带 ``missing-case:`` 前缀，便于人工识别
        """
        return RequestSpec(
            name=f"{_MISSING_CASE_PREFIX}:{case_id or 'unknown'} ({reason})",
            method="GET",
            url="",
            case_id=case_id,
            assertions=[
                # 这条 status_code 断言永远不会被执行（因为 url 空，HTTP 调用会失败），
                # 但带在身上让 spec.to_dict() 能反映"原本期望什么"
                AssertionRule(
                    type="status_code",
                    config={"expected": 200},
                    name="（用例缺失，永远失败）",
                ),
            ],
        )
