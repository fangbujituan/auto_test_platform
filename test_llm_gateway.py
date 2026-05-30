#!/usr/bin/env python3
"""测试整合后的 LLM Gateway。"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.services.llm_gateway import get_model, get_default_model


def test_integration():
    print("=" * 60)
    print("测试 LLM Gateway 整合")
    print("=" * 60)
    
    # 加载环境变量
    load_dotenv()
    
    try:
        # 1. 测试获取默认模型
        print("\n[1/2] 测试获取默认模型...")
        llm = get_default_model()
        print("  ✓ 默认模型获取成功")
        
        # 2. 测试调用模型
        print("\n[2/2] 测试调用模型...")
        result = llm.invoke("你好，请简单介绍一下你自己")
        print("  ✓ 模型调用成功")
        print(f"\n响应内容:\n{result.content}")
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_integration()
