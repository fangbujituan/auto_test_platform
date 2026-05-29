"""
角色和权限API路由。

作者: yandc
创建时间: 2026-01-15
"""
from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.role import Role, Permission
from app.utils.permission import login_required
from app.schemas.common import MessageResponseSchema

role_blp = Blueprint(
    "role", __name__,
    url_prefix="/api/roles",
    description="角色和权限管理"
)

# 向后兼容
role_bp = role_blp


@role_blp.route("")
class RolesView(MethodView):
    """角色列表"""

    @role_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取所有角色。"""
        roles = Role.query.all()
        return jsonify({"code": 0, "data": [r.to_dict() for r in roles]})


@role_blp.route("/permissions")
class PermissionsView(MethodView):
    """权限列表"""

    @role_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取所有权限。"""
        permissions = Permission.query.all()
        return jsonify({"code": 0, "data": [p.to_dict() for p in permissions]})


@role_blp.route("/init")
class InitRolesView(MethodView):
    """初始化角色和权限"""

    @role_blp.response(200, MessageResponseSchema)
    @role_blp.alt_response(500, schema=MessageResponseSchema, description="初始化失败")
    def post(self):
        """初始化默认角色和权限。"""
        try:
            # 检查是否已初始化
            if Role.query.count() > 0:
                return jsonify({
                    "code": 1,
                    "message": "角色已存在，无需初始化"
                })

            # 创建权限
            permissions_data = [
                # 项目权限
                {"name": "project:read", "resource": "project", "action": "read", "description": "查看项目"},
                {"name": "project:create", "resource": "project", "action": "create", "description": "创建项目"},
                {"name": "project:update", "resource": "project", "action": "update", "description": "编辑项目"},
                {"name": "project:delete", "resource": "project", "action": "delete", "description": "删除项目"},
                {"name": "project:manage_member", "resource": "project", "action": "manage_member", "description": "管理项目成员"},

                # 用例权限
                {"name": "case:read", "resource": "case", "action": "read", "description": "查看用例"},
                {"name": "case:create", "resource": "case", "action": "create", "description": "创建用例"},
                {"name": "case:update", "resource": "case", "action": "update", "description": "编辑用例"},
                {"name": "case:delete", "resource": "case", "action": "delete", "description": "删除用例"},

                # 执行权限
                {"name": "execute:run", "resource": "execute", "action": "run", "description": "执行测试"},
                {"name": "execute:read", "resource": "execute", "action": "read", "description": "查看执行结果"},
            ]

            permissions = []
            for perm_data in permissions_data:
                perm = Permission(**perm_data)
                db.session.add(perm)
                permissions.append(perm)

            db.session.flush()  # 获取权限ID

            # 创建角色
            # 1. 平台管理员（所有权限）
            admin_role = Role(name="admin", description="平台管理员", is_system=1)
            admin_role.permissions = permissions
            db.session.add(admin_role)

            # 2. 项目负责人（项目内所有权限）
            owner_role = Role(name="owner", description="项目负责人", is_system=1)
            owner_role.permissions = permissions
            db.session.add(owner_role)

            # 3. 项目成员（读写权限，不能删除项目和管理成员）
            member_perms = [p for p in permissions if p.action in ['read', 'create', 'update', 'run']]
            member_role = Role(name="member", description="项目成员", is_system=1)
            member_role.permissions = member_perms
            db.session.add(member_role)

            # 4. 只读用户（只能查看）
            viewer_perms = [p for p in permissions if p.action == 'read']
            viewer_role = Role(name="viewer", description="只读用户", is_system=1)
            viewer_role.permissions = viewer_perms
            db.session.add(viewer_role)

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "角色和权限初始化成功",
                "data": {
                    "roles": ["admin", "owner", "member", "viewer"],
                    "permissions_count": len(permissions)
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"初始化失败: {str(e)}"
            }), 500
