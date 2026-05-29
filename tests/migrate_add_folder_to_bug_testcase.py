"""
为Bug和TestCase添加folder_id字段的数据库迁移脚本。

作者: yandc
创建时间: 2026-01-22
"""
from sqlalchemy import text
from app.flask_app import create_app
from app.models.base import db

app = create_app()

with app.app_context():
    try:
        # 为bugs表添加folder_id字段
        db.session.execute(text("""
            ALTER TABLE bugs
            ADD COLUMN folder_id INTEGER,
            ADD FOREIGN KEY (folder_id) REFERENCES api_folders(id)
        """))
        print("✓ bugs表添加folder_id字段成功")
    except Exception as e:
        print(f"✗ bugs表添加folder_id字段失败: {e}")
        db.session.rollback()

    try:
        # 为test_case_management表添加folder_id字段
        db.session.execute(text("""
            ALTER TABLE test_case_management
            ADD COLUMN folder_id INTEGER,
            ADD FOREIGN KEY (folder_id) REFERENCES api_folders(id)
        """))
        print("✓ test_case_management表添加folder_id字段成功")
    except Exception as e:
        print(f"✗ test_case_management表添加folder_id字段失败: {e}")
        db.session.rollback()

    try:
        db.session.commit()
        print("\n✓ 数据库迁移完成！")
    except Exception as e:
        print(f"\n✗ 数据库迁移失败: {e}")
        db.session.rollback()
