#!/usr/bin/env python3
"""测试局域网内的大模型连接 - 简化版（无需额外依赖）"""

import socket
import urllib.request
import json
import sys

def test_connection():
    # 配置信息
    BASE_URL = "http://192.168.1.7:4000"
    API_KEY = "sk-your-super-secret-key-2026"
    MODEL_NAME = "llama3.2-1b"

    print("=" * 60)
    print("局域网大模型连接测试")
    print("=" * 60)
    print(f"Base URL:  {BASE_URL}")
    print(f"API Key:   {API_KEY}")
    print(f"Model:     {MODEL_NAME}")
    print()

    # 1. 先测试基础网络连接
    print("[1/3] 测试网络连接...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex(('192.168.1.7', 4000))
        s.close()
        if result == 0:
            print("  ✓ 网络连接正常，端口开放")
        else:
            print(f"  ✗ 网络连接失败，错误码: {result}")
            print("  可能原因:")
            print("    - 服务未启动")
            print("    - IP 地址错误")
            print("    - 端口错误 (当前配置为 4000)")
            print("    - 防火墙阻止")
    except Exception as e:
        print(f"  ✗ 网络连接测试出错: {e}")

    # 2. 测试 /v1/models 端点（如果有的话）
    print("\n[2/3] 测试 /v1/models 端点...")
    try:
        url = f"{BASE_URL}/v1/models"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {API_KEY}")
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("  ✓ 服务响应正常")
            print("  可用模型:")
            for model in data.get('data', []):
                print(f"    - {model.get('id')}")
    except urllib.error.URLError as e:
        print(f"  ✗ 请求失败: {e}")
        print("  提示: 某些部署可能不提供 /v1/models 端点")
    except Exception as e:
        print(f"  ✗ 模型列表查询出错: {e}")

    # 3. 实际发送聊天请求
    print("\n[3/3] 发送测试聊天请求...")
    try:
        url = f"{BASE_URL}/v1/chat/completions"
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "你好，请简单介绍一下你自己"}],
            "temperature": 0.7,
            "max_tokens": 512
        }
        
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {API_KEY}")
        req.add_header("Content-Type", "application/json")
        
        json_data = json.dumps(payload).encode('utf-8')
        
        with urllib.request.urlopen(req, json_data, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("  ✓ 请求成功!")
            choice = data.get('choices', [{}])[0]
            content = choice.get('message', {}).get('content', '')
            print(f"  响应内容: {content}")
            usage = data.get('usage', {})
            if usage:
                print(f"  Token 使用: {usage}")
    except urllib.error.HTTPError as e:
        print(f"  ✗ HTTP 错误: {e.code}")
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            print(f"  错误详情: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
        except:
            print(f"  错误响应: {e.read().decode('utf-8', errors='ignore')[:500]}")
    except urllib.error.URLError as e:
        print(f"  ✗ URL 错误: {e}")
    except Exception as e:
        print(f"  ✗ 请求出错: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("诊断建议:")
    print("  1. 确认服务已启动: 在 192.168.1.7 机器上检查进程是否运行")
    print("  2. 确认 IP 地址: 检查部署大模型的机器 IP 是否为 192.168.1.7")
    print("  3. 确认端口: 检查服务是否监听在 4000 端口")
    print("  4. 检查防火墙: 确认防火墙允许 4000 端口的入站连接")
    print("  5. 检查 API Key: 确认 API Key 是否正确")
    print("  6. 检查模型名: 确认模型名 llama3.2-1b 是否存在")
    print("=" * 60)

if __name__ == "__main__":
    test_connection()
