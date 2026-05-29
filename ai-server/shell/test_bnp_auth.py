"""
测试 BNP 登录态工具

步骤：
1. 登录 BNP 系统并保存登录态
2. 检查登录态有效性
3. 使用登录态访问目标页面

运行: python shell/test_bnp_auth.py
"""

import json
from pathlib import Path

# 添加项目根目录到路径（shell 目录的上级目录）
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.playwright.bnp_auth_tool import bnp_login_and_save, bnp_check_auth


def test_bnp_auth():
    """测试 BNP 登录态功能."""
    
    print("=" * 60)
    print("BNP 登录态工具测试")
    print("=" * 60)
    
    # 步骤 1: 登录并保存登录态
    print("\n[步骤 1] 登录 BNP 系统并保存登录态...")
    print("-" * 40)
    
    login_result = bnp_login_and_save(
        headless=False,  # 显示浏览器，方便观察
    )
    
    print(f"\n登录结果:")
    print(json.dumps(login_result, ensure_ascii=False, indent=2))
    
    if not login_result.get("success"):
        print("\n❌ 登录失败，测试终止")
        return
    
    print("\n✅ 登录成功！")
    
    # 步骤 2: 检查登录态有效性
    print("\n[步骤 2] 检查登录态有效性...")
    print("-" * 40)
    
    check_result = bnp_check_auth()
    print(f"\n登录态检查结果:")
    print(json.dumps(check_result, ensure_ascii=False, indent=2))
    
    if not check_result.get("valid"):
        print("\n❌ 登录态无效，测试终止")
        return
    
    print("\n✅ 登录态有效！")
    
    # 步骤 3: 使用登录态访问目标页面
    print("\n[步骤 3] 使用登录态访问目标页面...")
    print("-" * 40)
    
    target_url = "https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items/form-data"
    auth_state_path = login_result.get("auth_state_path")
    
    print(f"目标页面: {target_url}")
    print(f"登录态文件: {auth_state_path}")
    
    # 使用 Playwright 加载登录态并访问页面
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n❌ Playwright 未安装")
        return
    
    try:
        with sync_playwright() as p:
            # 启动浏览器（显示界面）
            browser = p.chromium.launch(headless=False)
            
            # 创建 context 并加载登录态
            context = browser.new_context(
                storage_state=auth_state_path,
                viewport={"width": 1920, "height": 1080},
            )
            
            page = context.new_page()
            
            # 访问目标页面
            print(f"\n正在访问: {target_url}")
            page.goto(target_url, timeout=220000)
            page.wait_for_load_state("networkidle")
            
            # 等待页面加载
            page.wait_for_timeout(25000)
            
            current_url = page.url
            page_title = page.title()
            
            print(f"\n当前 URL: {current_url}")
            print(f"页面标题: {page_title}")
            
            # 截图保存到项目根目录
            screenshot_path = project_root / "bnp_auth_test_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            print(f"\n截图已保存: {screenshot_path}")
            
            # 检查是否在目标页面
            if "billing-items" in current_url or "form-data" in current_url:
                print("\n✅ 成功访问目标页面！")
                print("🎉 测试完成！浏览器将保持打开状态 60 秒供您查看...")
                page.wait_for_timeout(60000)
            elif "Login" in page_title or "login" in current_url.lower():
                print("\n❌ 被重定向到登录页面，登录态可能无效")
            else:
                print(f"\n⚠️ 当前不在目标页面")
            
            browser.close()
            
    except Exception as e:
        print(f"\n❌ 访问页面时出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试结束")
    print("=" * 60)


if __name__ == "__main__":
    test_bnp_auth()
