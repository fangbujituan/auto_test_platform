"""
修改测试用例表，使 module_id 和 folder_id 字段可选

作者: yandc
创建时间: 2026-01-22
"""
from app.flask_app import create_app
from app.models.base import db
from sqlalchemy import text

def migrate():
    """执行迁移"""
    app = create_app()
    with app.app_context():
        try:
            print("开始迁移测试用例表...")
            
            # 修改 module_id 字段为可空
            print("1. 修改 module_id 字段为可空...")
            db.session.execute(text("""
                ALTER TABLE test_case_management 
                MODIFY COLUMN module_id INT NULL COMMENT '所属模块ID（可选）'
            """))
            
            # 确保 folder_id 字段为可空（如果已存在）
            print("2. 确保 folder_id 字段为可空...")
            db.session.execute(text("""
                ALTER TABLE test_case_management 
                MODIFY COLUMN folder_id INT NULL COMMENT '所属目录ID（可选）'
            """))
            
            db.session.commit()
            print("✅ 迁移成功完成！")
            
            # 验证修改
            print("\n验证表结构...")
            result = db.session.execute(text("""
                SHOW COLUMNS FROM test_case_management 
                WHERE Field IN ('module_id', 'folder_id')
            """))
            
            print("\n当前字段信息:")
            for row in result:
                print(f"  - {row[0]}: {row[1]}, Null={row[2]}, Default={row[4]}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 迁移失败: {str(e)}")
            raise

if __name__ == "__main__":
    migrate()
