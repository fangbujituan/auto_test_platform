"""
测试用例API路由。

作者: yandc
创建时间: 2026-01-13
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.case import TestCase
from app.schemas.common import MessageResponseSchema
from app.schemas.case import CaseCreateSchema, CaseUpdateSchema, CaseQuerySchema

case_blp = Blueprint(
    "case", __name__,
    url_prefix="/api/cases",
    description="API测试用例管理"
)

# 向后兼容
case_bp = case_blp


@case_blp.route("")
class CasesView(MethodView):
    """测试用例列表与创建"""

    @case_blp.arguments(CaseQuerySchema, location="query")
    @case_blp.response(200, MessageResponseSchema)
    def get(self, query_args):
        """获取所有测试用例，可选按project_id过滤。"""
        project_id = query_args.get("project_id")
        query = TestCase.query
        if project_id:
            query = query.filter_by(project_id=project_id)
        cases = query.all()
        return jsonify({"code": 0, "data": [c.to_dict() for c in cases]})

    @case_blp.arguments(CaseCreateSchema)
    @case_blp.response(200, MessageResponseSchema)
    def post(self, json_data):
        """创建新的测试用例。"""
        case = TestCase(
            name=json_data.get("name"),
            description=json_data.get("description"),
            project_id=json_data.get("project_id"),
            method=json_data.get("method", "GET"),
            url=json_data.get("url"),
            headers=json_data.get("headers"),
            params=json_data.get("params"),
            body=json_data.get("body"),
            expected_status=json_data.get("expected_status", 200),
            expected_response=json_data.get("expected_response"),
            priority=json_data.get("priority", 2),
        )
        db.session.add(case)
        db.session.commit()
        return jsonify({"code": 0, "data": case.to_dict()})


@case_blp.route("/<int:case_id>")
class CaseDetailView(MethodView):
    """测试用例详情、更新与删除"""

    @case_blp.response(200, MessageResponseSchema)
    def get(self, case_id):
        """获取单个测试用例。"""
        case = TestCase.query.get_or_404(case_id)
        return jsonify({"code": 0, "data": case.to_dict()})

    @case_blp.arguments(CaseUpdateSchema)
    @case_blp.response(200, MessageResponseSchema)
    def put(self, json_data, case_id):
        """更新测试用例。"""
        case = TestCase.query.get_or_404(case_id)

        for field in ["name", "description", "method", "url", "headers",
                      "params", "body", "expected_status", "expected_response",
                      "status", "priority"]:
            if field in json_data:
                setattr(case, field, json_data[field])

        db.session.commit()
        return jsonify({"code": 0, "data": case.to_dict()})

    @case_blp.response(200, MessageResponseSchema)
    def delete(self, case_id):
        """删除测试用例。"""
        case = TestCase.query.get_or_404(case_id)
        db.session.delete(case)
        db.session.commit()
        return jsonify({"code": 0, "message": "删除成功"})
