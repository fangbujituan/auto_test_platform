"""
初始化Bug管理模块数据。

作者: yandc
创建时间: 2026-01-22
"""
import sys
from datetime import datetime
from app.flask_app import create_app
from app.models.base import db
from app.models.bug import Bug
from app.models.project import Project
from app.models.user import User


def init_bug_data():
    """初始化Bug管理数据。"""
    app = create_app()
    
    with app.app_context():
        print("开始初始化Bug管理模块...")
        
        # 创建bugs表
        print("创建bugs表...")
        db.create_all()
        print("✓ bugs表创建成功")
        
        # 检查是否已有数据
        existing_bugs = Bug.query.count()
        if existing_bugs > 0:
            print(f"已存在 {existing_bugs} 条Bug记录，跳过示例数据创建")
            return
        
        # 获取第一个项目和用户
        project = Project.query.first()
        user = User.query.first()
        
        if not project or not user:
            print("警告: 未找到项目或用户，无法创建示例Bug数据")
            print("请先运行 init_db.py 初始化基础数据")
            return
        
        print(f"使用项目: {project.name} (ID: {project.id})")
        print(f"使用用户: {user.username} (ID: {user.id})")
        
        # 创建示例Bug数据
        sample_bugs = [
            {
                "title": "登录页面无法正常显示",
                "description": "在Chrome浏览器中打开登录页面时，页面布局错乱，无法正常显示登录表单",
                "project_id": project.id,
                "status": "open",
                "priority": "high",
                "severity": "major",
                "category": "UI",
                "module": "用户认证",
                "tags": ["前端", "登录"],
                "reporter_id": user.id,
                "assignee_id": user.id,
                "environment": "Chrome 120, Windows 11",
                "version": "v1.0.0",
                "steps_to_reproduce": "1. 打开浏览器\n2. 访问登录页面\n3. 观察页面显示",
                "expected_result": "登录页面正常显示，表单元素对齐",
                "actual_result": "页面布局错乱，按钮位置不正确",
            },
            {
                "title": "API接口返回500错误",
                "description": "调用用户信息接口时偶尔返回500内部服务器错误",
                "project_id": project.id,
                "status": "in_progress",
                "priority": "critical",
                "severity": "critical",
                "category": "后端",
                "module": "API接口",
                "tags": ["后端", "API", "性能"],
                "reporter_id": user.id,
                "assignee_id": user.id,
                "environment": "生产环境",
                "version": "v1.0.1",
                "steps_to_reproduce": "1. 发送GET请求到 /api/user/info\n2. 高并发情况下重复请求\n3. 观察响应",
                "expected_result": "返回200状态码和用户信息",
                "actual_result": "偶尔返回500错误，错误信息: Database connection timeout",
                "related_apis": [1],
            },
            {
                "title": "测试用例执行结果不准确",
                "description": "自动化测试用例执行后，结果统计数据与实际不符",
                "project_id": project.id,
                "status": "resolved",
                "priority": "medium",
                "severity": "normal",
                "category": "测试",
                "module": "测试执行",
                "tags": ["测试", "自动化"],
                "reporter_id": user.id,
                "assignee_id": user.id,
                "environment": "测试环境",
                "version": "v1.0.0",
                "steps_to_reproduce": "1. 创建测试用例\n2. 执行测试\n3. 查看结果统计",
                "expected_result": "统计数据准确反映测试结果",
                "actual_result": "成功数量计算错误",
                "resolution": "fixed",
                "resolution_note": "修复了结果统计逻辑中的计数错误",
                "resolved_at": datetime.now(),
                "resolved_by": user.id,
                "related_test_cases": [1],
            },
            {
                "title": "项目成员权限设置无效",
                "description": "为项目成员设置只读权限后，该成员仍然可以编辑项目内容",
                "project_id": project.id,
                "status": "open",
                "priority": "high",
                "severity": "major",
                "category": "权限",
                "module": "项目管理",
                "tags": ["权限", "安全"],
                "reporter_id": user.id,
                "environment": "所有环境",
                "version": "v1.0.0",
                "steps_to_reproduce": "1. 添加项目成员\n2. 设置为只读权限\n3. 使用该成员账号尝试编辑",
                "expected_result": "只读成员无法编辑项目内容",
                "actual_result": "只读成员可以正常编辑",
            },
            {
                "title": "导出功能在大数据量时超时",
                "description": "当导出超过1000条数据时，请求超时",
                "project_id": project.id,
                "status": "open",
                "priority": "low",
                "severity": "minor",
                "category": "功能",
                "module": "数据导出",
                "tags": ["性能", "导出"],
                "reporter_id": user.id,
                "environment": "生产环境",
                "version": "v1.0.1",
                "steps_to_reproduce": "1. 选择大量数据\n2. 点击导出按钮\n3. 等待响应",
                "expected_result": "成功导出所有数据",
                "actual_result": "请求超时，无法完成导出",
            },
        ]
        
        print(f"\n创建 {len(sample_bugs)} 条示例Bug记录...")
        for bug_data in sample_bugs:
            bug = Bug(**bug_data)
            db.session.add(bug)
            print(f"  - {bug_data['title']} [{bug_data['status']}]")
        
        db.session.commit()
        print(f"\n✓ 成功创建 {len(sample_bugs)} 条Bug记录")
        
        # 显示统计信息
        print("\n=== Bug统计信息 ===")
        print(f"总计: {Bug.query.count()} 条")
        print(f"待处理: {Bug.query.filter_by(status='open').count()} 条")
        print(f"处理中: {Bug.query.filter_by(status='in_progress').count()} 条")
        print(f"已解决: {Bug.query.filter_by(status='resolved').count()} 条")
        print(f"高优先级: {Bug.query.filter_by(priority='high').count()} 条")
        print(f"严重级别: {Bug.query.filter_by(priority='critical').count()} 条")
        
        print("\n✓ Bug管理模块初始化完成！")
        print("\n可用的API端点:")
        print(f"  GET    /api/projects/{project.id}/bugs - 获取Bug列表")
        print(f"  POST   /api/projects/{project.id}/bugs - 创建Bug")
        print(f"  GET    /api/projects/{project.id}/bugs/<bug_id> - 获取Bug详情")
        print(f"  PUT    /api/projects/{project.id}/bugs/<bug_id> - 更新Bug")
        print(f"  DELETE /api/projects/{project.id}/bugs/<bug_id> - 删除Bug")
        print(f"  POST   /api/projects/{project.id}/bugs/<bug_id>/resolve - 解决Bug")
        print(f"  POST   /api/projects/{project.id}/bugs/<bug_id>/reopen - 重新打开Bug")
        print(f"  GET    /api/projects/{project.id}/bugs/statistics - 获取统计信息")


if __name__ == "__main__":
    try:
        init_bug_data()
    except Exception as e:
        print(f"\n✗ 初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
