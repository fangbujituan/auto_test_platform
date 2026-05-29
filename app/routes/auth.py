"""
身份验证API路由。

作者: yandc
创建时间: 2026-01-14
"""
import uuid
from flask import jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.user import User
from app.models.project_member import ProjectMember
from app.schemas.auth import (
    LoginRequestSchema,
    LoginResponseSchema,
    MessageResponseSchema,
    CurrentUserResponseSchema,
    InitUsersResponseSchema,
    UpdateProfileRequestSchema,
    ChangePasswordRequestSchema,
)

auth_blp = Blueprint(
    "auth", __name__,
    url_prefix="/api/auth",
    description="身份验证相关接口"
)


@auth_blp.route("/login")
class LoginView(MethodView):
    """用户登录"""

    @auth_blp.arguments(LoginRequestSchema)
    @auth_blp.response(200, LoginResponseSchema)
    @auth_blp.alt_response(400, schema=MessageResponseSchema, description="参数缺失")
    @auth_blp.alt_response(401, schema=MessageResponseSchema, description="认证失败")
    def post(self, json_data):
        """用户登录接口"""
        username = json_data.get("username")
        password = json_data.get("password")

        user = User.query.filter_by(username=username).first()

        if not user:
            return jsonify({"code": 1, "message": "用户不存在"}), 401

        if not user.check_password(password):
            return jsonify({"code": 1, "message": "密码错误"}), 401

        if user.is_active != 1:
            return jsonify({"code": 1, "message": "账号已被禁用"}), 401

        token = f"mock_token_{uuid.uuid4().hex}"

        return jsonify({
            "code": 0,
            "message": "登录成功",
            "data": {"token": token, "username": username}
        })


@auth_blp.route("/logout")
class LogoutView(MethodView):
    """用户登出"""

    @auth_blp.response(200, MessageResponseSchema)
    def post(self):
        """用户登出接口"""
        return jsonify({"code": 0, "message": "退出成功"})


@auth_blp.route("/current")
class CurrentUserView(MethodView):
    """当前用户信息"""

    @auth_blp.response(200, CurrentUserResponseSchema)
    def get(self):
        """获取当前登录用户信息"""
        # 手动调用 login_required 逻辑
        from app.utils.permission import get_current_user
        user = get_current_user()
        if not user:
            return jsonify({"code": 401, "message": "未登录或登录已过期"}), 401

        g.current_user = user

        memberships = ProjectMember.query.filter_by(user_id=user.id).all()
        roles = list(set([m.role.name for m in memberships]))

        return jsonify({
            "code": 0,
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "status": user.is_active,
                "roles": roles if roles else ["member"],
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "last_login": None
            }
        })


@auth_blp.route("/profile")
class ProfileUpdateView(MethodView):
    """更新用户资料"""

    @auth_blp.arguments(UpdateProfileRequestSchema)
    @auth_blp.response(200, MessageResponseSchema)
    @auth_blp.alt_response(401, schema=MessageResponseSchema, description="未登录")
    @auth_blp.alt_response(500, schema=MessageResponseSchema, description="服务器错误")
    def put(self, json_data):
        """更新当前用户资料（邮箱）"""
        from app.utils.permission import get_current_user
        user = get_current_user()
        if not user:
            return jsonify({"code": 401, "message": "未登录或登录已过期"}), 401

        try:
            user.email = json_data.get("email")
            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": user.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"操作失败: {str(e)}"}), 500


@auth_blp.route("/password")
class PasswordChangeView(MethodView):
    """修改密码"""

    @auth_blp.arguments(ChangePasswordRequestSchema)
    @auth_blp.response(200, MessageResponseSchema)
    @auth_blp.alt_response(400, schema=MessageResponseSchema, description="当前密码错误")
    @auth_blp.alt_response(401, schema=MessageResponseSchema, description="未登录")
    def put(self, json_data):
        """修改当前用户密码"""
        from app.utils.permission import get_current_user
        user = get_current_user()
        if not user:
            return jsonify({"code": 401, "message": "未登录或登录已过期"}), 401

        current_password = json_data.get("current_password")
        new_password = json_data.get("new_password")

        if not user.check_password(current_password):
            return jsonify({"code": 1, "message": "当前密码错误"}), 400

        try:
            user.set_password(new_password)
            db.session.commit()
            return jsonify({"code": 0, "message": "密码修改成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"操作失败: {str(e)}"}), 500


@auth_blp.route("/init")
class InitUsersView(MethodView):
    """初始化用户"""

    @auth_blp.response(200, InitUsersResponseSchema)
    @auth_blp.alt_response(500, schema=MessageResponseSchema, description="初始化失败")
    def post(self):
        """初始化默认用户（仅用于测试）"""
        try:
            if User.query.count() > 0:
                return jsonify({"code": 1, "message": "用户已存在，无需初始化"})

            admin = User(username="admin", email="admin@example.com")
            admin.set_password("admin123")

            test_user = User(username="test", email="test@example.com")
            test_user.set_password("test123")

            db.session.add(admin)
            db.session.add(test_user)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "初始化成功",
                "data": {"users": ["admin/admin123", "test/test123"]}
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"初始化失败: {str(e)}"}), 500


@auth_blp.route("/users")
class UsersListView(MethodView):
    """获取所有用户列表"""

    @auth_blp.response(200, MessageResponseSchema)
    def get(self):
        """获取系统中所有用户（用于添加成员时选择）。"""
        from app.utils.permission import get_current_user
        user = get_current_user()
        if not user:
            return jsonify({"code": 401, "message": "未登录"}), 401

        users = User.query.filter_by(is_active=1).all()
        return jsonify({
            "code": 0,
            "data": [
                {"id": u.id, "username": u.username, "email": u.email}
                for u in users
            ]
        })
