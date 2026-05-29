#!/usr/bin/env python3
"""
BNP 登录态刷新脚本

检查登录态有效性，如果无效则自动重新登录。

运行方式:
    python shell/refresh_auth.py           # 检查并自动刷新
    python shell/refresh_auth.py --force   # 强制重新登录
    python shell/refresh_auth.py --check   # 仅检查，不刷新
"""

import argparse
import json
import sys
from pathlib import Path

# 添加项目根目录到路径（shell 目录的上级目录）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="BNP 登录态刷新工具")
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="强制重新登录，忽略现有登录态"
    )
    parser.add_argument(
        "--check", 
        action="store_true", 
        help="仅检查登录态，不刷新"
    )
    parser.add_argument(
        "--headless", 
        action="store_true", 
        help="无头模式运行（不显示浏览器）"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔐 BNP 登录态管理")
    print("=" * 60)
    
    from tools.playwright.bnp_auth_tool import bnp_check_auth, bnp_login_and_save
    
    # 如果只是检查
    if args.check:
        print("\n📋 检查登录态...")
        result = bnp_check_auth()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result.get("valid"):
            print("\n✅ 登录态有效")
            return 0
        else:
            print("\n❌ 登录态无效或不存在")
            return 1
    
    # 如果强制刷新
    if args.force:
        print("\n🔄 强制重新登录...")
        need_login = True
    else:
        # 检查现有登录态
        print("\n📋 检查现有登录态...")
        check_result = bnp_check_auth()
        
        if not check_result.get("exists"):
            print("⚠️  登录态文件不存在")
            need_login = True
        elif not check_result.get("valid"):
            print(f"⚠️  登录态无效: {check_result.get('message')}")
            need_login = True
        elif check_result.get("token_expired"):
            print(f"⚠️  登录态已过期: {check_result.get('token_expires_at')}")
            need_login = True
        else:
            print(f"✅ 登录态有效（剩余时间: {check_result.get('time_remaining', '未知')}）")
            need_login = False
    
    if need_login:
        print("\n🔄 正在重新登录...")
        login_result = bnp_login_and_save(headless=args.headless)
        
        if login_result.get("success"):
            print("\n✅ 登录成功！")
            print(f"   文件: {login_result.get('auth_state_path')}")
            print(f"   Cookies: {login_result.get('cookies_count', 0)} 个")
            print(f"   SignToken: {'已保存' if login_result.get('has_sign_token') else '未找到'}")
            return 0
        else:
            print(f"\n❌ 登录失败: {login_result.get('error')}")
            return 1
    else:
        print("\n✅ 无需刷新，登录态有效")
        return 0


if __name__ == "__main__":
    sys.exit(main())
