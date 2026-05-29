"""BNP 系统登录态管理工具.

专门用于 BNP 系统的登录和登录态管理：
1. 自动登录 BNP 系统
2. 使用 context.storageState() 保存完整登录态（cookies + localStorage）
3. 验证登录态有效性
4. 后续访问时直接读取已保存的登录态
5. 文件锁机制防止并发登录

使用方法：
    from tools.playwright.bnp_auth_tool import create_bnp_login_tool, create_bnp_check_auth_tool
    
    login_tool = create_bnp_login_tool()
    result = login_tool.invoke({})  # 自动登录并保存登录态
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool, BaseTool

from tools.debug.readlog import logs
from tools.playwright.config import UIAutomationConfig, DEFAULT_CONFIG


# ============================================================================
# 常量定义
# ============================================================================

# BNP 系统配置
BNP_LOGIN_URL = "https://bnp-test.item.pub/"
BNP_USERNAME = "fangbu"
BNP_PASSWORD = "123456"

# 默认登录态保存路径（相对于工作空间根目录）
# 统一登录态目录到 playwright_scripts/auth_state/
DEFAULT_AUTH_STATE_PATH = "playwright_scripts/auth_state/bnp_auth.json"

# ============================================================================
# 登录锁机制（防止并发登录）
# ============================================================================

# 锁文件后缀
LOCK_SUFFIX = ".logging_in"

# 全局内存锁（用于同一进程内的并发控制）
_login_in_progress = False


def _get_lock_file_path(auth_state_path: str, config: UIAutomationConfig | None = None) -> Path:
    """获取锁文件路径"""
    cfg = config or DEFAULT_CONFIG
    return Path(cfg.workspace_root) / f"{auth_state_path}{LOCK_SUFFIX}"


def _is_login_in_progress(auth_state_path: str, config: UIAutomationConfig | None = None) -> bool:
    """
    检查是否有登录正在进行中.
    
    同时检查内存锁和文件锁，防止跨进程并发登录。
    """
    global _login_in_progress
    
    # 检查内存锁
    if _login_in_progress:
        return True
    
    # 检查文件锁
    lock_file = _get_lock_file_path(auth_state_path, config)
    if lock_file.exists():
        # 检查锁文件是否过期（超过 60 秒视为死锁，自动清理）
        lock_age = time.time() - lock_file.stat().st_mtime
        if lock_age > 60:
            logs.warning(f"[BNP Auth] ⚠️ 发现过期的登录锁，自动清理: {lock_file}")
            lock_file.unlink()
            return False
        return True
    
    return False


def _acquire_login_lock(auth_state_path: str, config: UIAutomationConfig | None = None) -> bool:
    """
    获取登录锁.
    
    Returns:
        True 表示成功获取锁，False 表示已有其他进程在登录中
    """
    global _login_in_progress
    
    if _is_login_in_progress(auth_state_path, config):
        return False
    
    # 设置内存锁
    _login_in_progress = True
    
    # 设置文件锁
    lock_file = _get_lock_file_path(auth_state_path, config)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(f"{datetime.now().isoformat()}\npid={None}")  # 可扩展添加 PID
    
    logs.info(f"[BNP Auth] 🔒 获取登录锁: {lock_file}")
    return True


def _release_login_lock(auth_state_path: str, config: UIAutomationConfig | None = None) -> None:
    """释放登录锁"""
    global _login_in_progress
    
    # 释放内存锁
    _login_in_progress = False
    
    # 释放文件锁
    lock_file = _get_lock_file_path(auth_state_path, config)
    if lock_file.exists():
        lock_file.unlink()
        logs.info(f"[BNP Auth] 🔓 释放登录锁: {lock_file}")


def wait_for_login_complete(
    auth_state_path: str = DEFAULT_AUTH_STATE_PATH,
    config: UIAutomationConfig | None = None,
    timeout: float = 60.0,
    poll_interval: float = 1.0,
) -> dict[str, Any]:
    """
    等待正在进行的登录完成.
    
    如果检测到有其他进程正在登录，等待其完成并返回登录态检查结果。
    
    Args:
        auth_state_path: 登录态文件路径
        config: UI 自动化配置
        timeout: 最长等待时间（秒）
        poll_interval: 轮询间隔（秒）
        
    Returns:
        包含等待结果的字典
    """
    result = {
        "waited": False,
        "success": False,
        "auth_state_path": auth_state_path,
    }
    
    if not _is_login_in_progress(auth_state_path, config):
        result["message"] = "没有正在进行的登录"
        return result
    
    logs.info(f"[BNP Auth] ⏳ 检测到其他进程正在登录，等待完成...")
    result["waited"] = True
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        # 检查锁是否已释放
        if not _is_login_in_progress(auth_state_path, config):
            logs.info(f"[BNP Auth] ✅ 登录已完成，等待时间: {time.time() - start_time:.1f}秒")
            
            # 检查登录态文件是否已创建
            cfg = config or DEFAULT_CONFIG
            auth_file = Path(cfg.workspace_root) / auth_state_path
            
            if auth_file.exists():
                check_result = bnp_check_auth(auth_state_path, config)
                result.update({
                    "success": check_result.get("valid", False),
                    "message": "等待登录成功",
                    "check_result": check_result,
                })
            else:
                result["message"] = "登录失败：登录态文件未创建"
            
            return result
        
        time.sleep(poll_interval)
    
    # 超时
    result["message"] = f"等待登录超时（{timeout}秒）"
    logs.warning(f"[BNP Auth] ⚠️ {result['message']}")
    return result


# ============================================================================
# 核心登录函数
# ============================================================================

def bnp_login_and_save(
    username: str = BNP_USERNAME,
    password: str = BNP_PASSWORD,
    auth_state_path: str = DEFAULT_AUTH_STATE_PATH,
    headless: bool = False,
    config: UIAutomationConfig | None = None,
    wait_stable_seconds: int = 10,
) -> dict[str, Any]:
    """
    登录 BNP 系统并保存登录态.
    
    使用 Playwright 进行自动化登录，登录成功后保存完整的登录态
    （cookies + localStorage）到 JSON 文件。
    
    支持锁机制防止并发登录。
    
    Args:
        username: 用户名（默认 fangbu）
        password: 密码（默认 123456）
        auth_state_path: 登录态保存路径（相对于工作空间根目录）
        headless: 是否无头模式（默认 False，登录时建议显示浏览器）
        config: UI 自动化配置
        wait_stable_seconds: 登录成功后等待页面稳定的时间（秒，默认 10）
        
    Returns:
        包含登录结果的字典
    """
    # 动态导入 playwright，避免在模块加载时报错
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except ImportError:
        return {
            "success": False,
            "error": "Playwright 未安装，请运行: pip install playwright && playwright install chromium",
        }
    
    cfg = config or DEFAULT_CONFIG
    
    # 尝试获取登录锁
    if not _acquire_login_lock(auth_state_path, cfg):
        return {
            "success": False,
            "error": "login_in_progress",
            "message": "其他进程正在登录中，请稍后重试或调用 wait_for_login_complete() 等待",
        }
    
    # 解析保存路径
    auth_file = Path(cfg.workspace_root) / auth_state_path
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    
    result = {
        "success": False,
        "auth_state_path": str(auth_file),
        "login_url": BNP_LOGIN_URL,
        "username": username,
        "timestamp": datetime.now().isoformat(),
    }
    
    try:
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            
            # 1. 导航到登录页面
            logs.info(f"[BNP Auth] 导航到登录页面: {BNP_LOGIN_URL}")
            page.goto(BNP_LOGIN_URL, timeout=cfg.navigation_timeout)
            page.wait_for_load_state("networkidle")
            
            # 2. 输入用户名
            logs.info(f"[BNP Auth] 输入用户名: {username}")
            try:
                # 方法1：找到 Username 标签后的输入框
                page.get_by_text("Username:").wait_for(state="visible", timeout=5000)
                username_input = page.locator("input").first
                username_input.fill(username)
                logs.info("[BNP Auth] ✅ 用户名输入成功（方法1）")
            except Exception:
                # 方法2：直接使用 CSS 选择器
                page.locator('input[type="text"], input:not([type="password"])').first.fill(username)
                logs.info("[BNP Auth] ✅ 用户名输入成功（方法2）")
            
            # 3. 输入密码
            logs.info(f"[BNP Auth] 输入密码: {'*' * len(password)}")
            try:
                password_input = page.locator('input[type="password"]')
                password_input.fill(password)
                logs.info("[BNP Auth] ✅ 密码输入成功")
            except Exception:
                page.locator("input").nth(1).fill(password)
                logs.info("[BNP Auth] ✅ 密码输入成功（备用方法）")
            
            # 4. 点击登录按钮
            logs.info("[BNP Auth] 点击登录按钮...")
            try:
                page.get_by_role("button", name="Sign in").click()
                logs.info("[BNP Auth] ✅ 登录按钮点击成功")
            except Exception:
                page.locator("button").click()
                logs.info("[BNP Auth] ✅ 登录按钮点击成功（备用方法）")
            
            # 5. 等待登录完成 - 使用多种策略
            logs.info("[BNP Auth] 等待登录完成...")
            
            # 初始化变量（避免 UnboundLocalError）
            current_url = page.url
            page_title = page.title()
            
            # 判断登录是否成功
            login_success = False
            
            # 策略1：等待 URL 变化（不再停留在登录页）
            try:
                # 等待 URL 不再是登录页（最多等待 20 秒）
                page.wait_for_url(lambda url: url != BNP_LOGIN_URL and "login" not in url.lower(), timeout=20000)
                login_success = True
                current_url = page.url
                page_title = page.title()
                logs.info("[BNP Auth] 🎉 登录成功！（URL 已跳转）")
            except Exception as e:
                logs.warning(f"[BNP Auth] URL 跳转检测超时: {e}")
                
                # 策略2：检查页面标题和 URL
                current_url = page.url
                page_title = page.title()
                logs.info(f"[BNP Auth] 当前 URL: {current_url}")
                logs.info(f"[BNP Auth] 页面标题: {page_title}")
                
                # 登录成功的条件：URL 不是登录页，或标题不是 Login Form
                if current_url != BNP_LOGIN_URL and "login" not in current_url.lower():
                    login_success = True
                    logs.info("[BNP Auth] 🎉 登录成功！（URL 已变化）")
                elif page_title != "Login Form":
                    login_success = True
                    logs.info("[BNP Auth] 🎉 登录成功！（标题已变化）")
                elif "Home" in current_url or page_title == "Home":
                    login_success = True
                    logs.info("[BNP Auth] 🎉 登录成功！")
                else:
                    # 策略3：再等待一段时间检查 localStorage 中是否有 SignToken
                    page.wait_for_timeout(5000)
                    
                    # 检查是否有 SignToken
                    has_token = page.evaluate("() => localStorage.getItem('SignToken') !== null")
                    if has_token:
                        login_success = True
                        current_url = page.url
                        page_title = page.title()
                        logs.info("[BNP Auth] 🎉 登录成功！（检测到 SignToken）")
                    else:
                        logs.warning(f"[BNP Auth] ⚠️ 登录可能失败，当前页面: {page_title}")
                        logs.warning(f"[BNP Auth]   URL: {current_url}")
            
            if login_success:
                # 7. 等待页面完全稳定后再保存登录态（可配置时间）
                logs.info(f"[BNP Auth] ⏳ 等待 {wait_stable_seconds} 秒确保页面完全加载...")
                page.wait_for_timeout(wait_stable_seconds * 1000)
                
                # 8. 保存登录态（先删除旧文件）
                # 删除旧文件（如果存在）
                if auth_file.exists():
                    logs.info(f"[BNP Auth] 🗑️ 删除旧的登录态文件: {auth_file}")
                    auth_file.unlink()
                
                logs.info(f"[BNP Auth] 💾 保存登录态到: {auth_file}")
                context.storage_state(path=str(auth_file))
                
                # 9. 等待确保保存成功
                logs.info(f"[BNP Auth] ⏳ 等待 2 秒确保保存完成...")
                page.wait_for_timeout(2000)  # 等待 2 秒
                
                # 读取并显示保存的内容
                with open(auth_file, "r", encoding="utf-8") as f:
                    auth_data = json.load(f)
                
                cookies_count = len(auth_data.get("cookies", []))
                origins = auth_data.get("origins", [])
                localStorage_count = sum(len(o.get("localStorage", [])) for o in origins)
                
                logs.info(f"[BNP Auth] 📊 保存内容: {cookies_count} 个 cookies, {localStorage_count} 个 localStorage 项")
                
                # 检查关键登录信息
                sign_token = None
                for origin in origins:
                    for item in origin.get("localStorage", []):
                        if item.get("name") == "SignToken":
                            sign_token = item.get("value", "")[:50] + "..."
                            break
                
                result.update({
                    "success": True,
                    "message": "登录成功，登录态已保存",
                    "cookies_count": cookies_count,
                    "localStorage_count": localStorage_count,
                    "has_sign_token": sign_token is not None,
                    "final_url": current_url,
                    "final_title": page_title,
                })
            else:
                result.update({
                    "success": False,
                    "error": "登录失败，请检查用户名密码或网络连接",
                    "final_url": current_url,
                    "final_title": page_title,
                })
            
            # 关闭浏览器
            browser.close()
            
    except PlaywrightTimeoutError as e:
        result["error"] = f"操作超时: {e}"
    except Exception as e:
        result["error"] = f"登录过程出错: {e}"
    finally:
        # 释放登录锁
        _release_login_lock(auth_state_path, cfg)
    
    return result


def bnp_check_auth(
    auth_state_path: str = DEFAULT_AUTH_STATE_PATH,
    config: UIAutomationConfig | None = None,
    verify_with_page: bool = False,
) -> dict[str, Any]:
    """
    检查 BNP 登录态是否有效.
    
    读取已保存的登录态文件，检查：
    1. 文件是否存在
    2. 是否包含必要的登录信息（SignToken）
    3. JWT Token 是否过期（如果可解析）
    4. 可选：实际访问页面验证（verify_with_page=True）
    
    注意：JWT exp 字段只表示 token 理论有效期，服务器端会话可能更早过期。
    建议使用 verify_with_page=True 进行实际验证。
    
    Args:
        auth_state_path: 登录态文件路径（相对于工作空间根目录）
        config: UI 自动化配置
        verify_with_page: 是否通过实际访问页面验证登录态（默认 False）
        
    Returns:
        包含登录态状态的字典
    """
    import base64
    
    cfg = config or DEFAULT_CONFIG
    auth_file = Path(cfg.workspace_root) / auth_state_path
    
    result = {
        "exists": False,
        "auth_state_path": str(auth_file),
        "valid": False,
    }
    
    if not auth_file.exists():
        result["message"] = "登录态文件不存在"
        return result
    
    result["exists"] = True
    
    try:
        with open(auth_file, "r", encoding="utf-8") as f:
            auth_data = json.load(f)
        
        cookies_count = len(auth_data.get("cookies", []))
        origins = auth_data.get("origins", [])
        localStorage_count = sum(len(o.get("localStorage", [])) for o in origins)
        
        result["cookies_count"] = cookies_count
        result["localStorage_count"] = localStorage_count
        
        # 查找 SignToken
        sign_token = None
        for origin in origins:
            for item in origin.get("localStorage", []):
                if item.get("name") == "SignToken":
                    sign_token = item.get("value", "")
                    break
        
        if not sign_token:
            result["message"] = "登录态无效：缺少 SignToken"
            return result
        
        # 尝试解析 JWT Token 检查是否过期
        jwt_valid = False
        try:
            # JWT 格式: header.payload.signature
            parts = sign_token.split(".")
            if len(parts) >= 2:
                # 解码 payload（添加 padding）
                payload_b64 = parts[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
                payload = json.loads(payload_json)
                
                exp = payload.get("exp")
                if exp:
                    exp_time = datetime.fromtimestamp(exp)
                    now = datetime.now()
                    
                    result["token_expires_at"] = exp_time.isoformat()
                    result["token_expired"] = now > exp_time
                    result["time_remaining"] = str(exp_time - now) if now < exp_time else "已过期"
                    
                    if now > exp_time:
                        result["message"] = f"登录态已过期（JWT过期时间: {exp_time}）"
                        result["valid"] = False
                        return result
                    else:
                        jwt_valid = True
                        # JWT 未过期，但服务器端会话可能已过期
                        # 继续检查，不直接返回 True
                else:
                    jwt_valid = True
            else:
                jwt_valid = True
                
        except Exception as e:
            logs.warning(f"[bnp_check_auth] JWT 解析失败: {e}")
            jwt_valid = True  # 解析失败，假设 JWT 有效，继续其他检查
        
        # 获取文件修改时间
        mtime = datetime.fromtimestamp(auth_file.stat().st_mtime)
        result["modified_at"] = mtime.isoformat()
        
        # 检查文件修改时间
        # Playwright 官方文档：需要手动删除过期的 storage state
        # 最佳实践：超过 30 分钟就认为可能过期，需要强制刷新
        AUTH_STATE_MAX_AGE_MINUTES = 30  # 30 分钟超时
        
        file_age = datetime.now() - mtime
        result["file_age"] = str(file_age)
        result["file_age_minutes"] = file_age.total_seconds() / 60
        
        # 如果文件超过 30 分钟，认为已过期
        if file_age.total_seconds() > AUTH_STATE_MAX_AGE_MINUTES * 60:
            result["message"] = f"登录态已过期（文件已存在 {file_age}，超过 {AUTH_STATE_MAX_AGE_MINUTES} 分钟限制）"
            result["valid"] = False
            result["reason"] = "file_too_old"
            return result
        
        # 如果需要实际验证
        if verify_with_page:
            logs.info("[bnp_check_auth] 开始实际页面验证...")
            verify_result = _verify_auth_by_page(str(auth_file).replace("\\", "/"))
            result["page_verify"] = verify_result
            
            if verify_result.get("valid"):
                result["valid"] = True
                result["message"] = "登录态有效（实际页面验证通过）"
            else:
                result["valid"] = False
                result["message"] = f"登录态无效（{verify_result.get('reason', '页面验证失败')}）"
        else:
            # 没有实际验证，基于 JWT 和文件时间判断
            if jwt_valid:
                result["valid"] = True
                result["message"] = f"登录态可能有效（JWT未过期，剩余时间: {result.get('time_remaining', '未知')}）"
                result["warning"] = "JWT未过期不代表服务器会话有效，建议使用 verify_with_page=True 验证"
        
    except Exception as e:
        result["error"] = f"读取登录态文件失败: {e}"
    
    return result


def _verify_auth_by_page(auth_state_path: str) -> dict[str, Any]:
    """
    通过实际访问页面验证登录态是否有效。
    
    Args:
        auth_state_path: 登录态文件路径
        
    Returns:
        包含验证结果的字典
    """
    result = {"valid": False}
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["error"] = "Playwright 未安装"
        return result
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=auth_state_path,
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            
            # 访问需要登录的页面
            test_url = "https://bnp-test.item.pub/vue/#/billing/billing-setup/billing-full-set/billing-items"
            page.goto(test_url, timeout=30000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            
            current_url = page.url
            page_title = page.title()
            
            result["final_url"] = current_url
            result["page_title"] = page_title
            
            # 判断是否被重定向到登录页
            if "login" in current_url.lower() or "Login" in page_title:
                result["valid"] = False
                result["reason"] = "重定向到登录页"
            elif "billing" in current_url.lower():
                result["valid"] = True
                result["reason"] = "成功访问目标页面"
            else:
                result["valid"] = False
                result["reason"] = f"页面状态未知: {current_url}"
            
            browser.close()
            
    except Exception as e:
        result["error"] = str(e)
        result["reason"] = f"验证过程出错: {e}"
    
    return result


# ============================================================================
# 工具创建函数
# ============================================================================

def create_bnp_login_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """
    创建 BNP 系统登录工具.
    
    Returns:
        LangChain 工具实例
    """
    cfg = config or DEFAULT_CONFIG
    
    def login(
        username: str = BNP_USERNAME,
        password: str = BNP_PASSWORD,
        auth_state_path: str = DEFAULT_AUTH_STATE_PATH,
        headless: bool = False,
    ) -> str:
        """
        登录 BNP 系统并保存登录态.
        
        自动打开浏览器，输入用户名密码登录，成功后保存登录态到 JSON 文件。
        后续可以使用 run_playwright_script 配合 auth_state 参数直接访问 BNP 系统。
        
        Args:
            username: 用户名（默认 fangbu）
            password: 密码（默认 123456）
            auth_state_path: 登录态保存路径（默认 auth_state/bnp_auth.json）
            headless: 是否无头模式（默认 False，建议显示浏览器以便观察登录过程）
            
        Returns:
            JSON 格式的登录结果
        """
        result = bnp_login_and_save(
            username=username,
            password=password,
            auth_state_path=auth_state_path,
            headless=headless,
            config=cfg,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    return StructuredTool.from_function(
        name="bnp_login",
        func=login,
        description="""登录 BNP 系统并保存登录态。

自动打开浏览器，输入用户名密码登录，成功后保存登录态到 JSON 文件。
后续可以使用 run_playwright_script 配合 auth_state 参数直接访问 BNP 系统。

参数：
- username: 用户名（可选，默认 fangbu）
- password: 密码（可选，默认 123456）
- auth_state_path: 登录态保存路径（可选，默认 auth_state/bnp_auth.json）
- headless: 是否无头模式（可选，默认 False）

返回 JSON 格式的登录结果，包含：
- success: 是否成功
- auth_state_path: 登录态文件路径
- cookies_count: 保存的 cookies 数量
- localStorage_count: 保存的 localStorage 项数
- has_sign_token: 是否包含登录令牌

使用示例：
1. 调用此工具登录并保存登录态
2. 调用 run_playwright_script 执行脚本，设置 auth_state 参数
""",
    )


def create_bnp_check_auth_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """
    创建 BNP 登录态检查工具.
    
    Returns:
        LangChain 工具实例
    """
    cfg = config or DEFAULT_CONFIG
    
    def check_auth(auth_state_path: str = DEFAULT_AUTH_STATE_PATH) -> str:
        """
        检查 BNP 登录态是否有效.
        
        读取已保存的登录态文件，检查是否过期。
        
        Args:
            auth_state_path: 登录态文件路径（默认 auth_state/bnp_auth.json）
            
        Returns:
            JSON 格式的检查结果
        """
        result = bnp_check_auth(
            auth_state_path=auth_state_path,
            config=cfg,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    return StructuredTool.from_function(
        name="bnp_check_auth",
        func=check_auth,
        description="""检查 BNP 登录态是否有效。

读取已保存的登录态文件，检查：
1. 文件是否存在
2. 是否包含必要的登录信息（SignToken）
3. JWT Token 是否过期

参数：
- auth_state_path: 登录态文件路径（可选，默认 auth_state/bnp_auth.json）

返回 JSON 格式的检查结果，包含：
- exists: 文件是否存在
- valid: 登录态是否有效
- token_expired: Token 是否过期
- token_expires_at: Token 过期时间
- time_remaining: 剩余有效时间
""",
    )


# ============================================================================
# 列出所有登录态
# ============================================================================

def bnp_list_auth_states(
    auth_state_dir: str = "playwright_scripts/auth_state",
    config: UIAutomationConfig | None = None,
) -> dict[str, Any]:
    """
    列出所有已保存的登录态.
    
    Args:
        auth_state_dir: 登录态目录（相对于工作空间根目录）
        config: UI 自动化配置
        
    Returns:
        包含登录态列表的字典
    """
    cfg = config or DEFAULT_CONFIG
    actual_dir = Path(cfg.workspace_root) / auth_state_dir
    
    result = {
        "auth_state_dir": str(actual_dir),
        "exists": False,
        "auth_states": [],
        "total": 0,
    }
    
    if not actual_dir.exists():
        result["message"] = "登录态目录不存在"
        return result
    
    result["exists"] = True
    auth_states = []
    
    for auth_file in actual_dir.glob("*.json"):
        check_result = bnp_check_auth(
            auth_state_path=f"{auth_state_dir}/{auth_file.name}",
            config=cfg,
        )
        auth_states.append({
            "name": auth_file.stem,
            "path": f"{auth_state_dir}/{auth_file.name}",
            **check_result,
        })
    
    result["auth_states"] = auth_states
    result["total"] = len(auth_states)
    result["message"] = f"找到 {len(auth_states)} 个登录态文件"
    
    return result


def create_bnp_list_auth_states_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """
    创建列出所有登录态的工具.
    
    Returns:
        LangChain 工具实例
    """
    cfg = config or DEFAULT_CONFIG
    
    def list_auth_states(auth_state_dir: str = "playwright_scripts/auth_state") -> str:
        """
        列出所有已保存的登录态.
        
        Args:
            auth_state_dir: 登录态目录（默认 auth_state）
            
        Returns:
            JSON 格式的登录态列表
        """
        result = bnp_list_auth_states(
            auth_state_dir=auth_state_dir,
            config=cfg,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    return StructuredTool.from_function(
        name="bnp_list_auth_states",
        func=list_auth_states,
        description="""列出所有已保存的登录态。

参数：
- auth_state_dir: 登录态目录（可选，默认 auth_state）

返回 JSON 格式的登录态列表，包含每个登录态的详细信息：
- name: 登录态名称
- path: 文件路径
- valid: 是否有效
- token_expired: Token 是否过期
- time_remaining: 剩余有效时间
""",
    )
