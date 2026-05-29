"""
初始化测试用例管理模块的权限。

作者: yandc
创建时间: 2026-01-19
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.role import Role, Permission


def init_permissions():
    """初始化权限。"""
    app = create_app()
    
    with app.app_context():
        print("开始初始化测试用例管理权限...")
        
        # 定义权限
        permissions_data = [
            # 模块管理权限
            {"name": "创建模块", "resource": "module", "action": "create", "description": "创建测试模块"},
            {"name": "查看模块", "resource": "module", "action": "read", "description": "查看测试模块"},
            {"name": "更新模块", "resource": "module", "action": "update", "description": "更新测试模块"},
            {"name": "删除模块", "resource": "module", "action": "delete", "description": "删除测试模块"},
            
            # 测试用例权限
            {"name": "创建测试用例", "resource": "test_case", "action": "create", "description": "创建测试用例"},
            {"name": "查看测试用例", "resource": "test_case", "action": "read", "description": "查看测试用例"},
            {"name": "更新测试用例", "resource": "test_case", "action": "update", "description": "更新测试用例"},
            {"name": "删除测试用例", "resource": "test_case", "action": "delete", "description": "删除测试用例"},
        ]
        
        # 创建权限
        created_permissions = []
        for perm_data in permissions_data:
            perm = Permission.query.filter_by(
                resource=perm_data["resource"],
                action=perm_data["action"]
            ).first()
            if not perm:
                perm = Permission(**perm_data)
                db.session.add(perm)
                created_permissions.append(perm)
                print(f"✓ 创建权限: {perm_data['name']} ({perm_data['resource']}:{perm_data['action']})")
            else:
                print(f"- 权限已存在: {perm_data['name']} ({perm_data['resource']}:{perm_data['action']})")
        
        db.session.commit()
        
        # 为管理员角色添加所有权限
        admin_role = Role.query.filter_by(name="admin").first()
        if admin_role:
            for perm in created_permissions:
                if perm not in admin_role.permissions:
                    admin_role.permissions.append(perm)
            db.session.commit()
            print(f"\n✓ 已将所有权限添加到管理员角色")
        
        print("\n权限初始化完成！")


if __name__ == "__main__":
    init_permissions()
