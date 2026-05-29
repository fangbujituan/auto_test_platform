# ATP 测试平台 — 技术栈全景

> 本文档梳理项目所用的全部技术栈，方便面试讲解时快速回顾。

---

## 一、项目概述

ATP（Automated Testing Platform）是一个全栈接口自动化测试平台，涵盖项目管理、接口管理、测试用例管理、自动化执行、缺陷管理、需求管理、AI 辅助测试等功能模块。

---

## 二、前端技术栈

| 分类 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 核心框架 | Vue 3 | ^3.5 | Composition API + `<script setup>` 语法 |
| 构建工具 | Vite | ^7.2 | 开发热更新 + 生产构建 |
| UI 组件库 | Element Plus | ^2.13 | 含图标库 `@element-plus/icons-vue` |
| 路由 | Vue Router 4 | ^4.6 | `createWebHistory` 模式，路由守卫做登录拦截 |
| HTTP 请求 | Axios | ^1.13 | 封装统一请求拦截器（Token 注入、错误提示） |
| 富文本编辑器 | WangEditor 5 | ^5.1 | `@wangeditor/editor-for-vue` Vue 3 适配 |
| YAML 解析 | js-yaml | ^4.1 | 前端解析 Swagger YAML 文档 |
| 单元测试 | Vitest | ^4.1 | Vite 原生测试框架 |

### 前端架构要点

- **状态管理**：未引入 Pinia/Vuex，采用组件 props/emits + `localStorage` 管理登录态
- **主题切换**：支持 Element Plus 暗色模式（`dark/css-vars.css`）
- **路由守卫**：`beforeEach` 检查 `localStorage` 中的 token，未登录跳转 `/login`
- **API 层封装**：`src/api/request.js` 统一封装 Axios 实例，自动注入 `Authorization` 和 `X-Username` 请求头

---

## 三、后端技术栈

| 分类 | 技术 | 版本 | 说明 |
|------|------|------|------|
| Web 框架 | Flask | >=3.0 | 应用工厂模式（`create_app`） |
| ORM | SQLAlchemy 2.0 | >=2.0 | 通过 Flask-SQLAlchemy >=3.1 集成 |
| 数据库驱动 | PyMySQL | >=1.1 | MySQL 连接驱动 |
| 跨域 | Flask-CORS | >=4.0 | 全局 CORS 支持 |
| API 文档 | Flask-Smorest | >=0.44 | 自动生成 OpenAPI 3.0 文档，内置 Swagger UI / ReDoc |
| 序列化/校验 | Marshmallow | >=3.20 | Schema 定义请求/响应数据结构 |
| 加密 | cryptography (Fernet) | >=42.0 | 对称加密保护 AI API Key |
| 环境变量 | python-dotenv | >=1.0 | `.env` 文件加载配置 |
| HTTP 客户端 | Requests | >=2.31 | 接口执行引擎的核心依赖 |
| YAML 解析 | PyYAML | >=6.0 | 后端解析 Swagger YAML 文档 |
| Excel 处理 | Pandas + openpyxl | >=2.0 / >=3.1 | Excel 与数据库对比工具 |
| 定时任务 | APScheduler | >=3.10 | BackgroundScheduler 后台调度 |
| Cron 校验 | croniter | >=1.4 | 校验 Cron 表达式合法性 |
| 测试框架 | pytest | >=8.0 | 后端单元测试 |

### 后端架构要点

- **应用工厂**：`flask_app.py` 中 `create_app()` 统一初始化扩展、注册蓝图、创建表、启动调度器
- **蓝图注册**：通过 Flask-Smorest 的 `Blueprint` 组织 20+ 个 API 模块
- **权限体系**：RBAC 模型（Role-Based Access Control），4 个内置角色（admin / owner / member / viewer），装饰器 `@login_required` + `@check_project_permission` 控制访问
- **数据库迁移**：轻量级自动迁移（`auto_migrate`），通过 SQLAlchemy Inspector 检测缺失列并自动 ALTER TABLE

---

## 四、数据库 & 中间件

| 分类 | 技术 | 说明 |
|------|------|------|
| 关系型数据库 | MySQL | 主数据存储，字符集 `utf8mb4`，通过 `pymysql` 驱动连接 |
| ORM 层 | SQLAlchemy 2.0 | 声明式模型，BaseModel 统一 `id / created_at / updated_at` |
| 任务调度 | APScheduler (BackgroundScheduler) | 进程内后台调度器，支持 Cron 表达式定时触发自动化任务 |

> 项目未使用 Redis / MQ 等外部中间件，调度器和缓存均在进程内完成，部署简单。

---

## 五、接口执行引擎

项目的核心能力是接口自动化测试，执行引擎分为两层：

### 5.1 RequestFactory — HTTP 请求工厂

- 基于 `requests.Session` 封装，支持 GET / POST / PUT / DELETE / PATCH
- 支持三种请求体类型：`json` / `form` / `raw`
- 内置响应解析（自动 JSON 反序列化）、耗时统计、异常分类（Timeout / ConnectionError / Unknown）
- 提供 `validate_response()` 方法做状态码和响应体断言

### 5.2 TestExecutor — 测试用例执行器

- 调用 `requests.request()` 发送请求
- 自动对比预期状态码和预期响应体（支持部分匹配 / 递归匹配）
- 执行结果写入 `TestResult` 表，状态为 `passed / failed / error`

### 5.3 AutomationExecutor — 自动化任务执行引擎

- 按 `sort_order` 顺序执行任务关联的多个用例
- 执行前自动完成：前置 URL 解析 → 环境变量替换（`{{变量名}}`） → 全局参数合并
- 单个用例异常不中断整体执行，最终汇总 passed / failed / error 计数
- 防重复执行机制：检查是否有 `running` 状态的执行记录

### 5.4 环境变量替换

- 支持 `{{变量名}}` 占位符语法，递归替换 URL / Path / Headers / Params / Body
- 变量优先级：环境变量 > 全局变量
- 前置 URL 匹配：按 module + service 精确匹配 → 默认匹配 → 接口自带域名优先

---

## 六、自动化触发方式

| 触发方式 | 实现 | 说明 |
|----------|------|------|
| 手动执行 | API 调用 | 前端点击"执行"按钮 |
| Cron 定时 | APScheduler + CronTrigger | 支持标准 5 段 Cron 表达式，服务启动时从数据库恢复任务 |
| Webhook | Flask 路由 `/api/webhooks/<token>` | 通过唯一 Token 验证，可对接 CI/CD 流水线 |

---

## 七、AI 集成

### 支持的 AI 提供商

| 提供商 | 适配器 | 协议 |
|--------|--------|------|
| OpenAI | `OpenAIAdapter` | OpenAI `/v1/chat/completions` |
| 通义千问 (DashScope) | `DashScopeAdapter` | OpenAI 兼容格式 |
| Ollama | `OllamaAdapter` | Ollama `/api/chat` |

### AI 架构设计

- **适配器模式**：`ProviderAdapter` 抽象基类，统一 `chat()` / `chat_stream()` / `test_connection()` 接口
- **API Key 安全**：Fernet 对称加密存储，调用时内存解密，用完即清
- **提示词模板**：支持场景化模板（如测试用例生成），通过 `format_map` 替换变量
- **流式输出**：支持 SSE 流式返回 AI 回复

---

## 八、接口导入能力

| 格式 | 功能 |
|------|------|
| cURL | 解析 cURL 命令，提取 method / url / headers / body，支持 Windows CMD 格式兼容 |
| Swagger / OpenAPI | 支持 2.0 和 3.x，解析 paths 自动生成接口，按 tag 自动创建目录，支持 `$ref` 引用解析 |
| URL 远程获取 | 通过 URL 拉取远程 Swagger 文档，支持 JSON 和 YAML 格式 |

---

## 九、项目结构总览

```
├── app/                    # 后端（Flask）
│   ├── api/                # 路由层（Flask-Smorest Blueprint）
│   ├── models/             # 数据模型（SQLAlchemy）
│   ├── schemas/            # 请求/响应 Schema（Marshmallow）
│   ├── services/           # 业务逻辑层
│   │   ├── executor.py             # 测试用例执行器
│   │   ├── automation_executor.py  # 自动化任务执行引擎
│   │   ├── request_factory.py      # HTTP 请求工厂
│   │   ├── scheduler_service.py    # Cron 调度服务
│   │   ├── ai_service.py           # AI 统一调用服务
│   │   ├── ai_adapters.py          # AI 提供商适配器
│   │   └── variable_replacer.py    # 环境变量替换
│   ├── tools/              # 工具模块（Excel对比、用例生成）
│   ├── utils/              # 通用工具（加密、权限装饰器）
│   ├── config/             # 配置管理（多环境）
│   └── migrations/         # 轻量级数据迁移脚本
├── client/                 # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/            # API 请求封装
│   │   ├── components/     # 公共组件
│   │   ├── views/          # 页面视图
│   │   ├── router/         # 路由配置
│   │   └── utils/          # 工具函数
│   └── package.json
└── doc/                    # 项目文档
```

---

## 十、面试讲解要点提示

1. **前后端分离架构**：Vue 3 + Flask RESTful API，通过 Vite 代理解决开发环境跨域
2. **接口执行引擎**：基于 requests 库封装，支持多种请求体类型、响应断言、环境变量替换
3. **自动化编排**：用例按顺序执行，支持手动 / Cron / Webhook 三种触发方式
4. **RBAC 权限模型**：角色-权限多对多关系，装饰器模式实现接口级鉴权
5. **AI 集成**：适配器模式对接多家 AI 提供商，支持流式输出和提示词模板
6. **API 导入**：cURL 解析 + Swagger/OpenAPI 批量导入，降低接口录入成本
7. **API 文档自动化**：Flask-Smorest 自动生成 OpenAPI 3.0 文档，内置 Swagger UI
