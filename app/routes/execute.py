"""
测试执行API路由。

作者: yandc
创建时间: 2026-01-13
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.case import TestCase
from app.services.executor import TestExecutor
from app.schemas.common import MessageResponseSchema
from app.schemas.execute import BatchExecuteSchema

execute_blp = Blueprint(
    "execute", __name__,
    url_prefix="/api/execute",
    description="测试执行"
)

# 向后兼容
execute_bp = execute_blp


@execute_blp.route("/case/<int:case_id>")
class ExecuteCaseView(MethodView):
    """执行单个测试用例"""

    @execute_blp.response(200, MessageResponseSchema)
    def post(self, case_id):
        """执行单个测试用例。"""
        case = TestCase.query.get_or_404(case_id)
        executor = TestExecutor()
        result = executor.run_case(case)
        return jsonify({"code": 0, "data": result.to_dict()})


@execute_blp.route("/batch")
class ExecuteBatchView(MethodView):
    """批量执行测试用例"""

    @execute_blp.arguments(BatchExecuteSchema)
    @execute_blp.response(200, MessageResponseSchema)
    def post(self, json_data):
        """执行多个测试用例。"""
        case_ids = json_data.get("case_ids", [])

        cases = TestCase.query.filter(TestCase.id.in_(case_ids)).all()
        executor = TestExecutor()
        results = executor.run_cases(cases)

        return jsonify({
            "code": 0,
            "data": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.status == "passed"),
                "failed": sum(1 for r in results if r.status == "failed"),
            }
        })


@execute_blp.route("/project/<int:project_id>")
class ExecuteProjectView(MethodView):
    """执行项目所有测试用例"""

    @execute_blp.response(200, MessageResponseSchema)
    def post(self, project_id):
        """执行项目中的所有测试用例。"""
        cases = TestCase.query.filter_by(project_id=project_id, status=1).all()
        executor = TestExecutor()
        results = executor.run_cases(cases)

        return jsonify({
            "code": 0,
            "data": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.status == "passed"),
                "failed": sum(1 for r in results if r.status == "failed"),
            }
        })
