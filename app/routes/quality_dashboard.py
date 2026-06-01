"""
质量数据看板路由（V0.1）。

仅暴露一个端点：``GET /api/dashboard/quality/execution/trend``，按日聚合
测试执行结果。

权限：沿用现有 ``@login_required``，与 ``/api/dashboard/stats`` 一致。
**未做项目级隔离**——V0.1 简化版；后续版本会通过 ``project_members``
做严格隔离（spec Requirement 3）。

作者: yandc
"""
from __future__ import annotations

from datetime import date, datetime

from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas.common import MessageResponseSchema
from app.services.quality_metrics import get_execution_trend
from app.utils.permission import login_required


quality_dashboard_blp = Blueprint(
    "quality_dashboard",
    __name__,
    url_prefix="/api/dashboard/quality",
    description="质量数据看板（V0.1）",
)


def _parse_date_param(name: str) -> date | None:
    """从 query 中解析 YYYY-MM-DD 日期；非法则抛 ValueError。"""
    raw = request.args.get(name)
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _parse_int_param(name: str) -> int | None:
    """从 query 中解析正整数；非法返回 None。"""
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        v = int(raw)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


@quality_dashboard_blp.route("/execution/trend")
class ExecutionTrendView(MethodView):
    """按日聚合的测试执行趋势。"""

    @quality_dashboard_blp.response(200, MessageResponseSchema)
    @quality_dashboard_blp.alt_response(
        400, schema=MessageResponseSchema, description="参数错误"
    )
    @login_required
    def get(self):
        """获取测试执行趋势数据。

        Query 参数:
            project_id (int, 可选): 项目 ID；不传则统计全平台
            start_date (str, 可选): 起始日期 YYYY-MM-DD；默认 end_date - 30 天
            end_date   (str, 可选): 结束日期 YYYY-MM-DD；默认今天
        """
        try:
            start_date = _parse_date_param("start_date")
            end_date = _parse_date_param("end_date")
        except ValueError:
            return jsonify({
                "code": 1,
                "message": "日期格式错误，需 YYYY-MM-DD",
            }), 400

        project_id = _parse_int_param("project_id")

        try:
            data = get_execution_trend(
                project_id=project_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:  # noqa: BLE001
            return jsonify({
                "code": 1,
                "message": f"获取趋势数据失败: {e}",
            }), 500

        return jsonify({
            "code": 0,
            "data": {
                "items": data,
                "filters": {
                    "project_id": project_id,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
            },
        })
