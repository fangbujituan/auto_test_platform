"""
使用默认数据初始化数据库。

作者: yandc
创建时间: 2026-01-14
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.user import User
from app.init_ai_data import init_ai_templates

app = create_app()

with app.app_context():
    # 检查是否已有用户
    if User.query.count() > 0:
        print("用户已存在，无需初始化")
    else:
        # 创建默认用户
        admin = User(username="admin", email="admin@example.com")
        admin.set_password("admin123")
        
        test_user = User(username="test", email="test@example.com")
        test_user.set_password("test123")
        
        db.session.add(admin)
        db.session.add(test_user)
        db.session.commit()
        
        print("初始化成功！")
        print("测试账号：")
        print("  - admin / admin123")
        print("  - test / test123")

    # 初始化 AI 内置提示词模板
    print("\n初始化 AI 内置提示词模板...")
    init_ai_templates()
