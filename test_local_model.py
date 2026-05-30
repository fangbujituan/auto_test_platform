'''
Author: fangbu 1581779395@qq.com
Date: 2026-05-30 13:24:54
LastEditors: fangbu 1581779395@qq.com
LastEditTime: 2026-05-30 13:24:56
FilePath: /auto_test_platform/test_local_model.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
#!/usr/bin/env python3
"""测试局域网内的大模型连接"""

import sys
import os

# 添加 app 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from services.ai_adapters import OpenAIAdapter, get_adapter

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
    print("[1/4] 测试网络连接...")
    try:
        import socket
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

    # 2. 使用 OpenAIAdapter 测试连接
    print("\n[2/4] 使用 OpenAIAdapter 测试连接...")
    try:
        adapter = OpenAIAdapter(
            api_key=API_KEY,
            base_url=BASE_URL,
            model_name=MODEL_NAME
        )
        result = adapter.test_connection()
        print(f"  成功: {result.get('success')}")
        print(f"  消息: {result.get('message')}")
        if result.get('latency_ms'):
            print(f"  延迟: {result.get('latency_ms')} ms")
    except Exception as e:
        print(f"  ✗ 测试连接出错: {e}")

    # 3. 实际发送聊天请求
    print("\n[3/4] 发送测试聊天请求...")
    try:
        messages = [{"role": "user", "content": "你好，请简单介绍一下你自己"}]
        result = adapter.chat(messages, temperature=0.7, max_tokens=512)
        
        if 'error_code' in result:
            print(f"  ✗ 请求失败:")
            print(f"    错误码: {result.get('error_code')}")
            print(f"    错误信息: {result.get('error_message')}")
        else:
            print(f"  ✓ 请求成功!")
            print(f"  响应内容: {result.get('content')}")
            print(f"  Token 使用: {result.get('usage')}")
    except Exception as e:
        print(f"  ✗ 请求出错: {e}")

    # 4. 诊断建议
    print("\n[4/4] 诊断建议:")
    print("  1. 确认服务已启动: 在 192.168.1.7 机器上检查进程是否运行")
    print("  2. 确认 IP 地址: 检查部署大模型的机器 IP 是否为 192.168.1.7")
    print("  3. 确认端口: 检查服务是否监听在 4000 端口")
    print("  4. 检查防火墙: 确认防火墙允许 4000 端口的入站连接")
    print("  5. 检查 API Key: 确认 API Key 是否正确")
    print("  6. 检查模型名: 确认模型名 llama3.2-1b 是否存在")

if __name__ == "__main__":
    test_connection()
