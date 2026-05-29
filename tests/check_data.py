"""检查数据库中的目录和接口数据"""

from app.flask_app import create_app
from app.models.project import Project
from app.models.api_folder import ApiFolder
from app.models.api import Api

def check_data():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("数据库数据检查")
        print("=" * 60)
        
        projects = Project.query.all()
        print(f"\n总共有 {len(projects)} 个项目：")
        
        for project in projects:
            print(f"\n项目: {project.name} (ID: {project.id})")
            
            # 检查目录
            folders = ApiFolder.query.filter_by(project_id=project.id).all()
            print(f"  目录数量: {len(folders)}")
            for folder in folders:
                print(f"    - {folder.name} (ID: {folder.id})")
            
            # 检查接口
            apis = Api.query.filter_by(project_id=project.id).all()
            print(f"  接口数量: {len(apis)}")
            for api in apis:
                folder_name = "未分类"
                if api.folder_id:
                    folder = ApiFolder.query.get(api.folder_id)
                    if folder:
                        folder_name = folder.name
                print(f"    - {api.method} {api.name} -> {folder_name}")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    check_data()
