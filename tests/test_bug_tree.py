"""测试Bug树接口"""
import sys
from app.flask_app import create_app
from app.models.base import db
from app.models.bug import Bug
from app.models.api_folder import ApiFolder

app = create_app()

with app.app_context():
    project_id = 5
    
    print("=== 检查项目5的数据 ===")
    
    # 检查目录
    folders = ApiFolder.query.filter_by(project_id=project_id).all()
    print(f"\n目录数量: {len(folders)}")
    for folder in folders:
        print(f"  - {folder.id}: {folder.name} (parent_id={folder.parent_id})")
    
    # 检查Bug
    bugs = Bug.query.filter_by(project_id=project_id).all()
    print(f"\nBug数量: {len(bugs)}")
    for bug in bugs:
        print(f"  - {bug.id}: {bug.title}")
        print(f"    folder_id={bug.folder_id}")
        print(f"    created_at={bug.created_at}")
        print(f"    updated_at={bug.updated_at}")
        
        # 检查是否有None值
        if bug.created_at is None:
            print(f"    ⚠️ created_at is None!")
        if bug.updated_at is None:
            print(f"    ⚠️ updated_at is None!")
    
    # 测试树构建
    print("\n=== 测试树构建 ===")
    try:
        root_folders = ApiFolder.query.filter_by(
            project_id=project_id,
            parent_id=None
        ).order_by(ApiFolder.sort_order, ApiFolder.created_at).all()
        
        print(f"根目录数量: {len(root_folders)}")
        
        for folder in root_folders:
            print(f"\n处理目录: {folder.name}")
            
            # 获取该目录下的Bug
            folder_bugs = Bug.query.filter_by(
                project_id=project_id,
                folder_id=folder.id
            ).order_by(Bug.created_at.desc()).all()
            
            print(f"  该目录下的Bug数量: {len(folder_bugs)}")
            
            for bug in folder_bugs:
                try:
                    created_at_str = bug.created_at.strftime("%Y-%m-%d %H:%M:%S") if bug.created_at else "None"
                    updated_at_str = bug.updated_at.strftime("%Y-%m-%d %H:%M:%S") if bug.updated_at else "None"
                    print(f"    - {bug.title}: created={created_at_str}, updated={updated_at_str}")
                except Exception as e:
                    print(f"    - {bug.title}: ❌ 格式化时间失败: {e}")
        
        # 检查未分类的Bug
        uncategorized_bugs = Bug.query.filter_by(
            project_id=project_id,
            folder_id=None
        ).order_by(Bug.created_at.desc()).all()
        
        print(f"\n未分类Bug数量: {len(uncategorized_bugs)}")
        for bug in uncategorized_bugs:
            try:
                created_at_str = bug.created_at.strftime("%Y-%m-%d %H:%M:%S") if bug.created_at else "None"
                updated_at_str = bug.updated_at.strftime("%Y-%m-%d %H:%M:%S") if bug.updated_at else "None"
                print(f"  - {bug.title}: created={created_at_str}, updated={updated_at_str}")
            except Exception as e:
                print(f"  - {bug.title}: ❌ 格式化时间失败: {e}")
        
        print("\n✅ 树构建测试成功")
        
    except Exception as e:
        print(f"\n❌ 树构建失败: {e}")
        import traceback
        traceback.print_exc()
