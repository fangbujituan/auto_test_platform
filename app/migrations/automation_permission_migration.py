"""
数据库迁移脚本 - 自动化管理权限。

为已有的角色添加 automation:* 权限项。
如果权限已存在则跳过，保证幂等。

作者: yandc
创建时间: 2026-04-13
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.role import Role, Permission


AUTOMATION_PERMISSIONS = [
    {"name": "automation:create", "resource": "automation", "action": "create", "description": "创建自动化任务"},
    {"name": "automation:read", "resource": "automation", "action": "read", "description": "查看自动化任务"},
    {"name": "automation:update", "resource": "automation", "action": "update", "description": "编辑自动化任务"},
    {"name": "automation:delete", "resource": "automation", "action": "delete", "description": "删除自动化任务"},
    {"name": "automation:execute", "resource": "automation", "action": "execute", "description": "执行自动化任务"},
]

# 角色 → 允许的 action 列表
ROLE_ACTIONS = {
    "admin": ["create", "read", "update", "delete", "execute"],
    "owner": ["create", "read", "update", "delete", "execute"],
    "member": ["create", "read", "update", "execute"],
    "viewer": ["read"],
}


def run_migration():
    app = create_app()

    with app.app_context():
        # 1. 确保新表已创建
        db.create_all()
        print("[OK] 数据表已同步")

        # 2. 创建权限记录（跳过已存在的）
        perm_map = {}
        for pdata in AUTOMATION_PERMISSIONS:
            existing = Permission.query.filter_by(name=pdata["name"]).first()
            if existing:
                perm_map[pdata["action"]] = existing
                print(f"[SKIP] 权限已存在: {pdata['name']}")
            else:
                perm = Permission(**pdata)
                db.session.add(perm)
                db.session.flush()
                perm_map[pdata["action"]] = perm
                print(f"[OK] 创建权限: {pdata['name']}")

        # 3. 为各角色分配权限
        for role_name, actions in ROLE_ACTIONS.items():
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                print(f"[WARN] 角色不存在: {role_name}")
                continue

            existing_perm_ids = {p.id for p in role.permissions}
            added = 0
            for action in actions:
                perm = perm_map.get(action)
                if perm and perm.id not in existing_perm_ids:
                    role.permissions.append(perm)
                    added += 1

            if added:
                print(f"[OK] 角色 {role_name}: 新增 {added} 个自动化权限")
            else:
                print(f"[SKIP] 角色 {role_name}: 权限已完整")

        db.session.commit()
        print("\n自动化权限迁移完成！")


if __name__ == "__main__":
    run_migration()
