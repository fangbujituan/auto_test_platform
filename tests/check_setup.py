# -*- coding: utf-8 -*-
"""
检查测试用例管理模块配置是否正确

作者: yandc
创建时间: 2026-01-19
"""
import os
import sys

def check_file_exists(filepath, description):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description}不存在: {filepath}")
        return False

def check_backend():
    """检查后端文件"""
    print("\n" + "="*60)
    print("检查后端文件")
    print("="*60)
    
    files = [
        ("app/models/module.py", "模块模型"),
        ("app/models/test_case.py", "测试用例模型"),
        ("app/api/module.py", "模块API"),
        ("app/api/test_case.py", "测试用例API"),
        ("migrate_add_test_case_module.py", "数据库迁移脚本"),
        ("init_test_case_permissions.py", "权限初始化脚本"),
    ]
    
    all_ok = True
    for filepath, desc in files:
        if not check_file_exists(filepath, desc):
            all_ok = False
    
    return all_ok

def check_frontend():
    """检查前端文件"""
    print("\n" + "="*60)
    print("检查前端文件")
    print("="*60)
    
    files = [
        ("client/src/views/TestCaseManagement.vue", "测试用例管理页面"),
        ("client/src/api/module.js", "模块API封装"),
        ("client/src/api/testCase.js", "测试用例API封装"),
        ("client/src/router/index.js", "路由配置"),
    ]
    
    all_ok = True
    for filepath, desc in files:
        if not check_file_exists(filepath, desc):
            all_ok = False
    
    return all_ok

def check_router_config():
    """检查路由配置"""
    print("\n" + "="*60)
    print("检查路由配置")
    print("="*60)
    
    router_file = "client/src/router/index.js"
    if not os.path.exists(router_file):
        print(f"✗ 路由文件不存在: {router_file}")
        return False
    
    with open(router_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    checks = [
        ("TestCaseManagement", "TestCaseManagement组件导入"),
        ("test-cases", "测试用例路由路径"),
        ("TestCaseManagement", "TestCaseManagement组件使用"),
    ]
    
    all_ok = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"✓ {desc}已配置")
        else:
            print(f"✗ {desc}未配置")
            all_ok = False
    
    return all_ok

def check_project_detail():
    """检查ProjectDetail页面配置"""
    print("\n" + "="*60)
    print("检查ProjectDetail页面")
    print("="*60)
    
    detail_file = "client/src/views/ProjectDetail.vue"
    if not os.path.exists(detail_file):
        print(f"✗ ProjectDetail文件不存在: {detail_file}")
        return False
    
    with open(detail_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查测试用例菜单项
    if 'index="case"' in content and 'disabled' not in content.split('index="case"')[1].split('>')[0]:
        print("✓ 测试用例菜单项已启用")
    else:
        print("✗ 测试用例菜单项未启用或配置错误")
        return False
    
    # 检查handleModuleChange函数
    if "index === 'case'" in content or 'index === "case"' in content:
        print("✓ 测试用例跳转逻辑已配置")
    else:
        print("✗ 测试用例跳转逻辑未配置")
        return False
    
    return True

def check_database():
    """检查数据库表"""
    print("\n" + "="*60)
    print("检查数据库表")
    print("="*60)
    
    try:
        from app.flask_app import create_app
        from app.models.base import db
        from app.models.module import Module
        from app.models.test_case import TestCaseManagement, TestCaseApiBinding
        
        app = create_app()
        with app.app_context():
            # 检查表是否存在
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            required_tables = ['modules', 'test_case_management', 'test_case_api_bindings']
            all_ok = True
            
            for table in required_tables:
                if table in tables:
                    print(f"✓ 数据表存在: {table}")
                else:
                    print(f"✗ 数据表不存在: {table}")
                    all_ok = False
            
            return all_ok
    except Exception as e:
        print(f"✗ 检查数据库时出错: {str(e)}")
        print("  提示：请先运行数据库迁移脚本")
        return False

def check_permissions():
    """检查权限配置"""
    print("\n" + "="*60)
    print("检查权限配置")
    print("="*60)
    
    try:
        from app.flask_app import create_app
        from app.models.role import Permission
        
        app = create_app()
        with app.app_context():
            required_permissions = [
                ('module', 'create'),
                ('module', 'read'),
                ('module', 'update'),
                ('module', 'delete'),
                ('test_case', 'create'),
                ('test_case', 'read'),
                ('test_case', 'update'),
                ('test_case', 'delete'),
            ]
            
            all_ok = True
            for resource, action in required_permissions:
                perm = Permission.query.filter_by(resource=resource, action=action).first()
                if perm:
                    print(f"✓ 权限存在: {resource}:{action}")
                else:
                    print(f"✗ 权限不存在: {resource}:{action}")
                    all_ok = False
            
            return all_ok
    except Exception as e:
        print(f"✗ 检查权限时出错: {str(e)}")
        print("  提示：请先运行权限初始化脚本")
        return False

def main():
    """主函数"""
    print("\n" + "="*60)
    print("测试用例管理模块配置检查")
    print("="*60)
    
    results = {
        "后端文件": check_backend(),
        "前端文件": check_frontend(),
        "路由配置": check_router_config(),
        "ProjectDetail配置": check_project_detail(),
        "数据库表": check_database(),
        "权限配置": check_permissions(),
    }
    
    print("\n" + "="*60)
    print("检查结果汇总")
    print("="*60)
    
    all_passed = True
    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有检查通过！可以正常使用测试用例管理模块")
        print("\n访问路径：")
        print("1. 登录系统: http://localhost:5173")
        print("2. 进入项目列表")
        print("3. 选择项目进入详情页")
        print("4. 点击左侧菜单的'测试用例'")
    else:
        print("✗ 部分检查未通过，请根据上述提示进行修复")
        print("\n建议操作：")
        if not results["数据库表"]:
            print("- 运行数据库迁移: python migrate_add_test_case_module.py")
        if not results["权限配置"]:
            print("- 运行权限初始化: python init_test_case_permissions.py")
        if not results["前端文件"] or not results["路由配置"]:
            print("- 检查前端文件是否完整")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
