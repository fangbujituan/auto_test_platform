"""
测试接口保存功能修复

验证 headers、params、body 字段是否正确保存和读取
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.base import db
from app.models.api import Api
from app.models.project import Project
from app.models.user import User
import json

def test_api_save():
    """测试接口保存功能"""
    app = create_app()
    
    with app.app_context():
        # 获取测试项目
        project = Project.query.first()
        if not project:
            print("❌ 没有找到测试项目")
            return
        
        print(f"✓ 使用项目: {project.name} (ID: {project.id})")
        
        # 获取第一个接口
        api = Api.query.filter_by(project_id=project.id).first()
        if not api:
            print("❌ 没有找到测试接口")
            return
        
        print(f"✓ 使用接口: {api.name} (ID: {api.id})")
        
        # 打印当前数据
        print("\n当前接口数据:")
        print(f"  headers: {json.dumps(api.headers, ensure_ascii=False)}")
        print(f"  params: {json.dumps(api.params, ensure_ascii=False)}")
        print(f"  body: {json.dumps(api.body, ensure_ascii=False)}")
        print(f"  body_type: {api.body_type}")
        
        # 更新数据
        test_headers = {"Content-Type": "application/json", "Authorization": "Bearer test-token"}
        test_params = {"page": 1, "size": 20, "keyword": "测试"}
        test_body = {"username": "testuser", "password": "123456", "remember": True}
        
        api.headers = test_headers
        api.params = test_params
        api.body = test_body
        api.body_type = "json"
        
        db.session.commit()
        print("\n✓ 数据已更新")
        
        # 重新查询验证
        api_reloaded = Api.query.get(api.id)
        
        print("\n重新查询后的数据:")
        print(f"  headers: {json.dumps(api_reloaded.headers, ensure_ascii=False)}")
        print(f"  params: {json.dumps(api_reloaded.params, ensure_ascii=False)}")
        print(f"  body: {json.dumps(api_reloaded.body, ensure_ascii=False)}")
        print(f"  body_type: {api_reloaded.body_type}")
        
        # 验证数据
        assert api_reloaded.headers == test_headers, "headers 不匹配"
        assert api_reloaded.params == test_params, "params 不匹配"
        assert api_reloaded.body == test_body, "body 不匹配"
        assert api_reloaded.body_type == "json", "body_type 不匹配"
        
        print("\n✓ 所有数据验证通过！")
        
        # 测试 to_dict 方法
        api_dict = api_reloaded.to_dict()
        print("\nto_dict() 返回的数据:")
        print(f"  headers: {json.dumps(api_dict['headers'], ensure_ascii=False)}")
        print(f"  params: {json.dumps(api_dict['params'], ensure_ascii=False)}")
        print(f"  body: {json.dumps(api_dict['body'], ensure_ascii=False)}")
        print(f"  body_type: {api_dict['body_type']}")
        
        assert api_dict['headers'] == test_headers, "to_dict headers 不匹配"
        assert api_dict['params'] == test_params, "to_dict params 不匹配"
        assert api_dict['body'] == test_body, "to_dict body 不匹配"
        
        print("\n✓ to_dict() 数据验证通过！")
        print("\n" + "="*50)
        print("✓ 所有测试通过！接口保存功能正常")
        print("="*50)

if __name__ == "__main__":
    test_api_save()
