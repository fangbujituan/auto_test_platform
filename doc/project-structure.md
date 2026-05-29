# 自动化测试平台项目结构

## 项目概览
- 技术栈：Flask + Vue3 + MySQL
- 功能：API 自动化测试用例管理和执行

## 后端（Flask）

### app/
- Python 后端应用根目录

#### api/
- RESTful API 路由层

##### auth.py
- 用户认证接口
  - POST /api/auth/login - 用户登录
  - POST /api/auth/logout - 用户退出
  - POST /api/auth/init - 初始化测试用户

##### project.py
- 项目管理接口
  - GET /api/projects - 获取项目列表
  - POST /api/projects - 创建项目
  - PUT /api/projects/:id - 更新项目
  - DELETE /api/projects/:id - 删除项目

##### case.py
- 用例管理接口
  - GET /api/cases - 获取用例列表
  - GET /api/cases/:id - 获取单个用例
  - POST /api/cases - 创建用例
  - PUT /api/cases/:id - 更新用例
  - DELETE /api/cases/:id - 删除用例

##### execute.py
- 用例执行接口
  - POST /api/execute/case/:id - 执行单个用例
  - POST /api/execute/batch - 批量执行用例
  - POST /api/execute/project/:id - 执行项目所有用例

##### result.py
- 结果查询接口
  - GET /api/results - 获取结果列表
  - GET /api/results/:id - 获取单个结果

#### models/
- 数据模型层（ORM）

##### base.py
- 基础模型
  - BaseModel 类
    - id - 主键
    - created_at - 创建时间
    - updated_at - 更新时间

##### user.py
- 用户模型
  - username - 用户名
  - password_hash - 密码哈希
  - email - 邮箱
  - is_active - 是否激活

##### project.py
- 项目模型
  - name - 项目名称
  - description - 项目描述
  - status - 状态（1:启用 0:禁用）

##### case.py
- 测试用例模型
  - name - 用例名称
  - description - 用例描述
  - project_id - 所属项目
  - method - HTTP 方法
  - url - 请求地址
  - headers - 请求头
  - params - 查询参数
  - body - 请求体
  - expected_status - 期望状态码
  - expected_response - 期望响应
  - status - 状态
  - priority - 优先级

##### result.py
- 执行结果模型
  - case_id - 用例ID
  - status - 执行状态（passed/failed/error）
  - actual_status - 实际状态码
  - actual_response - 实际响应
  - duration - 执行耗时
  - error_message - 错误信息

#### services/
- 业务逻辑层

##### executor.py
- 用例执行器
  - TestExecutor 类
    - run_case() - 执行单个用例
    - run_cases() - 批量执行用例
    - _send_request() - 发送 HTTP 请求
    - _validate() - 验证响应
    - _match_response() - 响应匹配

#### config/
- 配置模块

##### settings.py
- 应用配置
  - Config - 基础配置
    - SECRET_KEY - 密钥
    - MYSQL_HOST - 数据库主机
    - MYSQL_PORT - 数据库端口
    - MYSQL_USER - 数据库用户
    - MYSQL_PASSWORD - 数据库密码
    - MYSQL_DATABASE - 数据库名
  - DevelopmentConfig - 开发环境配置
  - ProductionConfig - 生产环境配置

#### flask_app.py
- Flask 应用工厂
  - create_app() - 创建应用实例
  - 注册蓝图
  - 初始化扩展
  - 创建数据库表

#### init_db.py
- 数据库初始化脚本
  - 创建默认测试用户
    - admin / admin123
    - test / test123

#### requirements.txt
- Python 依赖清单
  - flask - Web 框架
  - flask-sqlalchemy - ORM
  - flask-cors - 跨域支持
  - pymysql - MySQL 驱动
  - requests - HTTP 客户端

## 前端（Vue）

### client/

#### src/

##### api/
- API 请求模块

###### request.js
- Axios 封装
  - 请求拦截器（添加 token）
  - 响应拦截器（统一错误处理）

###### auth.js
- 认证 API
  - login() - 登录
  - logout() - 退出

##### views/
- 页面组件

###### Login.vue
- 登录页面
  - 用户名密码表单
  - 表单验证
  - 登录逻辑
  - 测试账号提示

###### Welcome.vue
- 欢迎页面
  - 用户信息展示
  - 统计卡片（项目数、用例数、执行次数）
  - 退出登录
  - 快捷入口

##### router/
- 路由配置

###### index.js
- 路由定义
  - / - 重定向到登录
  - /login - 登录页
  - /welcome - 欢迎页
- 路由守卫
  - 登录验证
  - token 检查

##### App.vue
- 根组件
  - 路由视图容器
  - 全局样式

##### main.js
- 应用入口
  - 创建 Vue 实例
  - 注册 Element Plus
  - 注册路由
  - 挂载应用

#### package.json
- 前端依赖配置
  - vue - 框架
  - vue-router - 路由
  - element-plus - UI 组件库
  - axios - HTTP 客户端
  - vite - 构建工具

## 项目根目录

### run.py
- 后端启动入口
  - 创建 Flask 应用
  - 启动开发服务器（0.0.0.0:12048）

### venv/
- Python 虚拟环境
  - 隔离项目依赖

### .gitignore
- Git 忽略配置
  - __pycache__/
  - venv/
  - node_modules/
  - .env
  - *.db

### .pylintrc
- Pylint 配置
  - 禁用 import-outside-toplevel 警告

### .vscode/
- VS Code 配置

#### settings.json
- 编辑器设置
  - Python 解释器路径
  - 诊断配置

### README.md
- 项目文档
  - 项目介绍
  - 技术栈
  - 安装步骤
  - API 文档
  - 开发计划

## 数据库设计

### users
- 用户表
  - id - 主键
  - username - 用户名（唯一）
  - password_hash - 密码哈希
  - email - 邮箱
  - is_active - 是否激活
  - created_at - 创建时间
  - updated_at - 更新时间

### projects
- 项目表
  - id - 主键
  - name - 项目名称（唯一）
  - description - 项目描述
  - status - 状态
  - created_at - 创建时间
  - updated_at - 更新时间

### test_cases
- 测试用例表
  - id - 主键
  - name - 用例名称
  - description - 用例描述
  - project_id - 所属项目（外键）
  - method - HTTP 方法
  - url - 请求地址
  - headers - 请求头（JSON）
  - params - 查询参数（JSON）
  - body - 请求体（JSON）
  - expected_status - 期望状态码
  - expected_response - 期望响应（JSON）
  - status - 状态
  - priority - 优先级
  - created_at - 创建时间
  - updated_at - 更新时间

### test_results
- 执行结果表
  - id - 主键
  - case_id - 用例ID（外键）
  - status - 执行状态
  - actual_status - 实际状态码
  - actual_response - 实际响应（JSON）
  - duration - 执行耗时
  - error_message - 错误信息
  - created_at - 创建时间
  - updated_at - 更新时间

## 技术特性

### 后端特性
- RESTful API 设计
- SQLAlchemy ORM
- 密码哈希加密
- CORS 跨域支持
- 统一响应格式
- 异常处理

### 前端特性
- Vue3 Composition API
- Element Plus UI
- Axios 请求封装
- 路由守卫
- Token 认证
- 响应式布局

### 测试特性
- 动态用例管理
- HTTP 请求执行
- 响应断言验证
- 部分匹配支持
- 执行历史记录
- 批量执行

## 开发流程

### 后端开发
1. 定义数据模型（models/）
2. 编写 API 路由（api/）
3. 实现业务逻辑（services/）
4. 注册蓝图（flask_app.py）
5. 测试接口

### 前端开发
1. 创建页面组件（views/）
2. 配置路由（router/）
3. 封装 API 请求（api/）
4. 实现页面逻辑
5. 联调测试

### 部署流程
1. 配置生产环境变量
2. 构建前端静态文件
3. 配置 Nginx 反向代理
4. 启动 Flask 服务
5. 配置 HTTPS
