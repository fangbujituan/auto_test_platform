"""
测试Bug修复 - 验证创建Bug功能。

作者: yandc
创建时间: 2026-01-22
"""
import requests
import json

BASE_URL = "http://localhost:12048"
PROJECT_ID = 5  # 根据实际情况调整

def test_create_bug():
    """测试创建Bug功能。"""
    print("=== 测试Bug创建功能修复 ===\n")
    
    # 1. 登录
    print("1. 登录获取token...")
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    
    if response.status_code != 200:
        print(f"✗ 登录失败: {response.text}")
        return False
    
    data = response.json()
    token = data.get("data", {}).get("token")
    if not token:
        print("✗ 未获取到token")
        return False
    
    print(f"✓ 登录成功")
    print(f"  Token: {token[:30]}...")
    print()
    
    # 2. 创建Bug
    print("2. 创建Bug...")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Username": "admin",
        "Content-Type": "application/json"
    }
    
    bug_data = {
        "title": "测试Bug - 修复验证",
        "description": "这是用于验证500错误修复的测试Bug",
        "status": "open",
        "priority": "medium",
        "severity": "normal",
        "category": "测试",
        "module": "Bug管理",
        "environment": "Windows 11",
        "version": "v1.0.0",
        "steps_to_reproduce": "1. 运行测试脚本\n2. 观察结果",
        "expected_result": "Bug创建成功",
        "actual_result": "待验证"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs",
        headers=headers,
        json=bug_data
    )
    
    print(f"  状态码: {response.status_code}")
    print(f"  响应: {response.text[:200]}...")
    print()
    
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            bug = result.get("data", {})
            print("✓ Bug创建成功！")
            print(f"  Bug ID: {bug.get('id')}")
            print(f"  标题: {bug.get('title')}")
            print(f"  状态: {bug.get('status')}")
            print(f"  优先级: {bug.get('priority')}")
            print(f"  报告人ID: {bug.get('reporter_id')}")
            print(f"  创建时间: {bug.get('created_at')}")
            print()
            return True
        else:
            print(f"✗ 创建失败: {result.get('message')}")
            return False
    else:
        print(f"✗ 请求失败: {response.text}")
        return False


def test_get_bugs():
    """测试获取Bug列表。"""
    print("3. 获取Bug列表...")
    
    # 登录
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    token = response.json().get("data", {}).get("token")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Username": "admin"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        bugs = result.get("data", [])
        print(f"✓ 获取成功，共 {len(bugs)} 条Bug")
        if bugs:
            print(f"  最新Bug: {bugs[0].get('title')}")
        print()
        return True
    else:
        print(f"✗ 获取失败: {response.text}")
        return False


def test_statistics():
    """测试统计信息。"""
    print("4. 获取统计信息...")
    
    # 登录
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    token = response.json().get("data", {}).get("token")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Username": "admin"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/statistics",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        stats = result.get("data", {})
        print("✓ 统计信息获取成功")
        print(f"  总计: {stats.get('total')} 条")
        print(f"  按状态: {stats.get('by_status')}")
        print(f"  按优先级: {stats.get('by_priority')}")
        print()
        return True
    else:
        print(f"✗ 获取失败: {response.text}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Bug管理模块修复验证测试")
    print("=" * 60)
    print()
    
    try:
        # 测试创建Bug
        success1 = test_create_bug()
        
        # 测试获取Bug列表
        success2 = test_get_bugs()
        
        # 测试统计信息
        success3 = test_statistics()
        
        print("=" * 60)
        if success1 and success2 and success3:
            print("✓ 所有测试通过！Bug管理模块工作正常。")
        else:
            print("✗ 部分测试失败，请检查错误信息。")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 测试过程中出现异常: {str(e)}")
        import traceback
        traceback.print_exc()
