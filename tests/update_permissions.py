"""
更新权限系统，添加模块和测试用例权限。

作者: yandc
创建时间: 2026-01-19
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.role import Role, Permission


def update_permissions():
    """更新权限系统。"""
    app = create_app()
    
    with app.app_context():
        print("开始更新权限系统...")
        
        # 新增的权限
        new_permissions_data = [
            # 模块权限
            {"name": "module:read", "resource": "module", "action": "read", "description": "查看模块"},
            {"name": "module:create", "resource": "module", "action": "create", "description": "创建模块"},
            {"name": "module:update", "resource": "module", "action": "update", "description": "编辑模块"},
            {"name": "module:delete", "resource": "module", "action": "delete", "description": "删除模块"},
            
            # 测试用例权限
            {"name": "test_case:read", "resource": "test_case", "action": "read", "description": "查看测试用例"},
            {"name": "test_case:create", "resource": "test_case", "action": "create", "description": "创建测试用例"},
            {"name": "test_case:update", "resource": "test_case", "action": "update", "description": "编辑测试用例"},
            {"name": "test_case:delete", "resource": "test_case", "action": "delete", "description": "删除测试用例"},
        ]
        
        # 添加新权限
        new_permissions = []
        for perm_data in new_permissions_data:
            # 检查权限是否已存在
            existing = Permission.query.filter_by(name=perm_data["name"]).first()
            if existing:
                print(f"权限 {perm_data['name']} 已存在，跳过")
                new_permissions.append(existing)
                continue
            
            perm = Permission(**perm_data)
            db.session.add(perm)
            new_permissions.append(perm)
            print(f"创建权限: {perm_data['name']}")
        
        db.session.flush()
        
        # 更新角色权限
        # 1. admin 和 owner 角色拥有所有权限
        admin_role = Role.query.filter_by(name="admin").first()
        owner_role = Role.query.filter_by(name="owner").first()
        
        all_permissions = Permission.query.all()
        
        if admin_role:
            admin_role.permissions = all_permissions
            print("更新 admin 角色权限")
        
        if owner_role:
            owner_role.permissions = all_permissions
            print("更新 owner 角色权限")
        
        # 2. member 角色拥有读写权限
        member_role = Role.query.filter_by(name="member").first()
        if member_role:
            member_perms = [p for p in all_permissions if p.action in ['read', 'create', 'update', 'run']]
            member_role.permissions = member_perms
            print("更新 member 角色权限")
        
        # 3. viewer 角色只有读权限
        viewer_role = Role.query.filter_by(name="viewer").first()
        if viewer_role:
            viewer_perms = [p for p in all_permissions if p.action == 'read']
            viewer_role.permissions = viewer_perms
            print("更新 viewer 角色权限")
        
        db.session.commit()
        print("权限系统更新完成！")
        
        # 显示统计信息
        print(f"\n总权限数: {Permission.query.count()}")
        print(f"总角色数: {Role.query.count()}")


if __name__ == "__main__":
    update_permissions()
