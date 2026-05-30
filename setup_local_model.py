'''
Author: fangbu 1581779395@qq.com
Date: 2026-05-30 13:26:24
LastEditors: fangbu 1581779395@qq.com
LastEditTime: 2026-05-30 13:34:38
FilePath: /auto_test_platform/setup_local_model.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
#!/usr/bin/env python3
"""配置局域网大模型到测试平台"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app import create_app
from app.models.base import db
from app.models.ai_provider import AIProviderConfig
from app.utils.crypto import CryptoUtil

def setup_local_model():
    app = create_app()
    
    with app.app_context():
        # 检查是否已有这个配置
        existing = AIProviderConfig.query.filter_by(name="局域网 Llama3.2-1B").first()
        
        if existing:
            print(f"已存在配置: {existing.name}")
            print(f"  ID: {existing.id}")
            print(f"  Base URL: {existing.base_url}")
            print(f"  Model: {existing.model_name}")
            print("更新现有配置...")
            config = existing
        else:
            print("创建新配置...")
            config = AIProviderConfig()
        
        # 设置配置
        config.name = "局域网 Llama3.2-1B"
        config.provider_type = "openai"
        config.api_key_encrypted = CryptoUtil.encrypt("sk-your-super-secret-key-2026")
        config.base_url = "http://192.168.1.7:4000"
        config.model_name = "llama3.2-1b"
        config.is_enabled = True
        
        if not existing:
            db.session.add(config)
        
        # 设置为默认（如果还没有默认配置）
        default_exists = AIProviderConfig.query.filter_by(is_default=True).first()
        if not default_exists:
            config.is_default = True
            print("设置为默认提供商")
        else:
            print(f"当前默认提供商: {default_exists.name}")
            answer = input("是否将新配置设为默认? (y/n): ").strip().lower()
            if answer == 'y':
                # 取消其他默认
                AIProviderConfig.query.filter(AIProviderConfig.id != config.id).update({"is_default": False})
                config.is_default = True
                print("已设置为默认提供商")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("配置完成!")
        print("=" * 60)
        print(f"配置名称: {config.name}")
        print(f"提供商类型: {config.provider_type}")
        print(f"Base URL: {config.base_url}")
        print(f"模型名称: {config.model_name}")
        print(f"默认提供商: {'是' if config.is_default else '否'}")
        print(f"已启用: {'是' if config.is_enabled else '否'}")
        print("=" * 60)
        print("\n现在你可以在测试平台中使用这个本地模型了!")

if __name__ == "__main__":
    setup_local_model()
