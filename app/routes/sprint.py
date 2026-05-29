"""
冲刺管理路由。

作者: yandc
创建时间: 2026-03-12
"""
from flask import request, jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.sprint import Sprint
from app.models.operation_log import OperationLog
from app.utils.permission import login_required
from app.schemas.common import MessageResponseSchema
from app.schemas.requirement import SprintCreateSchema, SprintUpdateSchema, SprintQuerySchema

sprint_blp = Blueprint(
    "sprint", __name__,
    url_prefix="/api/sprints",
    description="冲刺管理"
)


def log_operation(api_name, action, target_type=None, target_id=None, project_id=None, detail=None):
    """记录操作日志。"""
    current_user = g.get("current_user")
    if not current_user:
        return
    log = OperationLog(
        api_name=api_name,
        action=action,
        operator_id=current_user.id,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.session.add(log)


@sprint_blp.route("")
class SprintsView(MethodView):
    """冲刺列表与创建"""

    @sprint_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取冲刺列表。"""
        project_id = request.args.get("project_id", type=int)
        if not project_id:
            return jsonify({"code": 1, "message": "缺少project_id参数"}), 400

        query = Sprint.query.filter_by(project_id=project_id)
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
        sprints = query.order_by(Sprint.start_date.desc()).all()
        return jsonify({"code": 0, "data": [s.to_dict() for s in sprints]})

    @sprint_blp.response(201, MessageResponseSchema)
    @sprint_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    def post(self):
        """创建新的冲刺。"""
        data = request.get_json()
        try:
            current_user = g.get("current_user")
            sprint = Sprint(
                name=data["name"],
                project_id=data["project_id"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                creator_id=current_user.id,
                goal=data.get("goal"),
                status=data.get("status", "planning"),
            )
            db.session.add(sprint)
            db.session.flush()
            log_operation("POST /api/sprints", f"创建冲刺: {sprint.name}", "sprint", sprint.id, sprint.project_id)
            db.session.commit()
            return jsonify({"code": 0, "message": "创建成功", "data": sprint.to_dict()}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@sprint_blp.route("/<int:sprint_id>")
class SprintDetailView(MethodView):
    """冲刺详情、更新与删除"""

    @sprint_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self, sprint_id):
        """获取冲刺详情。"""
        sprint = Sprint.query.get_or_404(sprint_id)
        return jsonify({"code": 0, "data": sprint.to_dict()})

    @sprint_blp.response(200, MessageResponseSchema)
    @sprint_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    def put(self, sprint_id):
        """更新冲刺。"""
        sprint = Sprint.query.get_or_404(sprint_id)
        data = request.get_json()
        try:
            for field in ["name", "start_date", "end_date", "goal", "status"]:
                if field in data:
                    setattr(sprint, field, data[field])
            log_operation("PUT /api/sprints", f"更新冲刺: {sprint.name}", "sprint", sprint.id, sprint.project_id)
            db.session.commit()
            return jsonify({"code": 0, "message": "更新成功", "data": sprint.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @sprint_blp.response(200, MessageResponseSchema)
    @sprint_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    def delete(self, sprint_id):
        """删除冲刺。"""
        sprint = Sprint.query.get_or_404(sprint_id)
        try:
            log_operation("DELETE /api/sprints", f"删除冲刺: {sprint.name}", "sprint", sprint.id, sprint.project_id)
            db.session.delete(sprint)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500
