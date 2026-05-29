"""
添加测试用例管理模块的数据库迁移脚本。

作者: yandc
创建时间: 2026-01-19
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.module import Module
from app.models.test_case import TestCaseManagement, TestCaseApiBinding

def migrate():
    """执行迁移。"""
    app = create_app()
    
    with app.app_context():
        print("开始创建测试用例管理相关表...")
        
        # 创建表
        db.create_all()
        
        print("✓ 模块表 (modules) 创建成功")
        print("✓ 测试用例管理表 (test_case_management) 创建成功")
        print("✓ 用例-API绑定表 (test_case_api_bindings) 创建成功")
        print("\n迁移完成！")


if __name__ == "__main__":
    migrate()
