"""
Initialize permission system.

作者: yandc
Created: 2026-01-15

Usage:
    python -m app.init_permission
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.role import Role, Permission
from app.models.user import User
from app.models.project_member import ProjectMember


def init_permissions():
    """Initialize roles and permissions."""
    app = create_app()
    
    with app.app_context():
        # 检查是否已初始化
        if Role.query.count() > 0:
            print("角色已存在，跳过初始化")
            return
        
        print("开始初始化权限系统...")
        
        # 创建权限
        permissions_data = [
            # 项目权限
            {"name": "project:read", "resource": "project", "action": "read", "description": "查看项目"},
            {"name": "project:create", "resource": "project", "action": "create", "description": "创建项目"},
            {"name": "project:update", "resource": "project", "action": "update", "description": "编辑项目"},
            {"name": "project:delete", "resource": "project", "action": "delete", "description": "删除项目"},
            {"name": "project:manage_member", "resource": "project", "action": "manage_member", "description": "管理项目成员"},
            
            # 用例权限（保留旧的case权限以兼容）
            {"name": "case:read", "resource": "case", "action": "read", "description": "查看用例"},
            {"name": "case:create", "resource": "case", "action": "create", "description": "创建用例"},
            {"name": "case:update", "resource": "case", "action": "update", "description": "编辑用例"},
            {"name": "case:delete", "resource": "case", "action": "delete", "description": "删除用例"},
            
            # 测试用例权限
            {"name": "test_case:read", "resource": "test_case", "action": "read", "description": "查看测试用例"},
            {"name": "test_case:create", "resource": "test_case", "action": "create", "description": "创建测试用例"},
            {"name": "test_case:update", "resource": "test_case", "action": "update", "description": "编辑测试用例"},
            {"name": "test_case:delete", "resource": "test_case", "action": "delete", "description": "删除测试用例"},
            
            # 执行权限
            {"name": "execute:run", "resource": "execute", "action": "run", "description": "执行测试"},
            {"name": "execute:read", "resource": "execute", "action": "read", "description": "查看执行结果"},
            
            # 自动化管理权限
            {"name": "automation:create", "resource": "automation", "action": "create", "description": "创建自动化任务"},
            {"name": "automation:read", "resource": "automation", "action": "read", "description": "查看自动化任务"},
            {"name": "automation:update", "resource": "automation", "action": "update", "description": "编辑自动化任务"},
            {"name": "automation:delete", "resource": "automation", "action": "delete", "description": "删除自动化任务"},
            {"name": "automation:execute", "resource": "automation", "action": "execute", "description": "执行自动化任务"},
        ]
        
        permissions = []
        for perm_data in permissions_data:
            perm = Permission(**perm_data)
            db.session.add(perm)
            permissions.append(perm)
        
        db.session.flush()
        print(f"创建了 {len(permissions)} 个权限")
        
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
        member_perms = [p for p in permissions if p.action in ['read', 'create', 'update', 'run', 'execute']]
        member_role = Role(name="member", description="项目成员", is_system=1)
        member_role.permissions = member_perms
        db.session.add(member_role)
        
        # 4. 只读用户（只能查看）
        viewer_perms = [p for p in permissions if p.action == 'read']
        viewer_role = Role(name="viewer", description="只读用户", is_system=1)
        viewer_role.permissions = viewer_perms
        db.session.add(viewer_role)
        
        db.session.commit()
        print("创建了 4 个角色: admin, owner, member, viewer")
        print("权限系统初始化完成！")


if __name__ == "__main__":
    init_permissions()
