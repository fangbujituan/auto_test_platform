"""
ApiEngine：对外的统一门面。

调用方只需要：

    from app.engine.api_engine import get_api_engine
    engine = get_api_engine()
    step = engine.run_inline_request(
        payload={"method": "GET", "url": "https://httpbin.org/get"},
        project_id=1,
    )

各入口的实现节奏（与 spec tasks 对齐）：

| 入口                     | Phase | 数据源                          |
|--------------------------|-------|---------------------------------|
| run_inline_request       | 1     | 前端 dict（不入库）              |
| run_inline_sequence      | 1     | 前端 dict 列表（不入库）          |
| run_single_api           | 2     | apis 表 + ApiModelLoader        |
| run_api_sequence         | 2     | apis 表 + ApiModelLoader        |
| run_test_case            | 4     | test_cases 表 + TestCaseLoader  |
| run_automation_task      | 3     | automation_tasks + Loader       |

未实现入口 SHALL 抛 NotImplementedError 提示对应 Phase 任务。

作者: yandc
"""
from __future__ import annotations

import logging
from typing import Any

from app.engine.api_engine.context import ExecutionContext
from app.engine.api_engine.exceptions import InvalidRequestSpecError
from app.engine.api_engine.http.client import HttpClient
from app.engine.api_engine.loaders.api_model_loader import ApiModelLoader
from app.engine.api_engine.loaders.automation_task_loader import AutomationTaskLoader
from app.engine.api_engine.loaders.inline_request_loader import InlineRequestLoader
from app.engine.api_engine.loaders.test_case_loader import TestCaseLoader
from app.engine.api_engine.reporters.automation_db_reporter import AutomationDbReporter
from app.engine.api_engine.reporters.base import Reporter
from app.engine.api_engine.reporters.console_reporter import ConsoleReporter
from app.engine.api_engine.reporters.test_result_db_reporter import TestResultDbReporter
from app.engine.api_engine.results import CollectionResult, StepResult
from app.engine.api_engine.runner.sequence_runner import SequenceRunner
from app.engine.api_engine.specs import (
    AssertionRule,
    CollectionSpec,
    ExtractRule,
    RequestSpec,
)
from app.engine.api_engine.strategies.failure_strategy import (
    FailureStrategy,
    make_strategy,
)

logger = logging.getLogger(__name__)


class ApiEngine:
    """API 执行引擎门面。

    构造参数：
        http_client:        HttpClient，可注入 Mock 用于测试
        default_strategy:   默认失败策略；spec 自带的 fail_strategy 优先
        default_reporters:  默认 reporter 列表（每次 run 都会挂上）
    """

    def __init__(
        self,
        *,
        http_client: HttpClient | None = None,
        default_strategy: FailureStrategy | None = None,
        default_reporters: list[Reporter] | None = None,
    ) -> None:
        self._http_client: HttpClient = http_client or HttpClient()
        self._default_strategy: FailureStrategy = (
            default_strategy or make_strategy("continue")
        )
        # 缺省挂控制台报告器
        self._default_reporters: list[Reporter] = (
            list(default_reporters)
            if default_reporters is not None
            else [ConsoleReporter()]
        )
        # dict → spec 的官方转换器（共享给所有 inline 入口）
        self._inline_loader: InlineRequestLoader = InlineRequestLoader()
        # apis 表 → spec 的官方转换器
        self._api_loader: ApiModelLoader = ApiModelLoader()
        # automation_tasks → CollectionSpec
        self._automation_loader: AutomationTaskLoader = AutomationTaskLoader()
        # test_cases → spec
        self._case_loader: TestCaseLoader = TestCaseLoader()

    # ==================================================================
    # Phase 1：临时 dict 调试入口（无需 DB 模型）
    # ==================================================================

    def run_inline_request(
        self,
        *,
        payload: dict[str, Any],
        project_id: int,
        environment_id: int | None = None,
        initial_variables: dict[str, Any] | None = None,
        extra_reporters: list[Reporter] | None = None,
    ) -> StepResult:
        """临时单接口执行（前端未保存接口时使用）。

        Args:
            payload: 单条请求规格 dict，至少包含 ``method`` 与 ``url``，
                     可含 ``headers/params/body/body_type/timeout/assertions/extracts``
            project_id: 用于加载项目级变量与全局参数
            environment_id: 可选环境 id
            initial_variables: 调用方注入的临时变量（覆盖项目变量）
            extra_reporters: 额外 reporter（如 PersistenceReporter）

        Returns:
            StepResult；HTTP / 断言失败均被吞掉，永不抛异常。

        Raises:
            InvalidRequestSpecError: 当 payload 缺失必填字段或字段非法时（在执行前）
        """
        spec = self._inline_loader.load_request(payload, default_name="ad-hoc-request")
        collection = CollectionSpec(
            name="ad-hoc-request",
            project_id=project_id,
            environment_id=environment_id,
            requests=[spec],
            fail_strategy="continue",
            initial_variables=initial_variables or {},
        )
        result = self._run_collection(collection, extra_reporters)
        # unwrap 第一条 step；保证调用方拿到的是单步语义
        if result.steps:
            return result.steps[0]
        # 极端情况：runner 顶层异常导致 steps 为空
        raise RuntimeError(
            f"run_inline_request 未产生 step 结果: {result.error_message}"
        )

    def run_inline_sequence(
        self,
        *,
        payloads: list[dict[str, Any]],
        project_id: int,
        environment_id: int | None = None,
        fail_strategy: str = "continue",
        name: str = "ad-hoc-sequence",
        initial_variables: dict[str, Any] | None = None,
        extra_reporters: list[Reporter] | None = None,
    ) -> CollectionResult:
        """临时多接口顺序执行（前端临时勾选多条 dict 时使用）。

        步骤间通过 ``extracts`` 抽取的变量自动可见于后续步骤。
        """
        collection = self._inline_loader.load_collection(
            payloads=payloads,
            project_id=project_id,
            environment_id=environment_id,
            name=name,
            fail_strategy=fail_strategy,
            initial_variables=initial_variables,
        )
        return self._run_collection(collection, extra_reporters)

    # ==================================================================
    # Phase 2：从 apis 表加载执行
    # ==================================================================

    def run_single_api(
        self,
        *,
        api_id: int,
        project_id: int,
        environment_id: int | None = None,
        overrides: dict[str, Any] | None = None,
        initial_variables: dict[str, Any] | None = None,
        extra_reporters: list[Reporter] | None = None,
    ) -> StepResult:
        """单接口执行（前端"点击发送"走这条）。

        Args:
            api_id:     ``apis.id``
            project_id: 用于隔离与变量加载
            environment_id: 可选环境 ID；前置 URL 与变量解析受其影响
            overrides:  调试态字段覆盖（method/path/headers/...）
            initial_variables: 调用方注入的临时变量
            extra_reporters: 额外 reporter（如自动化用 PersistenceReporter）

        Returns:
            StepResult；HTTP / 断言失败均不抛异常。

        Raises:
            LoaderError:             api_id 找不到时
            InvalidRequestSpecError: DB 中 assertions/extracts 字段非法时
        """
        spec = self._api_loader.load_request(
            api_id=api_id, project_id=project_id, overrides=overrides,
        )
        collection = CollectionSpec(
            name=f"api:{api_id}",
            project_id=project_id,
            environment_id=environment_id,
            requests=[spec],
            fail_strategy="continue",
            initial_variables=initial_variables or {},
        )
        result = self._run_collection(collection, extra_reporters)
        if result.steps:
            return result.steps[0]
        raise RuntimeError(
            f"run_single_api 未产生 step 结果: {result.error_message}"
        )

    def run_api_sequence(
        self,
        *,
        api_ids: list[int],
        project_id: int,
        environment_id: int | None = None,
        fail_strategy: str = "continue",
        name: str = "api-sequence",
        per_api_overrides: dict[int, dict[str, Any]] | None = None,
        initial_variables: dict[str, Any] | None = None,
        extra_reporters: list[Reporter] | None = None,
    ) -> CollectionResult:
        """多接口顺序执行（前端"批量运行"走这条）。

        步骤间通过 ``apis.extracts`` 抽取的变量自动可见于后续步骤。

        Raises:
            LoaderError:             任一 api_id 找不到时
            InvalidRequestSpecError: api_ids 为空 / DB 字段非法
        """
        collection = self._api_loader.load_collection(
            api_ids=api_ids,
            project_id=project_id,
            environment_id=environment_id,
            fail_strategy=fail_strategy,
            name=name,
            per_api_overrides=per_api_overrides,
            initial_variables=initial_variables,
        )
        return self._run_collection(collection, extra_reporters)

    # ==================================================================
    # Phase 3：自动化任务
    # ==================================================================

    def run_automation_task(
        self,
        *,
        task_id: int,
        environment_id: int | None = None,
        trigger_source: str = "manual",
        extra_reporters: list[Reporter] | None = None,
    ) -> "TaskExecution":  # 返回 ORM 实例，对齐老 AutomationExecutor 契约
        """执行自动化任务，写入 ``task_executions`` + ``task_execution_details``。

        Args:
            task_id:        ``automation_tasks.id``
            environment_id: 调用方覆盖；为 None 时用 ``task.environment_id``
            trigger_source: ``manual / cron / webhook``
            extra_reporters: 额外 reporter（如自定义观测）

        Returns:
            ``TaskExecution`` 实体；调用方据此对外返回。

        Raises:
            LoaderError: task_id 不存在
        """
        # 1. Loader 把 task 展开成 CollectionSpec
        collection = self._automation_loader.load_collection(
            task_id=task_id,
            environment_id=environment_id,
        )

        # 2. 单独构造 DB reporter，便于事后取 execution_id
        db_reporter = AutomationDbReporter(
            task_id=task_id,
            trigger_source=trigger_source,
        )
        reporters: list[Reporter] = [db_reporter]
        if extra_reporters:
            reporters.extend(extra_reporters)

        # 3. 跑（默认 reporter 仍包含控制台日志）
        self._run_collection(collection, reporters)

        # 4. 取实体返回（reporter 已经写完 finished 状态）
        from app.models.automation import TaskExecution
        if db_reporter.execution_id is None:
            raise RuntimeError(
                f"AutomationDbReporter 未产生 execution_id，"
                f"可能是 on_collection_started 写库失败 task_id={task_id}"
            )
        execution = TaskExecution.query.get(db_reporter.execution_id)
        if execution is None:
            raise RuntimeError(
                f"TaskExecution(id={db_reporter.execution_id}) 查询不到；"
                f"可能在 reporter 写入与查询之间被并发删除"
            )
        return execution

    # ==================================================================
    # Phase 4：单条 test_case 执行
    # ==================================================================

    def run_test_case(
        self,
        *,
        case_id: int | None = None,
        case=None,
        environment_id: int | None = None,
        initial_variables: dict[str, Any] | None = None,
        extra_reporters: list[Reporter] | None = None,
    ) -> "TestResult":  # 返回 ORM 实例，对齐老 TestExecutor.run_case 契约
        """执行单条 ``test_cases`` 行，写入 ``test_results``。

        Args:
            case_id:    与 ``case`` 二选一；优先 ``case``
            case:       已查询的 ``TestCase`` 实例（避免重复查询）
            environment_id: 可选环境 ID
            initial_variables: 调用方注入的临时变量
            extra_reporters: 额外 reporter

        Returns:
            ``TestResult`` 实体；与老 ``TestExecutor.run_case`` 完全一致。

        Raises:
            LoaderError: case_id 不存在
        """
        spec = self._case_loader.load_request(case_id=case_id, case=case)
        # project_id 仅用于变量加载与 GlobalParam 合并；无 case 实体时取 1 作占位
        project_id = case.project_id if case is not None else self._lookup_case_project_id(case_id)

        collection = CollectionSpec(
            name=f"test_case:{spec.case_id}",
            project_id=project_id,
            environment_id=environment_id,
            requests=[spec],
            fail_strategy="continue",
            initial_variables=initial_variables or {},
        )

        # 单独构造 DB reporter，便于事后取 result_id
        db_reporter = TestResultDbReporter()
        reporters: list[Reporter] = [db_reporter]
        if extra_reporters:
            reporters.extend(extra_reporters)

        self._run_collection(collection, reporters)

        from app.models.result import TestResult
        if db_reporter.last_result_id is None:
            raise RuntimeError(
                f"TestResultDbReporter 未产生 result_id，"
                f"可能是 on_step_completed 写库失败 case_id={spec.case_id}"
            )
        result = TestResult.query.get(db_reporter.last_result_id)
        if result is None:
            raise RuntimeError(
                f"TestResult(id={db_reporter.last_result_id}) 查询不到"
            )
        return result

    def run_test_cases(
        self,
        *,
        cases: list,
        environment_id: int | None = None,
        initial_variables: dict[str, Any] | None = None,
        extra_reporters: list[Reporter] | None = None,
    ) -> list:
        """批量执行 ``test_cases``。

        所有用例**共享一个** ExecutionContext（步骤间抽取的变量可被后续步骤引用）。
        与 ``run_test_case`` 单调用循环不同，本方法是真正的"批次"语义。

        Returns:
            ``list[TestResult]``，顺序与 ``cases`` 输入对齐。
        """
        if not cases:
            return []

        specs = [self._case_loader.load_request(case=c) for c in cases]
        project_id = cases[0].project_id

        collection = CollectionSpec(
            name=f"test_cases-batch ({len(cases)})",
            project_id=project_id,
            environment_id=environment_id,
            requests=specs,
            fail_strategy="continue",
            initial_variables=initial_variables or {},
        )

        db_reporter = TestResultDbReporter()
        reporters: list[Reporter] = [db_reporter]
        if extra_reporters:
            reporters.extend(extra_reporters)

        self._run_collection(collection, reporters)

        from app.models.result import TestResult
        if not db_reporter.result_ids:
            return []
        # 按写入顺序查实体；用 in_ 一次取回再按 id 顺序排
        rows = TestResult.query.filter(
            TestResult.id.in_(db_reporter.result_ids)
        ).all()
        rows_by_id = {r.id: r for r in rows}
        return [rows_by_id[rid] for rid in db_reporter.result_ids if rid in rows_by_id]

    @staticmethod
    def _lookup_case_project_id(case_id: int | None) -> int:
        """根据 case_id 查 project_id；查不到回退 0。"""
        if case_id is None:
            return 0
        try:
            from app.models.case import TestCase
            case = TestCase.query.get(case_id)
            return case.project_id if case else 0
        except Exception:  # pragma: no cover
            return 0

    # ==================================================================
    # 占位入口（已无；所有阶段入口都已实现）
    # ==================================================================

    # ==================================================================
    # 内部工具
    # ==================================================================

    def _run_collection(
        self,
        collection: CollectionSpec,
        extra_reporters: list[Reporter] | None,
    ) -> CollectionResult:
        """构造 ExecutionContext + SequenceRunner 跑一次。"""
        ctx = ExecutionContext(
            project_id=collection.project_id,
            environment_id=collection.environment_id,
            initial_variables=collection.initial_variables,
        )
        reporters: list[Reporter] = list(self._default_reporters)
        if extra_reporters:
            reporters.extend(extra_reporters)

        runner = SequenceRunner(
            http_client=self._http_client,
            strategy=self._default_strategy,
            reporters=reporters,
        )
        return runner.run(collection, ctx)


def _to_extract_rule(raw: Any) -> ExtractRule:
    """dict → ExtractRule（保留向后兼容的模块级工具，新代码请用 InlineRequestLoader）。"""
    return InlineRequestLoader._build_extract(raw)


def _to_assertion_rule(raw: Any) -> AssertionRule:
    """dict → AssertionRule（保留向后兼容的模块级工具，新代码请用 InlineRequestLoader）。"""
    return InlineRequestLoader._build_assertion(raw)


# ----------------------------------------------------------------------
# 全局单例（路由层使用 get_api_engine() 即可）
# ----------------------------------------------------------------------

_default_engine: ApiEngine | None = None


def get_api_engine() -> ApiEngine:
    """获取进程级默认 ApiEngine（懒初始化）。"""
    global _default_engine
    if _default_engine is None:
        _default_engine = ApiEngine()
    return _default_engine


def reset_api_engine() -> None:
    """重置默认引擎；仅供测试使用。"""
    global _default_engine
    _default_engine = None
