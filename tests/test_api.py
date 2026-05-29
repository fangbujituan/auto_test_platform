"""测试 API 接口"""
import requests

# 首先登录获取 token
def login():
    url = "http://localhost:12048/api/auth/login"
    data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"登录状态码: {response.status_code}")
        result = response.json()
        print(f"登录响应: {result}")
        return result.get('data', {}).get('token'), result.get('data', {}).get('username')
    except Exception as e:
        print(f"登录错误: {e}")
        return None, None

# 测试获取目录树
def test_folder_tree(token, username):
    url = "http://localhost:12048/api/projects/4/folders/tree"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Username": username
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"\n目录树状态码: {response.status_code}")
        print(f"目录树响应: {response.json()}")
    except Exception as e:
        print(f"目录树错误: {e}")

if __name__ == "__main__":
    token, username = login()
    if token:
        test_folder_tree(token, username)
