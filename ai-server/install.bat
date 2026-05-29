@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo   AI Agent 一键安装脚本
echo ============================================================
echo.

:: ============================================================
:: 1. 检查 Python
:: ============================================================
echo [1/7] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.10+
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo ✅ Python %PYVER%

:: ============================================================
:: 2. 检查 Node.js / npm
:: ============================================================
echo.
echo [2/7] 检查 Node.js 环境...
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Node.js，请先安装 Node.js 18+
    echo    下载地址: https://nodejs.org/
    pause
    exit /b 1
)
for /f %%i in ('node --version 2^>^&1') do set NODEVER=%%i
echo ✅ Node.js %NODEVER%

npm --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 npm
    pause
    exit /b 1
)

:: ============================================================
:: 3. 创建 Python 虚拟环境 + 安装依赖
:: ============================================================
echo.
echo [3/7] 配置 Python 虚拟环境...

if not exist ".venv" (
    echo    创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo ✅ 虚拟环境已创建
) else (
    echo ✅ 虚拟环境已存在
)

echo    激活虚拟环境...
call .venv\Scripts\activate.bat

echo    安装 Python 依赖（requirements.txt）...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ❌ Python 依赖安装失败
    pause
    exit /b 1
)
echo ✅ Python 依赖安装完成

:: 安装 Python Playwright 浏览器
echo    安装 Playwright 浏览器（Python 版，Chromium）...
playwright install chromium
if errorlevel 1 (
    echo ⚠️  Playwright 浏览器安装失败，可稍后手动执行: playwright install chromium
)

:: ============================================================
:: 4. 安装根目录 npm 依赖
:: ============================================================
echo.
echo [4/7] 安装 npm 依赖（根目录）...
call npm install
if errorlevel 1 (
    echo ⚠️  根目录 npm install 失败，继续...
)

:: 安装 @playwright/mcp（全局 npx 可用即可，这里预缓存）
echo    预缓存 @playwright/mcp@latest ...
call npx -y @playwright/mcp@latest --help >nul 2>&1
echo ✅ @playwright/mcp 已就绪

:: 安装 @antv/mcp-server-chart
echo    预缓存 @antv/mcp-server-chart ...
call npx -y @antv/mcp-server-chart --help >nul 2>&1
echo ✅ @antv/mcp-server-chart 已就绪

:: ============================================================
:: 5. 安装 playwright_scripts 目录依赖
:: ============================================================
echo.
echo [5/7] 安装 Playwright 测试脚本依赖...
pushd playwright_scripts
call npm install
if errorlevel 1 (
    echo ⚠️  playwright_scripts npm install 失败，继续...
)
:: 安装 Playwright 浏览器
echo    安装 Playwright 浏览器（Chromium）...
call npx playwright install chromium
if errorlevel 1 (
    echo ⚠️  Playwright 浏览器安装失败，可稍后手动执行:
    echo    cd playwright_scripts ^&^& npx playwright install chromium
)
popd
echo ✅ Playwright 测试环境就绪

:: ============================================================
:: 6. 初始化目录结构
:: ============================================================
echo.
echo [6/7] 初始化目录结构...
if not exist "data" mkdir data
if not exist "playwright_scripts\recordings" mkdir playwright_scripts\recordings
if not exist "playwright_scripts\auth_state" mkdir playwright_scripts\auth_state
if not exist "playwright_scripts\test-results" mkdir playwright_scripts\test-results
if not exist "logs" mkdir logs
if not exist "base64_images" mkdir base64_images
if not exist "playwright_reports" mkdir playwright_reports
if not exist "playwright_results" mkdir playwright_results
echo ✅ 目录结构就绪

:: ============================================================
:: 7. 初始化环境变量
:: ============================================================
echo.
echo [7/7] 检查环境变量配置...
if not exist ".env" (
    copy .env.example .env >nul
    echo ✅ 已从 .env.example 创建 .env，请编辑填写 API 密钥
) else (
    echo ✅ .env 文件已存在
)

:: ============================================================
:: 完成
:: ============================================================
echo.
echo ============================================================
echo   ✅ 安装完成！
echo ============================================================
echo.
echo   启动服务:
echo     .venv\Scripts\activate
echo     python start_server.py
echo.
echo   服务地址:
echo     API Server:    http://localhost:2025
echo     Studio UI:     http://localhost:2025/ui
echo     API 文档:      http://localhost:2025/docs
echo     Token Stats:   http://localhost:2025/api/v1/token-stats/overview
echo     Dashboard:     http://localhost:2025/token-stats/dashboard
echo.
echo   ⚠️  首次使用请先编辑 .env 文件，配置 API 密钥
echo ============================================================
echo.
pause
