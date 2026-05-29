#!/bin/bash
# ============================================================
#   AI Agent 一键安装脚本 (Linux / macOS)
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo "============================================================"
echo "  AI Agent 一键安装脚本"
echo "============================================================"
echo ""

# ============================================================
# 1. 检查 Python
# ============================================================
echo "[1/7] 检查 Python 环境..."
if ! command -v python3 &>/dev/null; then
    fail "未检测到 Python3，请先安装 Python 3.10+"
fi
PYVER=$(python3 --version 2>&1)
ok "$PYVER"

# ============================================================
# 2. 检查 Node.js / npm
# ============================================================
echo ""
echo "[2/7] 检查 Node.js 环境..."
if ! command -v node &>/dev/null; then
    fail "未检测到 Node.js，请先安装 Node.js 18+  https://nodejs.org/"
fi
ok "Node.js $(node --version)"

if ! command -v npm &>/dev/null; then
    fail "未检测到 npm"
fi

# ============================================================
# 3. 创建 Python 虚拟环境 + 安装依赖
# ============================================================
echo ""
echo "[3/7] 配置 Python 虚拟环境..."

if [ ! -d ".venv" ]; then
    echo "   创建虚拟环境 .venv ..."
    python3 -m venv .venv
    ok "虚拟环境已创建"
else
    ok "虚拟环境已存在"
fi

echo "   激活虚拟环境..."
source .venv/bin/activate

echo "   安装 Python 依赖（requirements.txt）..."
pip install -r requirements.txt -q
ok "Python 依赖安装完成"

# 安装 Python Playwright 浏览器
echo "   安装 Playwright 浏览器（Python 版，Chromium）..."
playwright install chromium || warn "Playwright 浏览器安装失败，可稍后手动执行: playwright install chromium"

# ============================================================
# 4. 安装根目录 npm 依赖
# ============================================================
echo ""
echo "[4/7] 安装 npm 依赖（根目录）..."
npm install || warn "根目录 npm install 失败，继续..."

# 预缓存 MCP 包
echo "   预缓存 @playwright/mcp@latest ..."
npx -y @playwright/mcp@latest --help >/dev/null 2>&1 || true
ok "@playwright/mcp 已就绪"

echo "   预缓存 @antv/mcp-server-chart ..."
npx -y @antv/mcp-server-chart --help >/dev/null 2>&1 || true
ok "@antv/mcp-server-chart 已就绪"

# ============================================================
# 5. 安装 playwright_scripts 目录依赖
# ============================================================
echo ""
echo "[5/7] 安装 Playwright 测试脚本依赖..."
pushd playwright_scripts >/dev/null
npm install || warn "playwright_scripts npm install 失败，继续..."

echo "   安装 Playwright 浏览器（Chromium）..."
npx playwright install chromium || warn "Playwright 浏览器安装失败，可稍后手动执行"
popd >/dev/null
ok "Playwright 测试环境就绪"

# ============================================================
# 6. 初始化目录结构
# ============================================================
echo ""
echo "[6/7] 初始化目录结构..."
mkdir -p data
mkdir -p playwright_scripts/recordings
mkdir -p playwright_scripts/auth_state
mkdir -p playwright_scripts/test-results
mkdir -p logs
mkdir -p base64_images
mkdir -p playwright_reports
mkdir -p playwright_results
ok "目录结构就绪"

# ============================================================
# 7. 初始化环境变量
# ============================================================
echo ""
echo "[7/7] 检查环境变量配置..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "已从 .env.example 创建 .env，请编辑填写 API 密钥"
else
    ok ".env 文件已存在"
fi

# ============================================================
# 完成
# ============================================================
echo ""
echo "============================================================"
echo "  ✅ 安装完成！"
echo "============================================================"
echo ""
echo "  启动服务:"
echo "    source .venv/bin/activate"
echo "    python start_server.py"
echo ""
echo "  服务地址:"
echo "    API Server:    http://localhost:2025"
echo "    Studio UI:     http://localhost:2025/ui"
echo "    API 文档:      http://localhost:2025/docs"
echo "    Token Stats:   http://localhost:2025/api/v1/token-stats/overview"
echo "    Dashboard:     http://localhost:2025/token-stats/dashboard"
echo ""
echo "  ⚠️  首次使用请先编辑 .env 文件，配置 API 密钥"
echo "============================================================"
