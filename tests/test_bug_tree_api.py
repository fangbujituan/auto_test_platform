"""测试Bug树API接口"""
import requests

# 测试接口
url = "http://localhost:12048/api/projects/5/bugs/tree"

# 需要登录token，从浏览器获取
# 你需要先登录，然后从浏览器的开发者工具中获取token
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
except Exception as e:
    print(f"请求失败: {e}")
