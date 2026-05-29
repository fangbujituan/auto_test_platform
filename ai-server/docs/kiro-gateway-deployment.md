# Kiro Gateway 部署指南

## 概述

Kiro Gateway 是一个第三方开源项目，通过读取本地 Kiro IDE 登录凭证，将 Kiro 的模型能力暴露为 OpenAI 兼容 API 和 Anthropic 兼容 API。

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    你的电脑 (本机)                           │
│                                                             │
│  ┌─────────────────┐   ┌─────────────────┐                 │
│  │  本项目          │   │  OpenClaw       │                 │
│  │  (LangGraph)    │   │  (或其他客户端)  │                 │
│  └────────┬────────┘   └────────┬────────┘                 │
│           │                     │                           │
│           │    共享同一个网关    │                           │
│           └─────────┬───────────┘                           │
│                     ▼                                       │
│           ┌─────────────────┐                               │
│           │  kiro-gateway   │                               │
│           │  localhost:9000 │                               │
│           └────────┬────────┘                               │
│                    │ 读取本地凭证                            │
│                    ▼                                        │
│           ┌─────────────────┐                               │
│           │ ~/.aws/sso/     │                               │
│           │ cache/*.json    │                               │
│           └─────────────────┘                               │
└─────────────────────────────────────────────────────────────┘
                      │
                      │ 互联网请求
                      ▼
            ┌─────────────────┐
            │  Kiro/AWS 官方  │
            │  云端 API       │
            └─────────────────┘
```

### 安全说明

| 检查项 | 结果 |
|--------|------|
| 向第三方服务器发送数据 | ❌ 无，所有请求都发往 AWS/Kiro 官方端点 |
| 凭证泄露风险 | ❌ 低，凭证只在本地处理 |
| 运行位置 | ✅ 完全在本地运行 |

⚠️ **风险提示**：
- 这是第三方开源项目，非 Kiro 官方产品
- 可能违反 Kiro/AWS 服务条款
- 使用前请自行评估风险

---

## 前提条件

1. **Kiro IDE 已安装并登录**
   - 使用企业账户登录
   - 登录后会生成凭证文件

2. **确认凭证文件存在**
   - 路径：`%USERPROFILE%\.aws\sso\cache\`
   - 文件：
     - `kiro-auth-token.json`（包含 accessToken, refreshToken）
     - `{hash}.json`（包含 clientId, clientSecret，企业账户需要）

3. **Docker 已安装**（推荐）或 Python 3.10+

---

## 部署方式

### 方式一：Docker 部署（推荐）

#### 1. 克隆仓库

```powershell
cd C:\Users\xinghua.ning\Documents\Code      # 修改成自己的实际目录
git clone https://github.com/jwadow/kiro-gateway.git
cd kiro-gateway
```

#### 2. 创建配置文件

```powershell
copy .env.example .env
```

编辑 `.env` 文件：

```env
# 凭证文件路径（容器内路径）
KIRO_CREDS_FILE=/home/kiro/.aws/sso/cache/kiro-auth-token.json

# 网关密码（自己设置，客户端需要使用相同密码）
PROXY_API_KEY=sk-12823d840d204ecdb671ede0a358cllms  #示例数据，请修改为自己的密码

# 服务器配置（容器内必须监听 0.0.0.0）
SERVER_HOST=0.0.0.0
SERVER_PORT=9000

# 可选：如果在中国需要代理
# VPN_PROXY_URL=http://127.0.0.1:7890
```

#### 3. 启动服务

**使用 Docker 命令（推荐，安全配置）：**

```powershell
docker run -d `
  -p 127.0.0.1:9000:9000 `
  -e PROXY_API_KEY="sk-12823d840d204ecdb671ede0a358cllms" `
  -e KIRO_CREDS_FILE="/home/kiro/.aws/sso/cache/kiro-auth-token.json" `
  -e SERVER_HOST=0.0.0.0 `
  -e SERVER_PORT=9000 `
  -v C:\Users\xinghua.ning\.aws\sso\cache:/home/kiro/.aws/sso/cache:ro `
  --name kiro-gateway `
  ghcr.io/jwadow/kiro-gateway:latest
```

> **安全说明**：`-p 127.0.0.1:9000:9000` 表示只绑定到本地回环地址，外部网络无法访问。

**使用 docker-compose：**

编辑 `docker-compose.yml`，确保端口配置正确：

```yaml
ports:
  - "127.0.0.1:9000:9000"
```

然后启动：

```powershell
docker-compose up -d
```

#### 4. 验证运行状态

```powershell
# 查看容器状态
docker ps

# 查看日志
docker logs kiro-gateway

# 健康检查
curl http://localhost:9000/health
```

---

### 方式二：Python 原生部署

#### 1. 克隆仓库

```powershell
cd C:\Users\xinghua.ning\Documents\Code
git clone https://github.com/jwadow/kiro-gateway.git
cd kiro-gateway
```

#### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

#### 3. 创建配置文件

```powershell
copy .env.example .env
```

编辑 `.env` 文件：

```env
# 凭证文件路径（Windows 路径）
KIRO_CREDS_FILE=C:\Users\xinghua.ning\.aws\sso\cache\kiro-auth-token.json

# 网关密码
PROXY_API_KEY=your-secret-password-here

# 只允许本地访问
SERVER_HOST=127.0.0.1

# 可选：代理
# VPN_PROXY_URL=http://127.0.0.1:7890
```

#### 4. 启动服务

```powershell
python main.py --port 9000
```

---

## 客户端配置

### 本项目（LangGraph Agent）

编辑项目的 `.env` 文件：

```env
# Kiro Gateway 配置
KIRO_BASE_URL=http://localhost:9000/v1
KIRO_API_KEY=your-secret-password-here

# 切换到 Kiro 提供商
LLM_PROVIDER=kiro
```

### OpenClaw 配置

在 OpenClaw 配置文件中添加：

```json
{
  "models": {
    "providers": {
      "kiro": {
        "baseUrl": "http://localhost:9000/v1",
        "apiKey": "your-secret-password-here",
        "api": "openai"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "kiro/claude-sonnet-4-5"
      }
    }
  }
}
```

### 其他支持 OpenAI API 的客户端

| 客户端 | 配置方式 |
|--------|----------|
| Claude Code | `ANTHROPIC_BASE_URL=http://localhost:9000` |
| Cursor | 设置 → OpenAI API Key → Base URL: `http://localhost:9000/v1` |
| Cline | 设置 OpenAI 兼容端点 |
| Continue | 配置 `apiBase` 和 `apiKey` |

---

## 可用模型

| 模型名称 | 说明 | 推荐场景 |
|----------|------|----------|
| `claude-sonnet-4-5` | 平衡性能 | 默认推荐 |
| `claude-sonnet-4-6` | 更强推理 | 复杂任务 |
| `claude-haiku-4-5` | 快速低成本 | 简单任务 |
| `claude-opus-4-5` | 最强推理 | 重要决策 |
| `deepseek-v3.2` | 低成本 | 预算有限 |
| `qwen3-coder-next` | 编码专用 | 代码任务 |
| `auto` | 自动选择 | 让系统决定 |

> 注意：模型可用性取决于你的 Kiro 订阅计划

---

## 常用命令

### Docker 部署

```powershell
# 查看状态
docker ps

# 查看日志
docker logs -f kiro-gateway

# 重启
docker restart kiro-gateway

# 停止
docker stop kiro-gateway

# 更新镜像
docker pull ghcr.io/jwadow/kiro-gateway:latest
docker stop kiro-gateway
docker rm kiro-gateway
# 重新运行 docker run 命令
```

### Python 部署

```powershell
# 启动
python main.py --port 9000

# 后台运行（Windows）
Start-Process python -ArgumentList "main.py --port 9000" -NoNewWindow

# 停止
# Ctrl+C 或找到进程终止
```

---

## 故障排查

### 1. Token 为空或过期

**现象**：凭证文件中 `accessToken` 和 `refreshToken` 为空

**解决**：
1. 打开 Kiro IDE
2. 重新登录企业账户
3. 确认凭证文件已更新

### 2. 连接失败

**现象**：客户端无法连接到 kiro-gateway

**检查**：
```powershell
# 检查服务是否运行
curl http://localhost:9000/health

# 检查端口是否被占用
netstat -ano | findstr :9000
```

### 3. 认证失败

**现象**：返回 401 Unauthorized

**检查**：
- 客户端的 `apiKey` 与 kiro-gateway 的 `PROXY_API_KEY` 是否一致

### 4. 企业账户特有问题

**现象**：企业账户（IdC）认证失败

**解决**：
- 确保两个凭证文件都存在：
  - `kiro-auth-token.json`
  - `{clientIdHash}.json`（通常是一串 hash 命名的文件）

---

## 安全建议

1. **绑定本地地址**
   - Docker: `-p 127.0.0.1:9000:9000`
   - Python: `SERVER_HOST=127.0.0.1`

2. **使用强密码**
   ```env
   PROXY_API_KEY=复杂的长密码
   ```

3. **锁定版本**
   ```powershell
   # 克隆后切换到特定版本
   git checkout v2.3
   ```

4. **定期检查更新**
   ```powershell
   git fetch
   git log HEAD..origin/main --oneline
   ```

---

## 相关链接

- [kiro-gateway GitHub](https://github.com/jwadow/kiro-gateway)
- [Kiro 官网](https://kiro.dev/)
- [Kiro 模型文档](https://kiro.dev/docs/models/)