"""
检查Bug数据。

作者: yandc
创建时间: 2026-01-22
"""
from app.flask_app import create_app
from app.models.bug import Bug
from app.models.project import Project
from app.models.user import User


def check_bug_data():
    """检查Bug数据。"""
    app = create_app()
    
    with app.app_context():
        print("=== Bug数据检查 ===\n")
        
        # 检查Bug总数
        total_bugs = Bug.query.count()
        print(f"Bug总数: {total_bugs}\n")
        
        if total_bugs == 0:
            print("没有Bug数据")
            return
        
        # 显示所有Bug
        print("所有Bug列表:")
        print("-" * 100)
        bugs = Bug.query.order_by(Bug.created_at.desc()).all()
        for bug in bugs:
            print(f"ID: {bug.id}")
            print(f"  标题: {bug.title}")
            print(f"  状态: {bug.status} | 优先级: {bug.priority} | 严重程度: {bug.severity}")
            print(f"  模块: {bug.module} | 分类: {bug.category}")
            print(f"  报告人ID: {bug.reporter_id} | 指派人ID: {bug.assignee_id}")
            if bug.resolved_at:
                print(f"  解决方案: {bug.resolution} | 解决时间: {bug.resolved_at}")
            print(f"  创建时间: {bug.created_at}")
            print("-" * 100)
        
        # 统计信息
        print("\n=== 统计信息 ===")
        
        # 按状态统计
        print("\n按状态:")
        for status in ['open', 'in_progress', 'resolved', 'closed', 'reopened']:
            count = Bug.query.filter_by(status=status).count()
            if count > 0:
                print(f"  {status}: {count}")
        
        # 按优先级统计
        print("\n按优先级:")
        for priority in ['low', 'medium', 'high', 'critical']:
            count = Bug.query.filter_by(priority=priority).count()
            if count > 0:
                print(f"  {priority}: {count}")
        
        # 按严重程度统计
        print("\n按严重程度:")
        for severity in ['trivial', 'minor', 'normal', 'major', 'critical']:
            count = Bug.query.filter_by(severity=severity).count()
            if count > 0:
                print(f"  {severity}: {count}")
        
        # 按项目统计
        print("\n按项目:")
        projects = Project.query.all()
        for project in projects:
            count = Bug.query.filter_by(project_id=project.id).count()
            if count > 0:
                print(f"  {project.name} (ID: {project.id}): {count}")
        
        # 检查关联数据
        print("\n=== 关联数据检查 ===")
        bugs_with_apis = Bug.query.filter(Bug.related_apis.isnot(None)).count()
        bugs_with_test_cases = Bug.query.filter(Bug.related_test_cases.isnot(None)).count()
        print(f"关联API的Bug: {bugs_with_apis}")
        print(f"关联测试用例的Bug: {bugs_with_test_cases}")
        
        # 显示一个完整的Bug详情
        if bugs:
            print("\n=== 示例Bug详情 ===")
            sample_bug = bugs[0]
            bug_dict = sample_bug.to_dict()
            import json
            print(json.dumps(bug_dict, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    check_bug_data()
