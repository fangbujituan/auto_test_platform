"""
StepExecutor：单步执行驱动。

执行流：
    render → resolve_url → merge_headers → send → extract → assert → compose

设计要点：
- 任何异常**绝不外抛**，统一转成 ``StepResult.error / error_type``，由
  SequenceRunner 在策略层决定是否中断。这是为了路由层兜底：一个 step 异常
  不应炸掉整个批次。
- 抽取失败：有 default 用 default 写入 ctx；没 default 不写 ctx 但加 warning。
  抽取失败本身**不**导致 step 失败（只有断言才决定通过/失败）。
- 断言类型未注册：标 step 错（error_type=AssertionTypeNotFoundError）。
- 日志格式与设计 §16 对齐，全程携带 run_id / step_index / api_id。

作者: yandc
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING

from app.engine.api_engine.assertions.base import AssertionRegistry
from app.engine.api_engine.exceptions import (
    AssertionTypeNotFoundError,
    ExtractorTypeNotFoundError,
)
from app.engine.api_engine.extractors.base import ExtractorRegistry
from app.engine.api_engine.results import (
    AssertionOutcome,
    ExtractOutcome,
    RequestRecord,
    StepResult,
)

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.http.client import HttpClient
    from app.engine.api_engine.specs import RequestSpec

logger = logging.getLogger(__name__)


class StepExecutor:
    """单步执行器。"""

    def __init__(self, http_client: HttpClient) -> None:
        self._http: HttpClient = http_client

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def execute(
        self,
        spec: RequestSpec,
        ctx: ExecutionContext,
        step_index: int,
    ) -> StepResult:
        """执行一个 step，返回 StepResult。

        永不抛异常。
        """
        started_at = datetime.now()
        warnings_before = len(ctx.warnings)

        # 准备容器（异常路径也要返回这些字段）
        request_record: RequestRecord | None = None
        response_record = None
        extract_outcomes: list[ExtractOutcome] = []
        assertion_outcomes: list[AssertionOutcome] = []
        error: str | None = None
        error_type: str | None = None
        rendered = spec  # 兜底：异常时仍能展示原始 spec

        try:
            # 1. 渲染 spec（变量替换）
            rendered = ctx.render_request(spec)
            self._log(ctx, step_index, spec.api_id, "render",
                      f"渲染完成 method={rendered.method} url={rendered.url}")

            # 2. 解析最终 URL（base_url + prefix_url + path）
            full_url = ctx.resolve_full_url(rendered)
            rendered = replace(rendered, url=full_url, base_url=None)
            self._log(ctx, step_index, spec.api_id, "resolve_url",
                      f"最终 URL = {full_url}")

            # 3. 合并全局 Header（项目级 GlobalParam）
            merged_headers = ctx.merge_global_params_into_headers(rendered.headers)
            rendered = replace(rendered, headers=merged_headers)

            # 4. 发送请求
            request_record, response_record, http_error, http_error_type = (
                self._http.send(rendered)
            )

            if http_error is not None:
                # HTTP 调用失败：记录错误，跳过 extract / assert
                error = http_error
                error_type = http_error_type or "HttpInvocationError"
                self._log(
                    ctx, step_index, spec.api_id, "send",
                    f"HTTP 失败 type={error_type} msg={error}",
                    level=logging.ERROR,
                )
            else:
                duration_ms = response_record.elapsed_ms if response_record else 0
                self._log(
                    ctx, step_index, spec.api_id, "send",
                    f"发送 {rendered.method} {rendered.url} "
                    f"-> {response_record.status_code} ({duration_ms:.0f}ms)",
                )

            # 5. 抽取（即使断言后续失败也要跑，便于排障）
            if response_record is not None:
                for rule in spec.extracts:
                    outcome = self._run_extractor(rule, response_record, ctx, step_index, spec.api_id)
                    extract_outcomes.append(outcome)
                    if outcome.value is not None:  # 成功 or 用了 default 都写
                        ctx.update_extracted({rule.name: outcome.value})
                    if not outcome.succeeded:
                        ctx.warnings.append(
                            f"step[{step_index}] 抽取 {rule.name} 失败: {outcome.message}"
                        )

            # 6. 断言（仅在拿到响应时才跑）
            if response_record is not None:
                for rule in spec.assertions:
                    outcome = self._run_assertion(rule, response_record, ctx, step_index, spec.api_id)
                    assertion_outcomes.append(outcome)
                    # 断言类型未注册：直接标 step 错（所有后续断言仍尝试运行，便于一次性报告）
                    if not outcome.passed and outcome.type == "__error__":
                        error = outcome.message
                        error_type = "AssertionTypeNotFoundError"

        except Exception as exc:  # noqa: BLE001  顶层兜底，不外抛
            error = f"step 执行未知错误: {exc}"
            error_type = exc.__class__.__name__
            logger.exception(
                "[api_engine] run_id=%s step=%s api_id=%s 未捕获异常: %s",
                ctx.run_id, step_index, spec.api_id, exc,
            )

        # 7. 汇总：passed = 没有 error 且所有断言通过
        passed = error is None and all(a.passed for a in assertion_outcomes)
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()

        # 收集本步新增的 warnings（context 累积全局，这里取本步增量）
        step_warnings = list(ctx.warnings[warnings_before:])

        result = StepResult(
            name=spec.name,
            api_id=spec.api_id,
            case_id=spec.case_id,
            step_index=step_index,
            passed=passed,
            request=request_record,
            response=response_record,
            assertions=assertion_outcomes,
            extracts=extract_outcomes,
            duration=duration,
            started_at=started_at,
            finished_at=finished_at,
            error=error,
            error_type=error_type,
            warnings=step_warnings,
        )

        passed_cnt = sum(1 for a in assertion_outcomes if a.passed)
        failed_cnt = len(assertion_outcomes) - passed_cnt
        self._log(
            ctx, step_index, spec.api_id, "result",
            f"{'通过' if passed else '失败'} | 断言 {passed_cnt}/{len(assertion_outcomes)} 通过"
            + (f", 错误: {error}" if error else ""),
            level=logging.INFO if passed else logging.WARNING,
        )
        return result

    # ------------------------------------------------------------------
    # 内部分步实现
    # ------------------------------------------------------------------

    def _run_extractor(
        self,
        rule,
        response,
        ctx: ExecutionContext,
        step_index: int,
        api_id: int | None,
    ) -> ExtractOutcome:
        """单个抽取规则。失败统一转 ExtractOutcome。"""
        try:
            extractor = ExtractorRegistry.get(rule.type)
        except ExtractorTypeNotFoundError as exc:
            return ExtractOutcome(
                name=rule.name, type=rule.type, expression=rule.expression,
                value=rule.default, succeeded=False,
                message=f"未注册的抽取器类型 '{rule.type}'; 可用: {exc.details.get('available', [])}",
            )

        try:
            outcome = extractor.extract(
                response, name=rule.name, expression=rule.expression, default=rule.default,
            )
        except Exception as exc:  # noqa: BLE001
            outcome = ExtractOutcome(
                name=rule.name, type=rule.type, expression=rule.expression,
                value=rule.default, succeeded=False,
                message=f"抽取器执行异常: {exc}",
            )

        # 日志：仅成功打 INFO，失败打 DEBUG（warnings 已经在 ctx 累积）
        level = logging.INFO if outcome.succeeded else logging.DEBUG
        self._log(
            ctx, step_index, api_id, "extract",
            f"{rule.name} <- ({rule.type}) {rule.expression} = "
            f"{outcome.value!r}{' [default]' if not outcome.succeeded else ''}",
            level=level,
        )
        return outcome

    def _run_assertion(
        self,
        rule,
        response,
        ctx: ExecutionContext,
        step_index: int,
        api_id: int | None,
    ) -> AssertionOutcome:
        """单条断言。type 未注册或执行异常都转为失败的 AssertionOutcome。"""
        try:
            assertion = AssertionRegistry.get(rule.type)
        except AssertionTypeNotFoundError as exc:
            return AssertionOutcome(
                type="__error__",  # 特殊标记，让 execute 知道这是 type 错
                name=rule.name or rule.type,
                passed=False,
                message=(
                    f"未注册的断言类型 '{rule.type}'; "
                    f"可用: {exc.details.get('available', [])}"
                ),
                expected=rule.config,
                actual=None,
            )

        try:
            outcome = assertion.check(response, rule.config or {}, ctx)
        except Exception as exc:  # noqa: BLE001
            outcome = AssertionOutcome(
                type=rule.type, name=rule.name or rule.type,
                passed=False, message=f"断言执行异常: {exc}",
                expected=rule.config, actual=None,
            )

        self._log(
            ctx, step_index, api_id, "assert",
            f"{outcome.type} {'通过' if outcome.passed else '失败'}: {outcome.message}",
            level=logging.INFO if outcome.passed else logging.WARNING,
        )
        return outcome

    @staticmethod
    def _log(
        ctx: ExecutionContext,
        step_index: int,
        api_id: int | None,
        phase: str,
        message: str,
        level: int = logging.INFO,
    ) -> None:
        logger.log(
            level,
            "[api_engine] run_id=%s step=%s api_id=%s 阶段=%s %s",
            ctx.run_id, step_index, api_id, phase, message,
        )
