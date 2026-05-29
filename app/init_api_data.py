"""
初始化API目录数据。

为现有项目创建默认目录，并将现有接口分配到目录中。

作者: yandc
创建时间: 2026-01-16
"""
from app.flask_app import create_app
from app.models.base import db
from app.models.project import Project
from app.models.api import Api
from app.models.api_folder import ApiFolder


def init_api_folders():
    """为所有项目初始化默认目录结构。"""
    app = create_app()
    
    with app.app_context():
        print("开始初始化API目录数据...")
        
        # 获取所有项目
        projects = Project.query.all()
        print(f"找到 {len(projects)} 个项目")
        
        for project in projects:
            print(f"\n处理项目: {project.name} (ID: {project.id})")
            
            # 检查是否已有目录
            existing_folders = ApiFolder.query.filter_by(project_id=project.id).count()
            if existing_folders > 0:
                print(f"  项目已有 {existing_folders} 个目录，跳过")
                continue
            
            # 创建默认目录
            default_folders = [
                {"name": "用户模块", "description": "用户相关接口", "sort_order": 1},
                {"name": "系统模块", "description": "系统相关接口", "sort_order": 2},
                {"name": "业务模块", "description": "业务相关接口", "sort_order": 3},
            ]
            
            created_folders = {}
            for folder_data in default_folders:
                folder = ApiFolder(
                    name=folder_data["name"],
                    description=folder_data["description"],
                    project_id=project.id,
                    parent_id=None,
                    sort_order=folder_data["sort_order"]
                )
                db.session.add(folder)
                db.session.flush()  # 获取ID
                created_folders[folder_data["name"]] = folder
                print(f"  创建目录: {folder.name}")
            
            # 获取该项目的所有接口
            apis = Api.query.filter_by(project_id=project.id).all()
            print(f"  找到 {len(apis)} 个接口")
            
            # 根据接口的category或名称智能分配到目录
            for api in apis:
                folder = None
                
                # 根据分类分配
                if api.category:
                    category_lower = api.category.lower()
                    if '用户' in category_lower or 'user' in category_lower:
                        folder = created_folders.get("用户模块")
                    elif '系统' in category_lower or 'system' in category_lower:
                        folder = created_folders.get("系统模块")
                    else:
                        folder = created_folders.get("业务模块")
                
                # 根据接口名称或路径分配
                if not folder:
                    name_lower = api.name.lower()
                    path_lower = api.path.lower()
                    
                    if 'user' in name_lower or 'user' in path_lower or '用户' in api.name:
                        folder = created_folders.get("用户模块")
                    elif 'auth' in name_lower or 'login' in name_lower or 'register' in name_lower:
                        folder = created_folders.get("用户模块")
                    elif 'system' in name_lower or 'config' in name_lower or '系统' in api.name:
                        folder = created_folders.get("系统模块")
                    else:
                        folder = created_folders.get("业务模块")
                
                if folder:
                    api.folder_id = folder.id
                    print(f"  接口 '{api.name}' 分配到 '{folder.name}'")
            
            db.session.commit()
            print(f"  项目 {project.name} 初始化完成")
        
        print("\n所有项目初始化完成！")


def reset_api_folders():
    """重置所有API目录数据（谨慎使用）。"""
    app = create_app()
    
    with app.app_context():
        print("警告：这将删除所有API目录数据！")
        confirm = input("确定要继续吗？(yes/no): ")
        
        if confirm.lower() != 'yes':
            print("操作已取消")
            return
        
        print("开始重置API目录数据...")
        
        # 清空所有接口的folder_id
        Api.query.update({Api.folder_id: None})
        
        # 删除所有目录
        deleted_count = ApiFolder.query.delete()
        
        db.session.commit()
        
        print(f"已删除 {deleted_count} 个目录")
        print("重置完成！")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset_api_folders()
    else:
        init_api_folders()
