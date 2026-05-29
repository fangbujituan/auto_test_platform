"""
测试结果API路由。

作者: yandc
创建时间: 2026-01-13
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.result import TestResult
from app.schemas.common import MessageResponseSchema
from app.schemas.result import ResultQuerySchema

result_blp = Blueprint(
    "result", __name__,
    url_prefix="/api/results",
    description="测试结果查询"
)

# 向后兼容
result_bp = result_blp


@result_blp.route("")
class ResultsView(MethodView):
    """测试结果列表"""

    @result_blp.arguments(ResultQuerySchema, location="query")
    @result_blp.response(200, MessageResponseSchema)
    def get(self, query_args):
        """获取测试结果，可选按case_id过滤。"""
        case_id = query_args.get("case_id")
        page = query_args.get("page", 1)
        per_page = query_args.get("per_page", 20)

        query = TestResult.query.order_by(TestResult.created_at.desc())
        if case_id:
            query = query.filter_by(case_id=case_id)

        pagination = query.paginate(page=page, per_page=per_page)

        return jsonify({
            "code": 0,
            "data": [r.to_dict() for r in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
        })


@result_blp.route("/<int:result_id>")
class ResultDetailView(MethodView):
    """测试结果详情"""

    @result_blp.response(200, MessageResponseSchema)
    def get(self, result_id):
        """获取单个测试结果。"""
        result = TestResult.query.get_or_404(result_id)
        return jsonify({"code": 0, "data": result.to_dict()})
