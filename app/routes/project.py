"""
项目API路由。

作者: yandc
创建时间: 2026-01-13
"""
from flask import request, jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.role import Role
from app.models.api_folder import ApiFolder
from app.models.api import Api
from app.models.case import TestCase
from app.models.test_case import TestCaseManagement, TestCaseApiBinding
from app.models.bug import Bug
from app.models.result import TestResult
from app.models.module import Module
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema

project_blp = Blueprint(
    "project", __name__,
    url_prefix="/api/projects",
    description="项目管理"
)

# 向后兼容
project_bp = project_blp


@project_blp.route("")
class ProjectsView(MethodView):
    """项目列表与创建"""

    @project_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取当前用户有权访问的所有项目。"""
        user = g.current_user

        memberships = ProjectMember.query.filter_by(user_id=user.id).all()
        project_ids = [m.project_id for m in memberships]

        if not project_ids:
            return jsonify({"code": 0, "data": []})

        projects = Project.query.filter(Project.id.in_(project_ids)).all()

        result = []
        for project in projects:
            project_dict = project.to_dict()
            member = next(
                (m for m in memberships if m.project_id == project.id),
                None
            )
            if member:
                project_dict['role'] = member.role.name
            result.append(project_dict)

        return jsonify({"code": 0, "data": result})

    @project_blp.response(200, MessageResponseSchema)
    @project_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    def post(self):
        """创建新项目并将创建者设为负责人。"""
        data = request.get_json()
        user = g.current_user

        try:
            project = Project(
                name=data.get("name"),
                description=data.get("description"),
            )
            db.session.add(project)
            db.session.flush()

            owner_role = Role.query.filter_by(name='owner').first()
            if not owner_role:
                db.session.rollback()
                return jsonify({
                    "code": 1,
                    "message": "系统角色未初始化，请先初始化角色"
                }), 500

            member = ProjectMember(
                project_id=project.id,
                user_id=user.id,
                role_id=owner_role.id
            )
            db.session.add(member)

            default_folders = [
                {"name": "用户模块", "description": "用户相关接口", "sort_order": 1},
                {"name": "系统模块", "description": "系统相关接口", "sort_order": 2},
                {"name": "业务模块", "description": "业务相关接口", "sort_order": 3},
            ]

            for folder_data in default_folders:
                folder = ApiFolder(
                    name=folder_data["name"],
                    description=folder_data["description"],
                    project_id=project.id,
                    parent_id=None,
                    sort_order=folder_data["sort_order"]
                )
                db.session.add(folder)

            db.session.commit()

            result = project.to_dict()
            result['role'] = 'owner'

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": result
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}"
            }), 500


@project_blp.route("/<int:project_id>")
class ProjectDetailView(MethodView):
    """项目详情、更新与删除"""

    @project_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('update')
    def put(self, project_id):
        """更新项目。"""
        project = Project.query.get_or_404(project_id)
        data = request.get_json()
        project.name = data.get("name", project.name)
        project.description = data.get("description", project.description)
        project.status = data.get("status", project.status)
        db.session.commit()
        return jsonify({"code": 0, "data": project.to_dict()})

    @project_blp.response(200, MessageResponseSchema)
    @project_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id):
        """删除项目及其所有关联数据。"""
        project = Project.query.get_or_404(project_id)

        try:
            # 1. 删除测试结果
            case_ids = [c.id for c in TestCase.query.filter_by(
                project_id=project_id
            ).all()]
            if case_ids:
                TestResult.query.filter(
                    TestResult.case_id.in_(case_ids)
                ).delete(synchronize_session=False)

            # 2. 删除测试用例-API绑定
            tcm_ids = [t.id for t in TestCaseManagement.query.filter_by(
                project_id=project_id
            ).all()]
            if tcm_ids:
                TestCaseApiBinding.query.filter(
                    TestCaseApiBinding.test_case_id.in_(tcm_ids)
                ).delete(synchronize_session=False)

            # 3. 删除测试用例管理
            TestCaseManagement.query.filter_by(
                project_id=project_id
            ).delete()

            # 4. 删除API测试用例
            TestCase.query.filter_by(project_id=project_id).delete()

            # 5. 删除Bug
            Bug.query.filter_by(project_id=project_id).delete()

            # 6. 删除API接口
            Api.query.filter_by(project_id=project_id).delete()

            # 7. 删除模块
            Module.query.filter_by(
                project_id=project_id
            ).update({"parent_id": None}, synchronize_session=False)
            Module.query.filter_by(project_id=project_id).delete()

            # 8. 删除目录
            ApiFolder.query.filter_by(
                project_id=project_id
            ).update({"parent_id": None}, synchronize_session=False)
            ApiFolder.query.filter_by(project_id=project_id).delete()

            # 9. 删除项目成员
            ProjectMember.query.filter_by(project_id=project_id).delete()

            # 10. 删除项目本身
            db.session.delete(project)
            db.session.commit()

            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}"
            }), 500
