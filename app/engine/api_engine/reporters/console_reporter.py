"""
ConsoleReporter：控制台日志摘要。

职责：
- ``on_collection_started``  打印开始横幅（项目/环境/总数/策略）
- ``on_step_completed``      增量打印每步结果（含失败断言摘要）
- ``on_collection_finished`` 打印总结（passed/failed/error/skipped + 耗时）

仅写日志，不落库、不写文件。本期是默认 reporter，所有 ApiEngine 入口都会挂。

作者: yandc
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.results import CollectionResult, StepResult
    from app.engine.api_engine.specs import CollectionSpec

logger = logging.getLogger(__name__)


class ConsoleReporter:
    """控制台报告器。

    输出全部走 ``logging.INFO``（失败步骤走 ``WARNING``），便于和应用统一日志体系融合。
    """

    def on_collection_started(
        self,
        spec: CollectionSpec,
        ctx: ExecutionContext,
    ) -> None:
        logger.info(
            "[api_engine] ========== 开始执行 ========== "
            "run_id=%s collection=%s project=%s env=%s 总步骤=%d 失败策略=%s",
            ctx.run_id,
            spec.name,
            spec.project_id,
            spec.environment_id,
            len(spec.requests),
            spec.fail_strategy,
        )

    def on_step_completed(
        self,
        step: StepResult,
        ctx: ExecutionContext,
    ) -> None:
        status = "✅ PASS" if step.passed else "❌ FAIL"
        method = step.request.method if step.request else "?"
        url = step.request.url if step.request else "?"
        status_code = step.response.status_code if step.response else "-"
        duration_ms = step.duration * 1000.0

        log = logger.info if step.passed else logger.warning
        log(
            "[api_engine] run_id=%s step=%d %s | %s %s -> %s | "
            "断言 %d/%d | 耗时 %.1fms",
            ctx.run_id, step.step_index, status,
            method, url, status_code,
            sum(1 for a in step.assertions if a.passed), len(step.assertions),
            duration_ms,
        )

        # 失败时把不通过的断言/错误打出来
        if not step.passed:
            if step.error:
                logger.warning(
                    "[api_engine] run_id=%s step=%d 错误: [%s] %s",
                    ctx.run_id, step.step_index, step.error_type, step.error,
                )
            for a in step.assertions:
                if not a.passed:
                    logger.warning(
                        "[api_engine] run_id=%s step=%d 断言失败: [%s] %s — %s",
                        ctx.run_id, step.step_index, a.type,
                        a.name or "(unnamed)", a.message,
                    )

        # warnings 单独提示（缺失变量/抽取失败）
        for w in step.warnings:
            logger.info(
                "[api_engine] run_id=%s step=%d ⚠ %s",
                ctx.run_id, step.step_index, w,
            )

    def on_collection_finished(
        self,
        result: CollectionResult,
        ctx: ExecutionContext,
    ) -> None:
        if result.error_message:
            logger.error(
                "[api_engine] run_id=%s collection 顶层异常: %s",
                ctx.run_id, result.error_message,
            )

        logger.info(
            "[api_engine] ========== 执行结束 ========== "
            "run_id=%s 总数=%d 通过=%d 失败=%d 错误=%d 跳过=%d 总耗时=%.2fs",
            ctx.run_id,
            result.total,
            result.passed,
            result.failed,
            result.error,
            result.skipped,
            result.duration,
        )
