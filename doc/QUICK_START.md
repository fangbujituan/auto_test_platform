# 快速开始指南

## 概述

本文档提供自动化测试平台（ATP）的快速入门指南，帮助你在本地开发环境中快速搭建和运行项目。

## 环境要求

- **操作系统**：Windows 10+ / macOS 10.15+ / Ubuntu 18.04+
- **Python**：3.10 或更高版本
- **Node.js**：18.x 或更高版本
- **MySQL**：8.0 或更高版本
- **Git**：2.20 或更高版本

## 后端配置

### 1. 克隆项目

```bash
git clone https://github.com/fangbujituan/auto_test_platform.git
cd auto_test_platform
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置数据库

创建 MySQL 数据库：

```sql
CREATE DATABASE business DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，修改数据库连接信息
# 主要修改以下变量：
# MYSQL_HOST=localhost
# MYSQL_PORT=3306
# MYSQL_USER=你的用户名
# MYSQL_PASSWORD=你的密码
# MYSQL_DATABASE=business
```

### 6. 启动后端服务

```bash
# 启动 Flask 开发服务器
python run.py
```

后端服务将运行在：http://localhost:12048

## 前端配置

### 1. 进入前端目录

```bash
cd client
```

### 2. 安装依赖

```bash
npm install
```

### 3. 启动前端开发服务器

```bash
npm run dev
```

前端服务将运行在：http://localhost:5173

## 数据库初始化

### 1. 初始化数据库表

在新的终端中（保持后端运行）：

```bash
python -m app.init_db
```

### 2. 初始化权限系统

```bash
python -m app.init_permission
```

## 访问系统

### 默认登录账号

- **管理员**：
  - 用户名：admin
  - 密码：admin123
  
- **测试用户**：
  - 用户名：test
  - 密码：test123

### 访问地址

1. **前端界面**：http://localhost:5173
2. **后端 API**：http://localhost:12048
3. **Swagger 文档**：http://localhost:12048/api/docs/swagger

## 常见问题

### 1. 端口冲突

如果端口被占用，可以修改：

- **后端端口**：修改 `.env` 中的 `BACKEND_PORT`
- **前端端口**：修改 `client/vite.config.js` 中的端口配置

### 2. 数据库连接失败

检查：
- MySQL 服务是否运行
- `.env` 中的数据库配置是否正确
- 数据库用户是否有权限

### 3. 依赖安装失败

尝试：
- 使用国内镜像源
- 升级 pip：`pip install --upgrade pip`
- 清除缓存：`pip cache purge`

## 下一步

完成快速启动后，建议：

1. **阅读完整文档**：[完整部署指南](COMPLETE_DEPLOYMENT_GUIDE.md)
2. **配置生产环境**：[生产环境部署指南](生产环境部署指南.md)
3. **了解项目结构**：[项目结构说明](project-structure.md)
4. **学习功能使用**：[测试用例管理](TEST_CASE_MODULE_GUIDE.md)

## 获取帮助

如遇问题无法解决，请：
1. 查看项目 README
2. 提交 Issue 到 GitHub 仓库
3. 联系项目维护者

---

**文档版本**：v1.0  
**最后更新**：2026年6月15日  
**适用环境**：开发环境