"""检查用户和项目的关联关系"""
from app.flask_app import create_app
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember

def check_user_projects():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("用户-项目关联检查")
        print("=" * 60)
        
        users = User.query.all()
        print(f"\n总共有 {len(users)} 个用户：")
        
        for user in users:
            print(f"\n用户: {user.username} (ID: {user.id})")
            
            memberships = ProjectMember.query.filter_by(user_id=user.id).all()
            print(f"  参与的项目数: {len(memberships)}")
            
            for membership in memberships:
                project = Project.query.get(membership.project_id)
                if project:
                    print(f"    - {project.name} (角色: {membership.role.name})")
        
        print("\n" + "=" * 60)
        print("所有项目：")
        print("=" * 60)
        
        projects = Project.query.all()
        for project in projects:
            print(f"\n项目: {project.name} (ID: {project.id})")
            members = ProjectMember.query.filter_by(project_id=project.id).all()
            print(f"  成员数: {len(members)}")
            for member in members:
                user = User.query.get(member.user_id)
                if user:
                    print(f"    - {user.username} (角色: {member.role.name})")

if __name__ == "__main__":
    check_user_projects()
