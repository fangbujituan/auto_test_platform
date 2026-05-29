"""
测试Bug管理API。

作者: yandc
创建时间: 2026-01-22
"""
import requests
import json

BASE_URL = "http://localhost:12048"
PROJECT_ID = 1

# 登录获取token
def login():
    """登录获取token。"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("token")
    return None


def test_bug_apis():
    """测试Bug管理API。"""
    print("=== 测试Bug管理API ===\n")
    
    # 登录
    print("1. 登录获取token...")
    token = login()
    if not token:
        print("✗ 登录失败")
        return
    print(f"✓ 登录成功，token: {token[:20]}...\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 获取Bug列表
    print("2. 获取Bug列表...")
    response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs", headers=headers)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bugs = response.json().get("data", [])
        print(f"✓ 获取成功，共 {len(bugs)} 条Bug")
        if bugs:
            print(f"  第一条: {bugs[0]['title']} [{bugs[0]['status']}]")
    print()
    
    # 创建新Bug
    print("3. 创建新Bug...")
    new_bug = {
        "title": "测试Bug - API自动创建",
        "description": "这是通过API测试脚本创建的Bug",
        "status": "open",
        "priority": "medium",
        "severity": "normal",
        "category": "测试",
        "module": "Bug管理",
        "tags": ["测试", "自动化"],
        "environment": "测试环境",
        "version": "v1.0.0",
        "steps_to_reproduce": "1. 运行测试脚本\n2. 观察结果",
        "expected_result": "Bug创建成功",
        "actual_result": "待验证"
    }
    response = requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs",
        headers=headers,
        json=new_bug
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bug_data = response.json().get("data", {})
        bug_id = bug_data.get("id")
        print(f"✓ 创建成功，Bug ID: {bug_id}")
        print(f"  标题: {bug_data['title']}")
        print(f"  状态: {bug_data['status']}")
        print(f"  优先级: {bug_data['priority']}")
    else:
        print(f"✗ 创建失败: {response.text}")
        return
    print()
    
    # 获取Bug详情
    print(f"4. 获取Bug详情 (ID: {bug_id})...")
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug_id}",
        headers=headers
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bug_data = response.json().get("data", {})
        print(f"✓ 获取成功")
        print(f"  标题: {bug_data['title']}")
        print(f"  描述: {bug_data['description']}")
        print(f"  创建时间: {bug_data['created_at']}")
    print()
    
    # 更新Bug
    print(f"5. 更新Bug (ID: {bug_id})...")
    update_data = {
        "priority": "high",
        "status": "in_progress",
        "description": "更新后的描述 - 已开始处理"
    }
    response = requests.put(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug_id}",
        headers=headers,
        json=update_data
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bug_data = response.json().get("data", {})
        print(f"✓ 更新成功")
        print(f"  新状态: {bug_data['status']}")
        print(f"  新优先级: {bug_data['priority']}")
    print()
    
    # 解决Bug
    print(f"6. 解决Bug (ID: {bug_id})...")
    resolve_data = {
        "resolution": "fixed",
        "resolution_note": "问题已修复并测试通过"
    }
    response = requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug_id}/resolve",
        headers=headers,
        json=resolve_data
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bug_data = response.json().get("data", {})
        print(f"✓ 解决成功")
        print(f"  状态: {bug_data['status']}")
        print(f"  解决方案: {bug_data['resolution']}")
        print(f"  解决时间: {bug_data['resolved_at']}")
    print()
    
    # 重新打开Bug
    print(f"7. 重新打开Bug (ID: {bug_id})...")
    response = requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug_id}/reopen",
        headers=headers
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bug_data = response.json().get("data", {})
        print(f"✓ 重新打开成功")
        print(f"  状态: {bug_data['status']}")
    print()
    
    # 获取统计信息
    print("8. 获取Bug统计信息...")
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/statistics",
        headers=headers
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        stats = response.json().get("data", {})
        print(f"✓ 获取成功")
        print(f"  总计: {stats['total']} 条")
        print(f"  按状态: {stats['by_status']}")
        print(f"  按优先级: {stats['by_priority']}")
        print(f"  按严重程度: {stats['by_severity']}")
    print()
    
    # 测试查询过滤
    print("9. 测试查询过滤 (status=open)...")
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?status=open",
        headers=headers
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        bugs = response.json().get("data", [])
        print(f"✓ 查询成功，找到 {len(bugs)} 条待处理Bug")
    print()
    
    # 删除Bug
    print(f"10. 删除Bug (ID: {bug_id})...")
    response = requests.delete(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug_id}",
        headers=headers
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"✓ 删除成功")
    print()
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    try:
        test_bug_apis()
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
