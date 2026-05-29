"""
Playwright 测试脚本运行器

使用方法：
1. 修改下方的可配置参数
2. 运行: python shell/run_ts.py

或者从项目根目录运行:
   python shell\run_ts.py
"""

import subprocess
import sys
from pathlib import Path

# ============================================================================
# 可修改参数
# ============================================================================

# 脚本文件名（位于 playwright_scripts/tests/ 目录下）
SCRIPT_NAME = "search_billing_items_by_uom.spec.ts"

# 登录态文件路径（相对于 playwright_scripts/ 目录）
AUTH_STATE = "auth_state/bnp_auth.json"

# 是否显示浏览器（True=有头模式，False=无头模式）
HEADED = True

# 浏览器项目（chromium, firefox, webkit）
PROJECT = "chromium"

# 单个测试超时时间（毫秒）- 公司网络慢，建议 120000（2分钟）或更长
TEST_TIMEOUT = 120000

# Python 脚本整体超时（秒）- 应大于 TEST_TIMEOUT
SCRIPT_TIMEOUT = 360000

# ============================================================================
# 以下代码无需修改
# ============================================================================

def do_bnp_login():
    """调用 BNP 登录工具进行登录"""
    print("\n" + "=" * 60)
    print("🔐 登录态不存在，开始自动登录...")
    print("=" * 60)
    
    try:
        # 动态导入避免循环依赖
        from tools.playwright.bnp_auth_tool import bnp_login_and_save
        result = bnp_login_and_save()
        
        if result.get("success"):
            print(f"✅ 登录成功: {result.get('message')}")
            return True
        else:
            print(f"❌ 登录失败: {result.get('error', result.get('message'))}")
            return False
    except Exception as e:
        print(f"❌ 登录过程出错: {e}")
        return False


def main():
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    playwright_dir = project_root / "playwright_scripts"
    
    # 检查脚本文件是否存在
    script_path = playwright_dir / "tests" / SCRIPT_NAME
    if not script_path.exists():
        print(f"❌ 脚本文件不存在: {script_path}")
        sys.exit(1)
    
    # 检查登录态文件是否存在
    auth_path = playwright_dir / AUTH_STATE
    if not auth_path.exists():
        print(f"⚠️ 登录态文件不存在: {auth_path}")
        # 自动登录
        if not do_bnp_login():
            print("❌ 自动登录失败，请手动登录后重试")
            sys.exit(1)
        # 重新检查
        if not auth_path.exists():
            print("❌ 登录后仍找不到登录态文件")
            sys.exit(1)
    else:
        # 检查登录态是否过期（30分钟有效期）
        try:
            from tools.playwright.bnp_auth_tool import bnp_check_auth
            check_result = bnp_check_auth(str(auth_path.relative_to(project_root)))
            if not check_result.get("valid"):
                print(f"⚠️ 登录态已过期: {check_result.get('message')}")
                # 自动重新登录
                if not do_bnp_login():
                    print("❌ 自动登录失败，请手动登录后重试")
                    sys.exit(1)
            else:
                print(f"✅ 登录态有效（剩余时间: {check_result.get('time_remaining', '未知')}）")
        except Exception as e:
            print(f"⚠️ 检查登录态时出错: {e}，继续运行")
    
    # 构建命令
    cmd = [
        "npx", "playwright", "test",
        f"tests/{SCRIPT_NAME}",
        f"--project={PROJECT}",
        f"--timeout={TEST_TIMEOUT}",  # 单个测试超时
    ]
    
    if HEADED:
        cmd.append("--headed")
    
    # 设置环境变量
    env = {
        **dict(__import__('os').environ),
        "PLAYWRIGHT_AUTH_STATE": AUTH_STATE,
    }
    
    # 打印运行信息
    print("\n" + "=" * 60)
    print("🚀 Playwright 测试运行器")
    print("=" * 60)
    print(f"  脚本: {SCRIPT_NAME}")
    print(f"  登录态: {AUTH_STATE}")
    print(f"  模式: {'有头' if HEADED else '无头'}")
    print(f"  项目: {PROJECT}")
    print(f"  测试超时: {TEST_TIMEOUT}ms")
    print(f"  工作目录: {playwright_dir}")
    print("=" * 60)
    print()
    
    # 执行命令
    try:
        result = subprocess.run(
            cmd,
            cwd=str(playwright_dir),
            env=env,
            timeout=SCRIPT_TIMEOUT,
            shell=True,  # Windows 需要 shell=True 来找到 npx
        )
        sys.exit(result.returncode)
    except subprocess.TimeoutExpired:
        print(f"❌ 脚本整体超时（{SCRIPT_TIMEOUT}秒）")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        sys.exit(130)


if __name__ == "__main__":
    main()
