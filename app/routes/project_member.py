"""
项目成员API路由。

作者: yandc
创建时间: 2026-01-15
"""
from flask import request, jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.user import User
from app.models.role import Role
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema

member_blp = Blueprint(
    "project_member", __name__,
    url_prefix="/api/project-members",
    description="项目成员管理"
)

# 向后兼容
member_bp = member_blp


@member_blp.route("/<int:project_id>")
class ProjectMembersView(MethodView):
    """项目成员列表"""

    @member_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有成员。"""
        members = ProjectMember.query.filter_by(project_id=project_id).all()
        return jsonify({
            "code": 0,
            "data": [m.to_dict() for m in members]
        })


@member_blp.route("")
class MemberAddView(MethodView):
    """添加项目成员"""

    @member_blp.response(200, MessageResponseSchema)
    @member_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @member_blp.alt_response(404, schema=MessageResponseSchema, description="资源不存在")
    @login_required
    @check_project_permission('manage_member')
    def post(self):
        """添加成员到项目。"""
        data = request.get_json()
        project_id = data.get('project_id')
        user_id = data.get('user_id')
        role_name = data.get('role', 'member')

        if not all([project_id, user_id]):
            return jsonify({
                "code": 1, "message": "缺少必要参数"
            }), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 1, "message": "项目不存在"}), 404

        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 1, "message": "用户不存在"}), 404

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return jsonify({"code": 1, "message": "角色不存在"}), 404

        existing = ProjectMember.query.filter_by(
            project_id=project_id, user_id=user_id
        ).first()
        if existing:
            return jsonify({
                "code": 1, "message": "用户已是项目成员"
            }), 400

        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role_id=role.id
        )
        db.session.add(member)
        db.session.commit()

        return jsonify({
            "code": 0,
            "message": "添加成功",
            "data": member.to_dict()
        })


@member_blp.route("/detail/<int:member_id>")
class MemberDetailView(MethodView):
    """更新与移除项目成员"""

    @member_blp.response(200, MessageResponseSchema)
    @member_blp.alt_response(403, schema=MessageResponseSchema, description="无权限")
    @login_required
    def put(self, member_id):
        """更新项目成员角色。"""
        member = ProjectMember.query.get_or_404(member_id)

        # 检查权限
        user = g.current_user
        project_member = ProjectMember.query.filter_by(
            project_id=member.project_id,
            user_id=user.id
        ).first()

        if not project_member:
            return jsonify({"code": 403, "message": "无权限"}), 403

        has_permission = False
        for perm in project_member.role.permissions:
            if perm.resource == 'project' and perm.action == 'manage_member':
                has_permission = True
                break

        if not has_permission:
            return jsonify({"code": 403, "message": "无权限"}), 403

        data = request.get_json()
        role_name = data.get('role')

        if not role_name:
            return jsonify({"code": 1, "message": "缺少角色参数"}), 400

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return jsonify({"code": 1, "message": "角色不存在"}), 404

        member.role_id = role.id
        db.session.commit()

        return jsonify({
            "code": 0,
            "message": "更新成功",
            "data": member.to_dict()
        })

    @member_blp.response(200, MessageResponseSchema)
    @member_blp.alt_response(403, schema=MessageResponseSchema, description="无权限")
    @login_required
    def delete(self, member_id):
        """从项目中移除成员。"""
        member = ProjectMember.query.get_or_404(member_id)

        current_user = g.current_user
        project_member = ProjectMember.query.filter_by(
            project_id=member.project_id,
            user_id=current_user.id
        ).first()

        if not project_member:
            return jsonify({"code": 403, "message": "无权限"}), 403

        has_permission = False
        for perm in project_member.role.permissions:
            if perm.resource == 'project' and perm.action == 'manage_member':
                has_permission = True
                break

        if not has_permission:
            return jsonify({"code": 403, "message": "无权限"}), 403

        if member.role.name == 'owner':
            return jsonify({
                "code": 1, "message": "不能移除项目负责人"
            }), 400

        db.session.delete(member)
        db.session.commit()

        return jsonify({"code": 0, "message": "移除成功"})
