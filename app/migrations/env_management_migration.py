"""
数据库迁移脚本 - 环境管理功能。

新增表: environments, prefix_urls, global_variables, global_params
修改表: environment_variables (新增 environment_id 列)
修改表: apis (新增 module, service 列)

兼容性: environment_id 可为空，旧数据不受影响。

作者: yandc
创建时间: 2026-04-03
"""
from sqlalchemy import inspect, text
from app.flask_app import create_app
from app.models.base import db


def column_exists(inspector, table_name, column_name):
    """检查表中是否已存在指定列。"""
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(inspector, table_name):
    """检查表是否已存在。"""
    return table_name in inspector.get_table_names()


def run_migration():
    """执行数据库迁移。"""
    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)

        # 1. 创建所有新表（db.create_all 会跳过已存在的表）
        db.create_all()
        print("[OK] 新表已创建（environments, prefix_urls, global_variables, global_params）")

        # 2. 为 environment_variables 表添加 environment_id 列（如果不存在）
        if table_exists(inspector, "environment_variables"):
            if not column_exists(inspector, "environment_variables", "environment_id"):
                db.session.execute(text(
                    "ALTER TABLE environment_variables "
                    "ADD COLUMN environment_id INTEGER NULL "
                    "REFERENCES environments(id)"
                ))
                db.session.commit()
                print("[OK] environment_variables 表已添加 environment_id 列")
            else:
                print("[SKIP] environment_variables.environment_id 列已存在")

        # 3. 为 apis 表添加 module 和 service 列（如果不存在）
        if table_exists(inspector, "apis"):
            if not column_exists(inspector, "apis", "module"):
                db.session.execute(text(
                    "ALTER TABLE apis ADD COLUMN module VARCHAR(200) NULL"
                ))
                db.session.commit()
                print("[OK] apis 表已添加 module 列")
            else:
                print("[SKIP] apis.module 列已存在")

            if not column_exists(inspector, "apis", "service"):
                db.session.execute(text(
                    "ALTER TABLE apis ADD COLUMN service VARCHAR(200) NULL"
                ))
                db.session.commit()
                print("[OK] apis 表已添加 service 列")
            else:
                print("[SKIP] apis.service 列已存在")

        print("\n迁移完成！")


if __name__ == "__main__":
    run_migration()
