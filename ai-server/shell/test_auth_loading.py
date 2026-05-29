#!/usr/bin/env python3
"""
测试 Playwright 登录态加载

对比测试：
1. 无需登录页面（Billing.aspx）
2. 需要登录页面（Vue 内部页面）

运行: python shell/test_auth_loading.py
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_auth_loading():
    """测试登录态加载"""
    
    # 登录态文件路径（正斜杠格式）
    auth_state_path = project_root / "playwright_scripts" / "auth_state" / "bnp_auth.json"
    auth_state_path_str = str(auth_state_path).replace("\\", "/")
    
    print("=" * 60)
    print("🧪 测试 Playwright 登录态加载")
    print("=" * 60)
    print(f"登录态文件: {auth_state_path_str}")
    print(f"文件存在: {auth_state_path.exists()}")
    
    if not auth_state_path.exists():
        print("❌ 登录态文件不存在，请先运行 refresh_auth.py")
        return
    
    # 读取登录态内容
    with open(auth_state_path, "r", encoding="utf-8") as f:
        auth_data = json.load(f)
    
    cookies_count = len(auth_data.get("cookies", []))
    origins = auth_data.get("origins", [])
    localStorage_count = sum(len(o.get("localStorage", [])) for o in origins)
    
    print(f"Cookies 数量: {cookies_count}")
    print(f"localStorage 项数: {localStorage_count}")
    
    # 查找 SignToken
    sign_token = None
    for origin in origins:
        for item in origin.get("localStorage", []):
            if item.get("name") == "SignToken":
                sign_token = item.get("value", "")[:50] + "..."
                break
    
    print(f"SignToken: {'存在' if sign_token else '未找到'}")
    print("=" * 60)
    
    # 使用 Playwright 测试
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright 未安装")
        return
    
    # 测试页面列表
    test_pages = [
        {
            "name": "无需登录页面（Billing.aspx）",
            "url": "https://bnp-test.item.pub/Home.html",
            "need_auth": False
        },
        {
            "name": "需要登录页面（Vue 内部页面）",
            "url": "https://bnp-test.item.pub/vue/#/billing/billing-setup/billing-full-set/billing-items",
            "need_auth": True
        }
    ]
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)
        
        # 创建 context 并加载登录态
        print(f"\n📦 加载登录态: {auth_state_path_str}")
        context = browser.new_context(
            storage_state=auth_state_path_str,
            viewport={"width": 1920, "height": 1080},
        )
        
        for i, page_info in enumerate(test_pages):
            print(f"\n{'=' * 60}")
            print(f"测试 {i + 1}: {page_info['name']}")
            print(f"需要登录态: {'是' if page_info['need_auth'] else '否'}")
            print("=" * 60)
            
            page = context.new_page()
            
            print(f"🚀 导航到: {page_info['url']}")
            page.goto(page_info['url'], timeout=360000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            
            current_url = page.url
            page_title = page.title()
            
            print(f"\n📍 当前 URL: {current_url}")
            print(f"📄 页面标题: {page_title}")
            
            # 判断结果
            if "login" in current_url.lower() or "Login" in page_title:
                print("❌ 被重定向到登录页面")
            elif page_info['need_auth']:
                if "billing" in current_url.lower() or "Billing" in page_title:
                    print("✅ 成功访问，登录态有效！")
                else:
                    print("⚠️ 页面状态未知")
            else:
                print("✅ 页面正常加载")
            
            # 截图
            screenshot_name = f"test_auth_{i + 1}_{'auth' if page_info['need_auth'] else 'public'}.png"
            screenshot_path = project_root / screenshot_name
            page.screenshot(path=str(screenshot_path))
            print(f"📸 截图已保存: {screenshot_path}")
            
            page.close()
        
        browser.close()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_auth_loading()
