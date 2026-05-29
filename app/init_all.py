"""
一键初始化脚本：创建数据库、表结构、默认用户、权限、AI模板。

在新电脑上部署项目时，只需运行：
    python -m app.init_all

作者: yandc
"""
import sys
import pymysql
from app.config.settings import Config


def ensure_database():
    """确保数据库存在，不存在则自动创建。"""
    print("[1/5] 检查数据库...")
    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.close()
        print(f"  ✓ 数据库 '{Config.MYSQL_DATABASE}' 已就绪")
    except Exception as e:
        print(f"  ✗ 数据库连接失败: {e}")
        print("  请检查 MySQL 是否启动，以及 settings.py 中的连接配置是否正确")
        sys.exit(1)


def create_tables(app):
    """创建所有表（已存在的表不受影响）。"""
    print("[2/5] 创建数据表...")
    from app.models.base import db
    with app.app_context():
        db.create_all()
        print("  ✓ 所有数据表已就绪")


def auto_migrate(app):
    """自动检测并补齐已有表的缺失列。"""
    print("[3/5] 检查表结构迁移...")
    from app.models.base import db
    from sqlalchemy import inspect, text

    # 定义需要检查的列: (表名, 列名, SQL定义)
    expected_columns = [
        ("apis", "module", "VARCHAR(200) NULL COMMENT '所属模块'"),
        ("apis", "service", "VARCHAR(200) NULL COMMENT '所属服务'"),
        ("apis", "prefix_url_id", "INT NULL COMMENT '绑定的前置URL ID'"),
    ]

    with app.app_context():
        inspector = inspect(db.engine)
        migrated = 0

        for table, column, col_def in expected_columns:
            if not inspector.has_table(table):
                continue
            existing = [c["name"] for c in inspector.get_columns(table)]
            if column not in existing:
                db.session.execute(
                    text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {col_def}")
                )
                db.session.commit()
                print(f"  ✓ 补齐列: {table}.{column}")
                migrated += 1

        if migrated == 0:
            print("  ✓ 表结构无需迁移")


def init_users(app):
    """初始化默认用户。"""
    print("[4/5] 初始化用户和权限...")
    from app.models.base import db
    from app.models.user import User
    from app.models.role import Role, Permission

    with app.app_context():
        # --- 用户 ---
        if User.query.count() > 0:
            print("  - 用户已存在，跳过")
        else:
            admin = User(username="admin", email="admin@example.com")
            admin.set_password("admin123")
            test_user = User(username="test", email="test@example.com")
            test_user.set_password("test123")
            db.session.add_all([admin, test_user])
            db.session.commit()
            print("  ✓ 创建用户: admin/admin123, test/test123")

        # --- 基础权限 ---
        if Role.query.count() > 0:
            print("  - 角色已存在，跳过基础权限初始化")
        else:
            permissions_data = [
                {"name": "project:read", "resource": "project", "action": "read", "description": "查看项目"},
                {"name": "project:create", "resource": "project", "action": "create", "description": "创建项目"},
                {"name": "project:update", "resource": "project", "action": "update", "description": "编辑项目"},
                {"name": "project:delete", "resource": "project", "action": "delete", "description": "删除项目"},
                {"name": "project:manage_member", "resource": "project", "action": "manage_member", "description": "管理项目成员"},
                {"name": "case:read", "resource": "case", "action": "read", "description": "查看用例"},
                {"name": "case:create", "resource": "case", "action": "create", "description": "创建用例"},
                {"name": "case:update", "resource": "case", "action": "update", "description": "编辑用例"},
                {"name": "case:delete", "resource": "case", "action": "delete", "description": "删除用例"},
                {"name": "test_case:read", "resource": "test_case", "action": "read", "description": "查看测试用例"},
                {"name": "test_case:create", "resource": "test_case", "action": "create", "description": "创建测试用例"},
                {"name": "test_case:update", "resource": "test_case", "action": "update", "description": "编辑测试用例"},
                {"name": "test_case:delete", "resource": "test_case", "action": "delete", "description": "删除测试用例"},
                {"name": "execute:run", "resource": "execute", "action": "run", "description": "执行测试"},
                {"name": "execute:read", "resource": "execute", "action": "read", "description": "查看执行结果"},
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

            # 模块管理权限（测试用例模块）
            module_perms_data = [
                {"name": "创建模块", "resource": "module", "action": "create",
                 "description": "创建测试模块"},
                {"name": "查看模块", "resource": "module", "action": "read",
                 "description": "查看测试模块"},
                {"name": "更新模块", "resource": "module", "action": "update",
                 "description": "更新测试模块"},
                {"name": "删除模块", "resource": "module", "action": "delete",
                 "description": "删除测试模块"},
            ]
            for perm_data in module_perms_data:
                existing = Permission.query.filter_by(
                    resource=perm_data["resource"],
                    action=perm_data["action"],
                ).first()
                if not existing:
                    perm = Permission(**perm_data)
                    db.session.add(perm)
                    permissions.append(perm)
            db.session.flush()

            # 创建角色
            admin_role = Role(
                name="admin", description="平台管理员", is_system=1
            )
            admin_role.permissions = permissions
            db.session.add(admin_role)

            owner_role = Role(
                name="owner", description="项目负责人", is_system=1
            )
            owner_role.permissions = permissions
            db.session.add(owner_role)

            member_perms = [
                p for p in permissions
                if p.action in [
                    "read", "create", "update", "run", "execute"
                ]
            ]
            member_role = Role(
                name="member", description="项目成员", is_system=1
            )
            member_role.permissions = member_perms
            db.session.add(member_role)

            viewer_perms = [
                p for p in permissions if p.action == "read"
            ]
            viewer_role = Role(
                name="viewer", description="只读用户", is_system=1
            )
            viewer_role.permissions = viewer_perms
            db.session.add(viewer_role)

            db.session.commit()
            print("  ✓ 创建 {} 个权限, 4 个角色".format(len(permissions)))


def init_ai_templates(app):
    """初始化 AI 内置提示词模板。"""
    print("[5/5] 初始化 AI 模板...")
    from app.init_ai_data import init_ai_templates as _init
    with app.app_context():
        _init()


def main():
    """执行全部初始化。"""
    print("=" * 50)
    print("ATP 测试平台 - 一键初始化")
    print("=" * 50)
    print()

    # 1. 确保数据库存在（在创建 Flask app 之前）
    ensure_database()

    # 2. 创建 Flask app（会加载所有模型）
    from app.flask_app import create_app
    app = create_app()

    # 3-5. 表结构、用户权限、AI模板
    create_tables(app)
    auto_migrate(app)
    init_users(app)
    init_ai_templates(app)

    print()
    print("=" * 50)
    print("初始化完成！")
    print("=" * 50)
    print()
    print("默认账号:")
    print("  admin / admin123")
    print("  test  / test123")
    print()
    print("启动项目:")
    print("  后端: python run.py")
    print("  前端: cd client && npm install && npm run dev")


if __name__ == "__main__":
    main()
