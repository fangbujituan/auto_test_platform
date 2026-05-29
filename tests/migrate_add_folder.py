"""
数据库迁移：为 apis 表添加 folder_id 字段，创建 api_folders 表。

使用方法:
    python migrate_add_folder.py

作者: yandc
创建时间: 2026-01-16
"""
from sqlalchemy import text
from app.flask_app import create_app
from app.models.base import db

def migrate():
    """执行数据库迁移。"""
    app = create_app()
    
    with app.app_context():
        print("开始数据库迁移...")
        
        try:
            # 检查 api_folders 表是否存在
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'api_folders'"
            ))
            table_exists = result.scalar() > 0
            
            if not table_exists:
                print("创建 api_folders 表...")
                db.session.execute(text("""
                    CREATE TABLE api_folders (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(200) NOT NULL COMMENT '目录名称',
                        description TEXT COMMENT '目录描述',
                        project_id INT NOT NULL COMMENT '项目ID',
                        parent_id INT COMMENT '父目录ID',
                        sort_order INT DEFAULT 0 COMMENT '排序',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                        FOREIGN KEY (parent_id) REFERENCES api_folders(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API目录表'
                """))
                print("✓ api_folders 表创建成功")
            else:
                print("✓ api_folders 表已存在")
            
            # 检查 apis 表是否有 folder_id 字段
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'apis' "
                "AND column_name = 'folder_id'"
            ))
            column_exists = result.scalar() > 0
            
            if not column_exists:
                print("为 apis 表添加 folder_id 字段...")
                db.session.execute(text("""
                    ALTER TABLE apis 
                    ADD COLUMN folder_id INT COMMENT '所属目录ID' AFTER project_id,
                    ADD FOREIGN KEY (folder_id) REFERENCES api_folders(id) ON DELETE SET NULL
                """))
                print("✓ folder_id 字段添加成功")
            else:
                print("✓ folder_id 字段已存在")
            
            db.session.commit()
            print("\n数据库迁移完成！")
            print("\n下一步：运行 'python init_folders.py' 初始化目录数据")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ 迁移失败: {str(e)}")
            raise

if __name__ == "__main__":
    migrate()
