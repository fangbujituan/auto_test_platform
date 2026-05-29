"""
仪表盘API路由。

作者: yandc
创建时间: 2026-02-12
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.project import Project
from app.models.api_folder import ApiFolder
from app.models.api import Api
from app.models.test_case import TestCaseManagement
from app.models.bug import Bug
from app.utils.permission import login_required
from app.schemas.common import MessageResponseSchema

dashboard_blp = Blueprint(
    "dashboard", __name__,
    url_prefix="/api/dashboard",
    description="仪表盘统计"
)

# 向后兼容
dashboard_bp = dashboard_blp


@dashboard_blp.route("/stats")
class DashboardStatsView(MethodView):
    """仪表盘统计数据"""

    @dashboard_blp.response(200, MessageResponseSchema)
    @dashboard_blp.alt_response(500, schema=MessageResponseSchema, description="获取统计数据失败")
    @login_required
    def get(self):
        """获取仪表盘全局统计数据。"""
        try:
            data = {
                "project_count": Project.query.count(),
                "folder_count": ApiFolder.query.count(),
                "api_count": Api.query.count(),
                "test_case_count": TestCaseManagement.query.count(),
                "bug_count": Bug.query.count(),
            }
            return jsonify({"code": 0, "data": data})
        except Exception as e:
            return jsonify({"code": 1, "message": f"获取统计数据失败: {str(e)}"}), 500
