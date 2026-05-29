# -*- coding: utf-8 -*-
"""
测试用例管理模块演示脚本。

作者: yandc
创建时间: 2026-01-19
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.project import Project
from app.models.module import Module
from app.models.test_case import TestCaseManagement, TestCaseApiBinding
from app.models.api import Api


def demo():
    """演示测试用例管理功能。"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("测试用例管理模块演示")
        print("=" * 60)
        
        # 1. 查找或创建测试项目
        project = Project.query.first()
        if not project:
            project = Project(name="演示项目", description="用于演示测试用例管理")
            db.session.add(project)
            db.session.commit()
            print(f"\n✓ 创建项目: {project.name} (ID: {project.id})")
        else:
            print(f"\n✓ 使用现有项目: {project.name} (ID: {project.id})")
        
        # 2. 创建模块结构
        print("\n" + "-" * 60)
        print("创建模块结构")
        print("-" * 60)
        
        # 创建顶层模块
        user_module = Module(
            module_no="MOD-USER",
            name="用户模块",
            description="用户相关功能模块",
            project_id=project.id
        )
        db.session.add(user_module)
        db.session.flush()
        print(f"✓ 创建顶层模块: {user_module.name} ({user_module.module_no})")
        
        # 创建子模块
        login_module = Module(
            module_no="MOD-USER-LOGIN",
            name="登录子模块",
            description="用户登录功能",
            project_id=project.id,
            parent_id=user_module.id
        )
        db.session.add(login_module)
        print(f"  ✓ 创建子模块: {login_module.name} ({login_module.module_no})")
        
        register_module = Module(
            module_no="MOD-USER-REG",
            name="注册子模块",
            description="用户注册功能",
            project_id=project.id,
            parent_id=user_module.id
        )
        db.session.add(register_module)
        print(f"  ✓ 创建子模块: {register_module.name} ({register_module.module_no})")
        
        db.session.commit()
        
        # 3. 创建测试用例
        print("\n" + "-" * 60)
        print("创建测试用例")
        print("-" * 60)
        
        test_cases = [
            {
                "title": "正常登录测试",
                "description": "测试用户使用正确的用户名和密码登录",
                "precondition": "用户已注册",
                "steps": "1. 打开登录页面\n2. 输入正确的用户名和密码\n3. 点击登录按钮",
                "expected_result": "登录成功，跳转到首页",
                "module_id": login_module.id,
                "priority": "P0",
                "case_type": "功能",
                "case_status": "已评审"
            },
            {
                "title": "错误密码登录测试",
                "description": "测试用户使用错误密码登录",
                "precondition": "用户已注册",
                "steps": "1. 打开登录页面\n2. 输入正确的用户名和错误的密码\n3. 点击登录按钮",
                "expected_result": "提示密码错误",
                "module_id": login_module.id,
                "priority": "P1",
                "case_type": "功能",
                "case_status": "已评审"
            },
            {
                "title": "未注册用户登录测试",
                "description": "测试未注册用户尝试登录",
                "precondition": "用户未注册",
                "steps": "1. 打开登录页面\n2. 输入未注册的用户名\n3. 点击登录按钮",
                "expected_result": "提示用户不存在",
                "module_id": login_module.id,
                "priority": "P1",
                "case_type": "功能",
                "case_status": "草稿"
            }
        ]
        
        for idx, case_data in enumerate(test_cases, 1):
            case_no = f"TC-{project.id}-{idx:04d}"
            test_case = TestCaseManagement(
                case_no=case_no,
                project_id=project.id,
                **case_data
            )
            db.session.add(test_case)
            db.session.flush()
            print(f"✓ 创建测试用例: {test_case.case_no} - {test_case.title}")
        
        db.session.commit()
        
        # 4. 统计信息
        print("\n" + "-" * 60)
        print("统计信息")
        print("-" * 60)
        
        total_modules = Module.query.filter_by(project_id=project.id).count()
        total_cases = TestCaseManagement.query.filter_by(project_id=project.id).count()
        
        print(f"项目: {project.name}")
        print(f"  - 模块数量: {total_modules}")
        print(f"  - 测试用例数量: {total_cases}")
        
        # 按模块统计
        print(f"\n按模块统计:")
        for module in Module.query.filter_by(project_id=project.id).all():
            case_count = TestCaseManagement.query.filter_by(module_id=module.id).count()
            indent = "  " if module.parent_id else ""
            print(f"{indent}- {module.name}: {case_count} 个用例")
        
        # 按优先级统计
        print(f"\n按优先级统计:")
        for priority in ["P0", "P1", "P2", "P3"]:
            count = TestCaseManagement.query.filter_by(
                project_id=project.id,
                priority=priority
            ).count()
            if count > 0:
                print(f"  - {priority}: {count} 个用例")
        
        # 按状态统计
        print(f"\n按状态统计:")
        for status in ["草稿", "已评审", "已废弃"]:
            count = TestCaseManagement.query.filter_by(
                project_id=project.id,
                case_status=status
            ).count()
            if count > 0:
                print(f"  - {status}: {count} 个用例")
        
        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)


if __name__ == "__main__":
    demo()
