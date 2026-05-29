# 权限系统快速启动指南

## 后端启动

### 1. 安装依赖
```bash
cd app
pip install -r requirements.txt
```

### 2. 启动后端服务
```bash
python run.py
```
后端将运行在 `http://localhost:12048`

### 3. 初始化权限系统
```bash
python -m app.init_permission
```

## 前端启动

### 1. 安装依赖
```bash
cd client
npm install
```

### 2. 启动前端服务
```bash
npm run dev
```
前端将运行在 `http://localhost:5173`

## 初始化系统

### 方式一：使用前端界面（推荐）

1. 访问 `http://localhost:5173/init`
2. 按步骤点击：
   - "初始化用户" → 创建 admin 和 test 用户
   - "初始化权限" → 创建角色和权限
3. 完成后点击"前往登录"

### 方式二：使用API

```bash
# 初始化用户
curl -X POST http://localhost:12048/api/auth/init

# 初始化权限
curl -X POST http://localhost:12048/api/roles/init
```

## 登录测试

### 默认账号

- **管理员账号**: admin / admin123
- **测试账号**: test / test123

### 登录步骤

1. 访问 `http://localhost:5173/login`
2. 输入用户名和密码
3. 登录成功后进入Dashboard

## 功能测试

### 1. 创建项目

1. 在Dashboard点击"项目管理"
2. 点击"新建项目"
3. 填写项目名称和描述
4. 创建成功后，你将自动成为项目负责人

### 2. 管理成员

1. 在项目列表找到你的项目
2. 点击"成员管理"（只有负责人可见）
3. 点击"添加成员"
4. 选择用户（如test）并分配角色
5. 可以修改角色或移除成员

### 3. 权限测试

1. 使用 admin 账号登录
   - 可以看到所有项目
   - 可以管理所有项目的成员

2. 使用 test 账号登录
   - 只能看到自己参与的项目
   - 根据角色有不同的操作权限

## API测试示例

### 登录
```bash
curl -X POST http://localhost:12048/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### 创建项目
```bash
curl -X POST http://localhost:12048/api/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin" \
  -d '{"name": "测试项目", "description": "这是一个测试项目"}'
```

### 获取项目列表
```bash
curl -X GET http://localhost:12048/api/projects \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin"
```

### 添加项目成员
```bash
curl -X POST http://localhost:12048/api/project-members \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin" \
  -d '{
    "project_id": 1,
    "user_id": 2,
    "role": "member"
  }'
```

## 目录结构

```
.
├── app/                          # 后端代码
│   ├── api/                      # API路由
│   │   ├── auth.py              # 认证接口
│   │   ├── project.py           # 项目接口
│   │   ├── role.py              # 角色接口
│   │   └── project_member.py   # 成员管理接口
│   ├── models/                   # 数据模型
│   │   ├── user.py              # 用户模型
│   │   ├── project.py           # 项目模型
│   │   ├── role.py              # 角色和权限模型
│   │   └── project_member.py   # 项目成员模型
│   ├── utils/                    # 工具函数
│   │   └── permission.py        # 权限装饰器
│   └── init_permission.py       # 权限初始化脚本
│
├── client/                       # 前端代码
│   ├── src/
│   │   ├── api/                 # API封装
│   │   │   ├── auth.js          # 认证API
│   │   │   ├── project.js       # 项目API
│   │   │   ├── member.js        # 成员API
│   │   │   └── role.js          # 角色API
│   │   ├── views/               # 页面组件
│   │   │   ├── Login.vue        # 登录页
│   │   │   ├── Dashboard.vue    # 仪表盘
│   │   │   ├── ProjectList.vue  # 项目列表
│   │   │   ├── ProjectMembers.vue # 成员管理
│   │   │   └── SystemInit.vue   # 系统初始化
│   │   └── router/              # 路由配置
│   │       └── index.js
│
├── PERMISSION_GUIDE.md          # 后端权限指南
├── FRONTEND_PERMISSION_GUIDE.md # 前端权限指南
└── QUICK_START.md               # 本文件
```

## 常见问题

### 1. 后端启动失败
- 检查Python版本（建议3.8+）
- 检查依赖是否安装完整
- 检查数据库配置

### 2. 前端启动失败
- 检查Node版本（建议16+）
- 删除node_modules重新安装
- 检查端口是否被占用

### 3. 登录失败
- 确认后端服务已启动
- 确认已初始化用户
- 检查浏览器控制台错误信息

### 4. 权限不生效
- 确认已初始化权限系统
- 检查用户是否有项目成员记录
- 查看后端日志

### 5. 跨域问题
- 后端已配置CORS
- 检查前端API baseURL配置
- 确认端口号正确

## 下一步

- 查看 [PERMISSION_GUIDE.md](./PERMISSION_GUIDE.md) 了解后端权限详情
- 查看 [FRONTEND_PERMISSION_GUIDE.md](./FRONTEND_PERMISSION_GUIDE.md) 了解前端实现
- 开始开发用例管理、执行记录等功能

## 部署到生产环境

### 使用 Gunicorn 部署

#### 1. 安装 Gunicorn

在服务器上安装 Gunicorn（添加到 requirements.txt）：

```bash
pip install gunicorn
```

#### 2. Gunicorn 基本命令

你的项目启动入口是 `run.py` 中的 `app` 对象：

```bash
# 开发环境测试（4个工作进程，绑定到127.0.0.1:12048）
gunicorn -w 4 -b 127.0.0.1:12048 run:app
```

**参数说明：**
- `-w 4`: 4个工作进程（建议 CPU 核心数 × 2 + 1）
- `-b 127.0.0.1:12048`: 绑定地址和端口（开发环境可直接对外）
- `run:app`: 指定应用入口（模块:应用实例）

> **注意**：生产环境推荐配合 Nginx 反向代理，Gunicorn 绑定到 `127.0.0.1`（仅本地访问），Nginx 对外监听 80/443 端口。

#### 3. 生产环境推荐配置

```bash
gunicorn \
  -w 4 \
  -k gevent \
  -b 127.0.0.1:12048 \
  --timeout 120 \
  --access-logfile /var/log/gunicorn/access.log \
  --error-logfile /var/log/gunicorn/error.log \
  --daemon \
  run:app
```

**参数说明：**
- `-b 127.0.0.1:12048`: 绑定到本地回环（配合 Nginx 反向代理）
- `-k gevent`: 使用 gevent 协程（适合 I/O 密集型 API）
- `--timeout 120`: 请求超时时间（秒）
- `--daemon`: 后台运行
- `--access-logfile` / `--error-logfile`: 日志文件路径

#### 4. 使用配置文件（推荐）

在项目根目录创建 `gunicorn.conf.py`：

```python
# gunicorn.conf.py
import multiprocessing

# 绑定地址和端口（生产环境推荐 127.0.0.1，配合 Nginx 反向代理）
bind = "127.0.0.1:12048"

# 工作进程数（CPU核心数 × 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1

# 使用 gevent 协程
worker_class = "gevent"

# 超时时间（秒）
timeout = 120

# 日志配置
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# 后台运行
daemon = True

# 限制请求体大小（100MB）
limit_request_field_size = 104857600
limit_request_line = 204800

# 预加载应用（节省内存）
preload_app = True

# 优雅重启
graceful_timeout = 30
```

**启动命令：**

```bash
gunicorn -c gunicorn.conf.py run:app
```

#### 5. 配合 Nginx 反向代理（生产环境推荐）

Nginx 配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:12048;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 120;
        proxy_send_timeout 120;
        proxy_read_timeout 120;
    }
}
```

#### 6. 重要注意事项

**环境变量：**
确保服务器上设置了正确的环境变量（特别是 `.env` 文件）：

```bash
# 在启动 Gunicorn 前加载环境变量
export FLASK_ENV=production
export DATABASE_URL="mysql+pymysql://user:password@host:3306/dbname"
export SECRET_KEY="your-secret-key"

gunicorn -w 4 -b 127.0.0.1:12048 run:app
```

**数据库迁移：**
部署前先执行数据库迁移：

```bash
python app/init_db.py
```

**静态文件：**
你的项目使用 Swagger UI，确保 `app/flask_app.py` 中的 `OPENAPI_SWAGGER_UI_URL` 等配置在生产环境可访问。

**生产环境配置要点：**
1. Gunicorn 绑定到 `127.0.0.1`（仅本地访问）
2. Nginx 对外监听 80/443 端口
3. Nginx 通过 `proxy_pass http://127.0.0.1:12048` 转发请求
4. 这样配置更安全，Nginx 可以处理 SSL、压缩、缓存等

#### 7. 常见问题

**Q: 启动时报错 "No module named 'app'"**
A: 确保在项目根目录下运行，或者将 `app` 目录加入 Python 路径：

```bash
PYTHONPATH=. gunicorn -w 4 -b 127.0.0.1:12048 run:app
```

**Q: 需要热重载开发模式？**
A: 使用 `--reload` 参数（仅开发环境）：

```bash
gunicorn -w 1 --reload -b 127.0.0.1:12048 run:app
```

**Q: 如何优雅重启？**
A: 发送 HUP 信号给 Gunicorn 主进程：

```bash
kill -HUP <gunicorn_master_pid>
```

**Q: 如何停止 Gunicorn？**
A: 发送 TERM 信号：

```bash
kill -TERM <gunicorn_master_pid>
```

或者使用 `pkill gunicorn`（会停止所有 Gunicorn 进程）。

#### 8. 完整部署脚本示例

创建 `deploy.sh`：

```bash
#!/bin/bash

# 项目路径
PROJECT_DIR="/path/to/unis_auto_platform"
LOG_DIR="/var/log/gunicorn"

# 创建日志目录
mkdir -p $LOG_DIR

# 进入项目目录
cd $PROJECT_DIR

# 激活虚拟环境（如果有）
# source venv/bin/activate

# 安装依赖
pip install -r app/requirements.txt

# 运行数据库迁移
python app/init_db.py

# 停止旧的 Gunicorn 进程
pkill -f gunicorn

# 启动新的 Gunicorn（生产环境推荐配合 Nginx）
gunicorn -c gunicorn.conf.py run:app

echo "Deployment completed successfully!"
```

#### 9. systemd 服务管理（推荐）

创建 systemd 服务文件 `/etc/systemd/system/gunicorn.service`：

```ini
[Unit]
Description=Gunicorn instance to serve unis_auto_platform
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/unis_auto_platform
Environment="PATH=/path/to/unis_auto_platform/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/path/to/unis_auto_platform/venv/bin/gunicorn \
    --workers 4 \
    --worker-class gevent \
    --bind 127.0.0.1:12048 \
    --timeout 120 \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log \
    run:app

[Install]
WantedBy=multi-user.target
```

**使用方法：**

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start gunicorn

# 设置开机自启
sudo systemctl enable gunicorn

# 查看状态
sudo systemctl status gunicorn

# 重启服务
sudo systemctl restart gunicorn

# 查看日志
sudo journalctl -u gunicorn -f
```

## 下一步

- 查看 [PERMISSION_GUIDE.md](./PERMISSION_GUIDE.md) 了解后端权限详情
- 查看 [FRONTEND_PERMISSION_GUIDE.md](./FRONTEND_PERMISSION_GUIDE.md) 了解前端实现
- 开始开发用例管理、执行记录等功能
- 部署到生产环境前，确保：
  - 修改 `.env` 中的 `SECRET_KEY`
  - 配置生产环境数据库连接
  - 设置 `FLASK_ENV=production`
  - 配置 Nginx 反向代理
  - 设置 systemd 服务管理