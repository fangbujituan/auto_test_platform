"""
质量数据看板（V0.1）—— 服务层。

V0.1 范围
---------
只提供 **测试执行统计-趋势** 一个指标：按日聚合每天的执行总数 / 通过 /
失败 / 错误 / 通过率。其他主题（Bug / 覆盖度 / 需求 / 项目总览 / 团队
效能 / 数据导出）留给后续版本。

设计取舍
--------
- ``test_results`` 表本身**没有 project_id 字段**，project 维度通过
  ``test_results.case_id → test_cases.project_id`` 关联得到。所以
  按项目过滤的 SQL 必须 join。
- 没有缓存层、没有 ``X-Cache`` 头、没有 10s 查询超时熔断——V0.1 数据规模
  小，这些后续优化项再加。
- 没有跨度限制（spec 要求 365 天上限），V0.1 信任前端传入。
- 字段命名与 spec 保持一致：``total / passed / failed / error /
  skipped / pass_rate / fail_rate``，方便未来扩展不破坏 schema。

作者: yandc
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func

from app.models.base import db
from app.models.case import TestCase
from app.models.result import TestResult


def get_execution_trend(
    *,
    project_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[dict]:
    """按日聚合测试执行结果。

    Args:
        project_id: 可选，按项目过滤；不传则统计全部
        start_date: 起始日期（含），不传默认 ``end_date - 30 天``
        end_date:   结束日期（含），不传默认今天

    Returns:
        日期升序的字典列表，每项包含::

            {
              "date": "YYYY-MM-DD",
              "total": int,
              "passed": int,
              "failed": int,
              "error": int,
              "skipped": int,
              "pass_rate": float | None,   # 0~100，分母为 0 时为 None
              "fail_rate": float | None,
            }

        缺失的日期会用 0 补齐（折线图友好）。
    """
    # 1) 时间范围归一化（半开区间 [start_dt, end_dt_exclusive)）
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(
        end_date + timedelta(days=1), datetime.min.time()
    )

    # 2) SQL 聚合：按 DATE(created_at) 分组，按 status 拆桶
    date_col = func.date(TestResult.created_at).label("d")
    query = db.session.query(
        date_col,
        TestResult.status,
        func.count(TestResult.id).label("cnt"),
    ).filter(
        TestResult.created_at >= start_dt,
        TestResult.created_at < end_dt_exclusive,
    )

    if project_id is not None:
        # test_results 没 project_id，必须 join test_cases
        query = query.join(TestCase, TestResult.case_id == TestCase.id)
        query = query.filter(TestCase.project_id == project_id)

    rows = query.group_by(date_col, TestResult.status).all()

    # 3) 把 (date, status) -> count 摊平到 date -> {status: count}
    by_date: dict[str, dict[str, int]] = {}
    for d, status, cnt in rows:
        # SQLite 返回 str，MySQL 返回 date；统一成字符串
        key = d if isinstance(d, str) else d.isoformat()
        bucket = by_date.setdefault(key, {})
        bucket[status or "unknown"] = (bucket.get(status or "unknown", 0)) + int(cnt)

    # 4) 补齐空日期（让前端折线图不会断）
    result: list[dict] = []
    cursor = start_date
    while cursor <= end_date:
        key = cursor.isoformat()
        bucket = by_date.get(key, {})
        passed = int(bucket.get("passed", 0))
        failed = int(bucket.get("failed", 0))
        error = int(bucket.get("error", 0))
        skipped = int(bucket.get("skipped", 0))
        total = passed + failed + error + skipped
        if total > 0:
            pass_rate = round(passed / total * 100, 2)
            fail_rate = round((failed + error) / total * 100, 2)
        else:
            pass_rate = None
            fail_rate = None
        result.append({
            "date": key,
            "total": total,
            "passed": passed,
            "failed": failed,
            "error": error,
            "skipped": skipped,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
        })
        cursor += timedelta(days=1)

    return result


__all__ = ["get_execution_trend"]
