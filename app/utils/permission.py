"""
权限工具和装饰器。

作者: yandc
创建时间: 2026-01-15
"""
from functools import wraps
from flask import request, jsonify, g
from app.models.user import User
from app.models.project_member import ProjectMember
from app.models.role import Role


def get_current_user():
    """从请求头获取当前用户。"""
    # 从请求头获取token（简化版，实际应该验证JWT）
    token = request.headers.get('Authorization')
    if not token:
        return None
    
    # 简化处理：从token中提取用户名
    # 实际应该解析JWT token
    if token.startswith('Bearer '):
        token = token[7:]
    
    # 这里简化处理，实际应该从token解析用户信息
    # 暂时从token中提取用户名（mock_token_{uuid}_username格式）
    username = request.headers.get('X-Username')
    if username:
        return User.query.filter_by(username=username).first()
    
    return None


def login_required(f):
    """要求用户登录的装饰器。"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "code": 401,
                "message": "未登录或登录已过期"
            }), 401
        
        g.current_user = user
        g.user = user  # 为了兼容性，同时设置g.user
        return f(*args, **kwargs)
    
    return decorated_function


def check_project_permission(action):
    """
    检查项目级权限的装饰器。
    
    参数:
        action: 操作类型，如 'read', 'update', 'delete', 'manage_member'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = g.get('current_user')
            if not user:
                return jsonify({
                    "code": 401,
                    "message": "未登录"
                }), 401
            
            # 获取项目ID（从路径参数或请求体）
            project_id = kwargs.get('project_id')
            if not project_id and request.method == 'POST':
                data = request.get_json()
                project_id = data.get('project_id')
            
            if not project_id:
                return jsonify({
                    "code": 400,
                    "message": "缺少项目ID"
                }), 400
            
            # 检查用户是否是平台管理员
            admin_role = Role.query.filter_by(name='admin').first()
            if admin_role:
                admin_member = ProjectMember.query.filter_by(
                    user_id=user.id,
                    role_id=admin_role.id
                ).first()
                if admin_member:
                    # 管理员拥有所有权限
                    return f(*args, **kwargs)
            
            # 检查用户在项目中的角色
            member = ProjectMember.query.filter_by(
                project_id=project_id,
                user_id=user.id
            ).first()
            
            if not member:
                return jsonify({
                    "code": 403,
                    "message": "无权访问该项目"
                }), 403
            
            # 检查角色权限
            role = member.role
            has_permission = False
            
            for permission in role.permissions:
                if permission.resource == 'project' and permission.action == action:
                    has_permission = True
                    break
            
            if not has_permission:
                return jsonify({
                    "code": 403,
                    "message": f"无权执行该操作: {action}"
                }), 403
            
            # 将项目成员信息存入g，供后续使用
            g.project_member = member
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def is_project_owner(user_id, project_id):
    """检查用户是否是项目负责人。"""
    member = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=user_id
    ).first()
    
    if not member:
        return False
    
    return member.role.name == 'owner'


def is_admin(user_id):
    """检查用户是否是平台管理员。"""
    admin_role = Role.query.filter_by(name='admin').first()
    if not admin_role:
        return False
    
    # 平台管理员不绑定具体项目，可以通过特殊标记判断
    # 这里简化处理：检查用户是否有admin角色的任意项目成员记录
    member = ProjectMember.query.filter_by(
        user_id=user_id,
        role_id=admin_role.id
    ).first()
    
    return member is not None


def require_permission(permission_code):
    """
    要求特定权限的装饰器。
    
    参数:
        permission_code: 权限代码，格式为 'resource:action'，如 'module:create', 'test_case:read'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({
                    "code": 401,
                    "message": "未登录或登录已过期"
                }), 401
            
            g.current_user = user
            
            # 解析权限代码
            try:
                resource, action = permission_code.split(':')
            except ValueError:
                return jsonify({
                    "code": 400,
                    "message": "权限代码格式错误"
                }), 400
            
            # 检查用户是否有该权限
            has_permission = False
            
            # 获取用户所有的项目成员记录
            members = ProjectMember.query.filter_by(user_id=user.id).all()
            
            for member in members:
                role = member.role
                for perm in role.permissions:
                    if perm.resource == resource and perm.action == action:
                        has_permission = True
                        break
                if has_permission:
                    break
            
            if not has_permission:
                return jsonify({
                    "code": 403,
                    "message": f"无权执行该操作: {permission_code}"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
