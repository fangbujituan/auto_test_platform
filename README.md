# 自动化测试平台 (ATP)

基于 Flask + Vue 的 API 自动化测试平台，支持接口管理、测试用例、Bug 跟踪、用例执行和结果分析。

## 系统架构与规划

### 总体定位

本平台是一个 **AI 驱动的自动化测试平台**。前后端代码同仓库管理但运行时相互独立，通过 Git 同步到服务器后基于 Docker 分别部署（`flask-app`、`nginx-frontend`、`mysql-db` 各自独立容器，通过内部网络通信）。

目标形态：用户在页面的对话框中描述测试意图，平台即可**自动生成测试用例与可执行脚本**，覆盖三类测试：

- **UI 测试** — UI 用例 + 脚本（Web 端，对应 `app/engine/ui_engine`）
- **API 测试** — API 用例 + 脚本（接口端，对应 `app/engine/api_engine`）
- **性能测试** — 性能用例 + 脚本（压测，对应 `app/engine/perf_engine`）

> App 端自动化（`app/engine/app_engine`）作为后续扩展方向预留。

### 执行引擎（app/engine）

引擎层按测试类型拆分为独立子引擎，统一负责"用例 → 脚本 → 执行 → 报告"的闭环：

| 子引擎 | 目录 | 职责 |
|--------|------|------|
| API 引擎 | `api_engine` | 接口用例执行、请求组装、断言、报告（现有流水线模块逐步归并至此） |
| UI 引擎 | `ui_engine` | Web UI 用例执行（Selenium / Playwright 方向） |
| App 引擎 | `app_engine` | 移动 App 用例执行（Appium 方向，预留） |
| 性能引擎 | `perf_engine` | 性能/压测执行与指标采集（Locust / JMeter 方向） |

### AI 与 Agent 协作（app/agents）

- 平台通过 **MCP（Model Context Protocol）** 对外暴露能力，供 AI 客户端调用以驱动测试用例生成与执行。
- `app/agents` 存放基于 **LangGraph** 构建的多 Agent，编排"理解需求 → 生成用例 → 生成脚本 → 调用引擎执行 → 汇总结果"的多步骤工作流。

**待定：Agent 的部署形态**

多 Agent 协作的承载方式尚未最终确定，目前有两个候选方案，后续验证后再定：

1. **随后端打包进 Docker** — Agent 作为后端进程的一部分，随 `flask-app` 容器部署。优点是部署简单、与现有引擎同进程调用方便；缺点是耦合度高、横向扩展受限。
2. **独立注册表 / 服务** — Agent 作为独立可注册的服务（注册表模式），按需被发现和调用。优点是解耦、便于独立扩缩容与复用；缺点是需要额外的服务发现与通信机制。

> 此项为开放决策点，待执行引擎补全后结合实际负载再评估。

## 📚 文档

详细的技术文档和指南请查看 [doc 目录](doc/INDEX.md)。

### 快速链接
- [快速开始指南](doc/QUICK_START.md)
- [完整部署指南](doc/COMPLETE_DEPLOYMENT_GUIDE.md)
- [项目结构说明](doc/project-structure.md)
- [Bug 管理模块](doc/BUG_MODULE_GUIDE.md)
- [测试用例管理](doc/TEST_CASE_MODULE_GUIDE.md)
- [API 测试指南](doc/API_TEST_GUIDE.md)
- [权限管理指南](doc/PERMISSION_GUIDE.md)
- [SaaS 私有化部署方案](doc/SAAS_PRIVATIZATION_DESIGN.md)
- [SAP 架构分析](doc/SAP_ARCHITECTURE_ANALYSIS.md)

## 项目结构

```
unis_auto_platform/
├── app/                      # 后端（Flask）
│   ├── flask_app.py          # Flask 应用工厂
│   ├── requirements.txt      # Python 依赖
│   ├── config/               # 配置模块
│   │   └── settings.py       # 数据库连接、环境配置
│   ├── models/               # 数据模型（ORM）
│   │   ├── base.py           # 基础模型（公共字段）
│   │   ├── user.py           # 用户模型
│   │   ├── project.py        # 项目模型
│   │   ├── project_member.py # 项目成员模型
│   │   ├── role.py           # 角色与权限模型
│   │   ├── api.py            # API 接口模型
│   │   ├── api_folder.py     # API 目录模型
│   │   ├── case.py           # API 测试用例模型
│   │   ├── test_case.py      # 测试用例管理模型
│   │   ├── bug.py            # Bug 模型
│   │   ├── sprint.py         # 冲刺（Sprint）模型
│   │   ├── requirement.py    # 需求模型与状态枚举
│   │   ├── tag.py            # 标签模型与需求-标签关联表
│   │   ├── operation_log.py  # 操作日志模型
│   │   ├── module.py         # 模块模型（树形结构）
│   │   ├── result.py         # 执行结果模型
│   │   ├── env_variable.py   # 环境变量模型
│   │   ├── ai_provider.py    # AI 提供商配置模型
│   │   └── ai_prompt.py      # AI 提示词模板模型
│   ├── routes/               # RESTful API 路由（全部基于 flask-smorest MethodView）
│   │   ├── auth.py           # 认证接口
│   │   ├── project.py        # 项目管理接口
│   │   ├── project_member.py # 项目成员接口
│   │   ├── role.py           # 角色管理接口
│   │   ├── api.py            # API 接口管理
│   │   ├── api_folder.py     # API 目录管理
│   │   ├── api_import.py     # API 导入（cURL / Swagger）
│   │   ├── case.py           # 用例管理接口
│   │   ├── test_case.py      # 测试用例管理接口
│   │   ├── bug.py            # Bug 管理接口
│   │   ├── sprint.py         # 冲刺管理接口
│   │   ├── requirement.py    # 需求管理、标签管理、操作日志接口
│   │   ├── execute.py        # 用例执行接口
│   │   ├── result.py         # 结果查询接口
│   │   ├── toolbox.py        # 工具箱接口
│   │   ├── dashboard.py      # 仪表盘接口
│   │   ├── env_variable.py   # 环境变量管理接口
│   │   ├── ai_provider.py    # AI 提供商配置接口
│   │   ├── ai_chat.py        # AI 对话接口（同步 + SSE 流式）
│   │   └── ai_prompt.py      # AI 提示词模板接口
│   ├── schemas/              # Marshmallow Schema（请求/响应定义）
│   │   ├── auth.py           # 认证相关 Schema
│   │   ├── project.py        # 项目相关 Schema
│   │   ├── member.py         # 项目成员 Schema
│   │   ├── common.py         # 通用 Schema
│   │   ├── case.py           # 用例 Schema
│   │   ├── execute.py        # 执行 Schema
│   │   ├── result.py         # 结果 Schema
│   │   ├── api_mgmt.py       # API 接口管理 Schema
│   │   ├── api_import.py     # API 导入 Schema（cURL / Swagger）
│   │   ├── bug.py            # Bug 管理 Schema
│   │   ├── requirement.py    # 需求/冲刺/标签/操作日志 Schema
│   │   ├── env_variable.py   # 环境变量 Schema
│   │   ├── ai.py             # AI 提供商/对话/提示词 Schema
│   │   └── test_case_mgmt.py # 测试用例管理 Schema
│   ├── services/             # 业务逻辑层
│   │   ├── executor.py       # 用例执行器
│   │   ├── request_factory.py # 请求构造器
│   │   ├── variable_replacer.py # 环境变量替换服务
│   │   ├── ai_service.py     # 统一 AI 调用服务
│   │   └── ai_adapters.py    # AI 提供商适配器（OpenAI / DashScope / Ollama）
│   ├── engine/               # 执行引擎（按测试类型拆分子引擎）
│   │   ├── api_engine/       # 接口自动化引擎（api-engine）
│   │   ├── ui_engine/        # Web UI 自动化引擎（UI-engine）
│   │   ├── app_engine/       # 移动 App 自动化引擎（app-engine，预留）
│   │   └── perf_engine/      # 性能/压测引擎（性能引擎）
│   ├── agents/               # 基于 LangGraph 的多 Agent 协作
│   ├── tools/                # 工具模块
│   │   ├── toolbox/          # 工具箱（测试用例生成器等）
│   │   └── tool_excel_db/    # Excel-DB 对比工具
│   └── utils/                # 工具函数
│       ├── permission.py     # 权限装饰器
│       └── crypto.py         # API Key 加解密工具
├── client/                   # 前端（Vue 3）
│   ├── src/
│   │   ├── api/              # API 请求层
│   │   ├── components/       # 公共组件
│   │   ├── views/            # 页面视图
│   │   ├── router/           # 路由配置
│   │   └── main.js           # 入口文件
│   └── vite.config.js        # Vite 配置
├── doc/                      # 项目文档
├── run.py                    # 后端启动入口
└── README.md
```

## 数据库设计

| 表名 | 说明 |
|------|------|
| users | 用户表（登录认证） |
| projects | 项目表（组织管理） |
| project_members | 项目成员表（用户-项目-角色关联） |
| roles | 角色表（admin/owner/member/viewer） |
| permissions | 权限表（resource:action） |
| role_permissions | 角色权限关联表 |
| apis | API 接口表（请求配置） |
| api_folders | API 目录表（树形结构） |
| test_cases | API 测试用例表（HTTP 请求、断言规则） |
| test_case_management | 测试用例管理表（功能用例） |
| test_case_api_bindings | 用例-接口绑定表 |
| bugs | Bug 表（缺陷跟踪） |
| modules | 模块表（树形结构） |
| sprints | 冲刺表（敏捷迭代管理） |
| requirements | 需求表（需求管理） |
| tags | 标签表 |
| requirement_tags | 需求-标签关联表 |
| operation_logs | 操作日志表 |
| test_results | 执行结果表（状态、响应、耗时） |
| environment_variables | 环境变量表（项目级变量管理） |
| ai_provider_configs | AI 提供商配置表（API Key 加密存储） |
| ai_prompt_templates | AI 提示词模板表（场景化提示词） |

## 本地项目初始化

### 后端初始化

```bash
# 克隆项目
git clone https://github.com/fangbujituan/unis_auto_platform.git
cd unis_auto_platform

# 创建并激活虚拟环境
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

创建数据库：

```sql
CREATE DATABASE business DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

配置环境变量（复制模板并修改）：

```bash
cp .env.example .env
# 修改 .env 中的数据库连接信息
```

`.env` 文件示例：
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=business
SECRET_KEY=dev-secret-key
AI_ENCRYPTION_KEY=your-fernet-key
```

启动后端服务：

```bash
# 启动服务（自动创建表）
python run.py

# 初始化用户和权限
python app/init_db.py
python -m app.init_permission
```

后端运行在 http://localhost:12048

### 前端初始化

```bash
cd client
npm install
npm run dev
```

前端运行在 http://localhost:5173

### 默认账号

| 用户名 | 密码 | 说明 |
|--------|------|------|
| admin | admin123 | 管理员 |
| test | test123 | 测试用户 |

## Swagger 接口文档

项目集成了 flask-smorest，自动生成 OpenAPI 3.0 规范的接口文档。启动后端服务后访问：

| 地址 | 说明 |
|------|------|
| http://localhost:12048/api/docs/swagger | Swagger UI（交互式文档，可直接调试接口） |
| http://localhost:12048/api/docs/redoc | ReDoc（阅读友好的文档） |
| http://localhost:12048/api/docs/openapi.json | OpenAPI JSON（可导入 Postman 等工具） |

所有 API 模块已全部迁移至 flask-smorest MethodView 模式，接口自动出现在 Swagger 文档中：
- 认证（auth）、项目（project）、项目成员（project_member）
- 角色（role）、API 接口（api）、API 目录（api_folder）
- 用例（case）、测试用例管理（test_case）、Bug（bug）
- 冲刺（sprint）、需求（requirement）、标签（tag）、操作日志（operation_log）
- 执行（execute）、结果（result）、工具箱（toolbox）、仪表盘（dashboard）
- API 导入（api_import）、环境变量（env_variable）
- AI 提供商（ai_provider）、AI 对话（ai_chat）、AI 提示词（ai_prompt）

> 完整接口列表请以 Swagger / ReDoc 在线文档为准，不再在此手动维护。

## 技术栈

### 后端
- Python 3.10+
- Flask 3.x — Web 框架
- Flask-SQLAlchemy — ORM
- Flask-Smorest — OpenAPI/Swagger 文档生成
- Marshmallow — 请求/响应 Schema 定义与校验
- Flask-CORS — 跨域支持
- PyMySQL — MySQL 驱动
- SQLAlchemy — SQL 工具包（Excel-DB 对比等场景直接使用）
- Cryptography — API Key 加密存储
- Requests — HTTP 客户端（AI 适配器、用例执行）
- Pandas + Openpyxl — Excel 数据处理
- python-dotenv — 环境变量加载
- Werkzeug — 密码哈希
- pytest — 单元测试

### 前端
- Vue 3 + Vite
- Element Plus — UI 组件库
- Axios — HTTP 客户端
- Vue Router — 路由管理
- WangEditor — 富文本编辑器

## 权限模型

采用 RBAC（基于角色的访问控制），分为项目级权限：

| 角色 | 说明 | 权限范围 |
|------|------|---------|
| admin | 平台管理员 | 所有权限 |
| owner | 项目负责人 | 项目内所有权限 |
| member | 项目成员 | 读写权限，不能删除项目和管理成员 |
| viewer | 只读用户 | 只能查看 |

## 功能模块

- 接口管理 — API 接口的增删改查、目录组织、在线测试
- API 导入 — 支持 cURL 命令和 Swagger/OpenAPI JSON 导入接口
- 测试用例 — 功能用例管理、用例-接口绑定
- Bug 管理 — 缺陷跟踪、状态流转、优先级/严重程度
- 需求管理 — 敏捷需求管理、冲刺迭代、标签分类、状态流转
- 用例执行 — 单个/批量/按项目执行，结果记录
- 环境变量 — 项目级变量管理，请求中 {{变量名}} 自动替换
- 仪表盘 — 项目统计、执行概览
- 工具箱 — 测试用例自动生成等辅助工具
- AI 助手 — 多提供商（OpenAI / 通义千问 / Ollama）对话、流式输出、提示词模板管理
- 权限管理 — RBAC 角色权限、项目成员管理
- 操作日志 — 用户操作行为记录与审计

## Docker 部署（生产环境）

### 前置条件

- Ubuntu 服务器已安装 Docker 和 Docker Compose 插件
- 服务器已安装 Git

### 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/fangbujituan/unis_auto_platform.git
cd unis_auto_platform

# 2. 创建环境变量文件
cp .env.example .env

# 3. 修改 .env 中的配置（密码、密钥等）
vim .env
# 重点修改：
#   MYSQL_PASSWORD — 数据库密码
#   SECRET_KEY — Flask 密钥
#   AI_ENCRYPTION_KEY — AI 模块加密密钥
#   MYSQL_HOST=mysql-db（Docker 内部网络，不要改）

# 4. 构建并启动所有服务
docker compose up -d --build

# 5. 查看容器状态（确保全部 healthy）
docker compose ps

# 6. 初始化数据库数据（首次部署执行）
docker compose exec flask-app python -m app.init_db
docker compose exec flask-app python -m app.init_permission
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://服务器IP:1801 |
| 后端 API | http://服务器IP:12048 |
| Swagger 文档 | http://服务器IP:12048/api/docs/swagger |

### 日常运维

```bash
# 查看日志
docker compose logs -f flask-app
## 方式1：在宿主机直接查看（推荐）
# 查看日志文件
tail -f /opt/vplatform/unis_auto_platform/logs/info.log
# 查看最近100行
tail -100 /opt/vplatform/unis_auto_platform/logs/info.log

## 方式2：进入容器查看
# 进入容器
docker exec -it flask-app bash
# 查看日志
tail -f /app/logs/info.log

## 方式3：不进入容器直接查看
docker exec flask-app tail -f /app/logs/info.log


# 重启服务
docker compose restart flask-app

# 更新代码后重新部署
git pull
docker compose up -d --build

# 停止所有服务
docker compose down

# 停止并删除数据卷（慎用，会清除数据库数据）
docker compose down -v

# 重启
docker compose up -d

# 验证 Flask 时区
docker compose exec flask-app python -c "from datetime import datetime; print(datetime.now())"

# 验证 MySQL 时区
docker compose exec mysql-db mysql -uroot -p你的密码 -e "SELECT NOW();"
```

## 常见问题

### 端口被占用
```cmd
netstat -ano | findstr :12048
taskkill /F /PID <进程ID>
```

### 数据库连接失败
- 检查 MySQL 服务是否启动
- 确认数据库 `business` 已创建
- 验证 `app/config/settings.py` 中的连接信息

### 登录失败
- 确保已运行 `python app/init_db.py` 初始化用户数据
- 确保已运行 `python -m app.init_permission` 初始化权限

## 开发计划

- [x] 用户登录认证
- [x] 项目管理（CRUD + 成员管理）
- [x] RBAC 权限系统
- [x] API 接口管理（目录树 + 在线测试）
- [x] 测试用例管理
- [x] Bug 管理
- [x] 用例执行与结果记录
- [x] 仪表盘统计
- [x] 工具箱（用例生成器）
- [x] Swagger 接口文档（flask-smorest）
- [x] 全部 API 模块迁移至 flask-smorest
- [x] 需求管理（冲刺、需求、标签、操作日志）
- [x] Swagger/OpenAPI 文件导入
- [x] cURL 命令导入
- [x] 环境变量管理（{{变量名}} 占位符替换）
- [x] AI 助手（多提供商适配、同步/流式对话、提示词模板）
- [ ] 质量数据统计（大数据看板）
  - [ ] 测试执行统计 — 通过率/失败率趋势图、按项目/模块维度统计、执行耗时分布
  - [ ] Bug 质量分析 — Bug 状态分布（饼图）、严重程度/优先级分布、Bug 趋势（新增 vs 关闭）、Bug 平均修复时长、按模块/版本的缺陷密度
  - [ ] 用例覆盖度 — 接口覆盖率（已绑定用例的接口占比）、用例优先级分布、用例状态分布（草稿/已评审/已废弃）
  - [ ] 需求质量追踪 — 需求状态流转统计、需求关联用例/Bug 数量、冲刺燃尽图、冲刺完成率对比
  - [ ] 项目质量总览 — 多项目质量评分对比、项目健康度雷达图（用例覆盖率、Bug 收敛率、执行通过率、需求完成率）
  - [ ] 团队效能统计 — 成员 Bug 提交/解决排行、成员用例执行量统计
  - [ ] 数据导出 — 质量报告 PDF/Excel 导出、自定义时间范围筛选
- [ ] 智能测试用例生成（AI 驱动）
- [ ] 执行引擎增强与补全
  - [ ] API 引擎（api_engine）能力补全
  - [ ] UI 引擎（ui_engine）—— UI 用例 + 脚本自动生成与执行
  - [ ] 性能引擎（perf_engine）—— 性能用例 + 脚本自动生成与执行
  - [ ] App 引擎（app_engine，预留）
- [ ] 页面对话框驱动的用例 + 脚本自动生成（UI / API / 性能）
- [ ] MCP 能力暴露（供 AI 客户端调用执行测试）
- [ ] LangGraph 多 Agent 协作（app/agents）
  - [ ] 确定 Agent 部署形态（随后端 Docker 打包 vs 独立注册表/服务）
- [ ] 定时任务支持
- [ ] 测试报告导出

## Git 版本管理

### 首次推送到 GitHub

1. **初始化本地仓库**：
```bash
git init
git add .
git commit -m "Initial commit: Flask + Vue automation test platform"
```

2. **关联远程仓库**：
```bash
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
```

3. **推送到远程**：
```bash
git push -u origin main
```

### 日常开发提交

```bash
# 查看修改状态
git status

# 添加修改文件
git add .

# 提交修改
git commit -m "描述本次修改内容"

# 推送到远程
git push
```

### 拉取远程更新

```bash
git pull origin main
```