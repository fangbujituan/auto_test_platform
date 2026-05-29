"""
测试权限修复后的 API 访问。

作者: yandc
创建时间: 2026-01-19
"""
import requests
import json

BASE_URL = "http://127.0.0.1:12048"


def test_with_user(username, password, project_id=5):
    """使用指定用户测试 API。"""
    print(f"\n{'='*60}")
    print(f"测试用户: {username}")
    print(f"{'='*60}")
    
    # 1. 登录
    print("\n1. 登录...")
    login_data = {
        "username": username,
        "password": password
    }
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"❌ 登录失败: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    data = result.get("data", {})
    token = data.get("token")
    if not token:
        print(f"❌ 登录响应中没有 token: {result}")
        return
    print(f"✅ 登录成功，token: {token[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Username": username
    }
    
    # 2. 测试模块树 API
    print(f"\n2. 获取项目 {project_id} 的模块树...")
    response = requests.get(
        f"{BASE_URL}/api/modules/tree",
        params={"project_id": project_id},
        headers=headers
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        modules = response.json()
        print(f"✅ 成功获取模块树，共 {len(modules)} 个顶层模块")
        for module in modules:
            print(f"  - {module['name']} (ID: {module['id']})")
    else:
        print(f"❌ 获取模块树失败")
        print(response.text)
    
    # 3. 测试测试用例列表 API
    print(f"\n3. 获取项目 {project_id} 的测试用例列表...")
    response = requests.get(
        f"{BASE_URL}/api/test-cases",
        params={"project_id": project_id, "page": 1, "per_page": 20},
        headers=headers
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 成功获取测试用例列表")
        print(f"  总数: {result['total']}")
        print(f"  当前页: {result['page']}/{result['pages']}")
        print(f"  本页数量: {len(result['items'])}")
        
        if result['items']:
            print("\n  前3个测试用例:")
            for case in result['items'][:3]:
                print(f"    - {case['case_no']}: {case['title']}")
    else:
        print(f"❌ 获取测试用例列表失败")
        print(response.text)


def main():
    """主函数。"""
    print("测试权限修复后的 API 访问")
    print("="*60)
    
    # 测试不同角色的用户
    test_users = [
        ("admin", "admin123"),  # 管理员
        ("test", "test123"),  # 普通用户
    ]
    
    for username, password in test_users:
        try:
            test_with_user(username, password)
        except Exception as e:
            print(f"\n❌ 测试用户 {username} 时出错: {e}")
    
    print("\n" + "="*60)
    print("测试完成")


if __name__ == "__main__":
    main()
