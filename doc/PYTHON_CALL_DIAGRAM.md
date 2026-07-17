# ATP 自动化测试平台 - Python 文件调用逻辑图

## 📋 文档说明

本文档描绘了 ATP 平台的 Python 代码调用流程，分为三个核心部分：
1. **Flask 后端启动流程**
2. **核心业务层调用关系**
3. **Code Factory (Agent编排系统) 初始化流程**

---

## 1. 🚀 Flask 后端启动流程

### 入口点

```
run.py
 └─→ app/flask_app.py::create_app()
     └─→ Flask应用初始化与蓝图注册
```

### 详细启动序列

```
run.py (应用程序启动入口)
│
├─→ from app.flask_app import create_app
│
└─→ create_app(config_name=None)  [app/flask_app.py]
    │
    ├─→ os.getenv("FLASK_ENV") or "development"
    │
    ├─→ Flask(__name__)
    │
    ├─→ app.config.from_object(config[config_name])  [app/config/settings.py]
    │
    ├─→ db.init_app(app)  [app/models/base.py]
    │
    ├─→ CORS(app)  [flask_cors]
    │
    ├─→ Api(app)  [flask_smorest]
    │
    ├─→ _register_request_logging(app)
    │   └─→ 注册 before_request / after_request 钩子
    │
    ├─→ _register_json_charset(app)
    │   └─→ 强制 JSON 响应字符集为 UTF-8
    │
    ├─→ 注册所有 flask-smorest 蓝图
    │   ├─→ from app.routes.auth import auth_blp
    │   ├─→ from app.routes.project import project_blp
    │   ├─→ from app.routes.api import api_blp
    │   ├─→ from app.routes.case import case_blp
    │   ├─→ from app.routes.execute import execute_blp
    │   ├─→ from app.routes.ai_chat import ai_chat_blp
    │   ├─→ from app.routes.agent_workflow import agent_workflow_blp
    │   ├─→ ... (共19个蓝图)
    │   └─→ api.register_blueprint(各蓝图)
    │
    ├─→ db.create_all()  [自动创建数据表]
    │
    └─→ SchedulerService().init_app(app)  [app/services/scheduler_service.py]
        └─→ 初始化定时任务调度器
```

---

## 2. 📦 核心业务层调用关系

### 分层架构

```
┌────────────────���────────────────────────────────────────────┐
│                      Flask Routes (路由层)                   │
│  auth.py / project.py / api.py / execute.py / ai_chat.py .. │
└────────────────────┬────────────────────────────────────────┘
                     │ Request/Response
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Marshmallow Schemas (校验层)                │
│  schemas/auth.py / schemas/case.py / schemas/execute.py ..  │
└────────────────────┬────────────────────────────────────────┘
                     │ Validated Data
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Services (业务逻辑层)                       │
│  executor.py / request_factory.py / ai_service.py           │
│  variable_replacer.py / ai_adapters.py                      │
└────────────────────┬────────────────────────────────────────┘
                     │ Business Logic
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     Engine (执行引擎层)                       │
│  engine/api_engine/ / engine/ui_engine/                     │
│  engine/perf_engine/ (规划中)                               │
└────────────────────┬────────────────────────────────────────┘
                     │ Execution
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Models (ORM数据模型)                        │
│  models/user.py / models/api.py / models/case.py            │
│  models/result.py / models/operation_log.py ..              │
└────────────────────┬────────────────────────────────────────┘
                     │ Persistence
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Database (MySQL数据库)                       │
│  users / projects / apis / test_cases / test_results ..     │
└─────────────────────────────────────────────────────────────┘
```

### 典型业务流 - 用例执行流程

```
Request: POST /api/v1/execute/run_case
    │
    └─→ app/routes/execute.py::ExecuteApi::post()
        │
        ├─→ 从 request 获取参数，通过 ExecuteSchema 校验
        │
        ├─→ app/services/executor.py::Executor::execute_case()
        │   │
        │   ├─→ app/services/variable_replacer.py::replace_variables()
        │   │   └─→ 替换 {{变量名}} 为环境变量值
        │   │
        │   ├─→ app/services/request_factory.py::RequestFactory::build()
        │   │   └─→ 根据测试用例配置构造 HTTP 请求
        │   │
        │   ├─→ app/engine/api_engine/api_executor.py
        │   │   │
        │   │   ├─→ 发送 HTTP 请求 (requests库)
        │   │   │
        │   │   ├─→ app/engine/api_engine/assertion/assertion_handler.py
        │   │   │   └─→ 执行断言 (json_subset / json_path_eq / status_code 等)
        │   │   │
        │   │   ├─→ app/engine/api_engine/extractor/extractor_handler.py
        │   │   │   └─→ 抽取响应字段供链式调用
        │   │   │
        │   │   └─→ 生成执行结果
        │   │
        │   └─→ app/models/result.py::TestResult::create()
        │       └─→ 持久化到 test_results 表
        │
        └─→ 返回 Response { status, result, duration, .. }
```

### AI 助手业务流

```
Request: POST /api/v1/ai/chat (流式对话)
    │
    └─→ app/routes/ai_chat.py::AIChatApi::post()
        │
        ├─→ 从 request 获取 message / model / provider
        │
        ├─→ app/services/ai_service.py::AIService::stream_chat()
        │   │
        │   ├─→ app/services/ai_adapters.py::get_adapter()
        │   │   ├─→ OpenAIAdapter (OpenAI API)
        │   │   ├─→ DashScopeAdapter (阿里通义千问)
        │   │   └─→ OllamaAdapter (本地模型)
        │   │
        │   ├─→ adapter.stream_chat(messages, model, temperature, max_tokens)
        │   │   │
        │   │   ├─→ 调用第三方 LLM API
        │   │   │
        │   │   └─→ yield 流式响应块
        │   │
        │   └─→ 更新 Token 统计 (TokenCounter)
        │
        ├─→ 使用 Flask SSE (Server-Sent Events) 流式返回
        │
        └─→ 前端 JavaScript 解析 SSE 流并实时显示
```

---

## 3. 🤖 Code Factory - Agent 编排系统

### 应用启动流程

```
code-factory/src/main.py::create_app()
    │
    ├─→ load_config_or_exit()
    │   └─→ code-factory/src/core/config.py::load_config_or_exit()
    │       ├─→ 从 config/ 目录加载 YAML 配置
    │       ├─→ 验证必须参数 (DB_HOST, DB_PASSWORD 等)
    │       └─→ 失败时 sys.exit(1)
    │
    ├─→ configure_logging()
    │   └─→ 初始化 structlog 结构化日志
    │
    ├─→ install_exception_hook()
    │   └─→ 安装全局异常捕获钩子
    │
    ├─→ _create_db_pool()
    │   └─→ asyncpg 创建 PostgreSQL 连接池
    │
    ├─→ _test_db_connection()
    │   └─→ 测试数据库连接性，失败退出
    │
    ├─→ _initialize_model_router()
    │   └─→ code-factory/tools/model_router.py::LiteLLMModelRouter()
    │       └─→ 初始化模型路由规则 (routing_rules.yaml)
    │
    ├─→ _initialize_vector_store()
    │   └─→ code-factory/rag/vector_store.py::PGVectorStore()
    │       └─→ 使用 PostgreSQL + PGVector 扩展
    │
    ├─→ _initialize_index_manager()
    │   └─→ code-factory/rag/index_manager.py::IndexManager()
    │       └─→ 管理向量索引增量更新
    │
    ├─→ _initialize_rag_pipeline()
    │   └─→ code-factory/rag/pipeline.py::RAGPipeline()
    │       │
    │       ├─→ 文档加载: MarkdownLoader / PDFLoader / SwaggerLoader
    │       ├─→ 分块: SemanticChunker (按语义边界分块)
    │       ├─→ 向量化: 通过 LiteLLM 调用 Embedding 模型
    │       ├─→ 检��: 密集/稀疏/混合检索
    │       └─→ 生成: 调用 LLM 生成最终回答
    │
    ├─→ _initialize_orchestrator()
    │   └─→ code-factory/agents/orchestrator.py::LangGraphOrchestrator()
    │       └─→ 基于 LangGraph 的 DAG 工作流编排
    │
    ├─→ _initialize_review_gate()
    │   └─→ code-factory/tools/review_gate.py::HumanReviewGate()
    │       └─→ Human-in-the-Loop 审核机制
    │
    └─→ return AppContext(
        config, db_pool, vector_store, index_manager,
        rag_pipeline, model_router, orchestrator, review_gate
    )
```

### Agent 工作流执行示例：测试用例生成

```
Request: POST /api/v1/workflows/test-case-generation
    │
    └─→ FastAPI 端点
        │
        └─→ code-factory/agents/orchestrator.py::LangGraphOrchestrator::run_workflow()
            │
            ├─→ 初始化 AgentState: { requirement, context, test_cases, errors, ... }
            │
            ├─→ Node 1: RequirementAnalyzer Agent
            │   │
            │   ├─→ 调用 code-factory/rag/pipeline.py::RAGPipeline::query()
            │   │   └─→ 从知识库检索相关需求文档
            │   │
            │   ├─→ 通过 LiteLLMModelRouter 路由请求到合适模型
            │   │
            │   └─→ 更新 state.analysis_result
            │
            ├─→ Node 2: TestCaseGenerator Agent
            │   │
            │   ├─→ 基于需求生成测试用例
            │   │
            │   ├─→ 调用 atp-mcp (Auto Test Platform MCP) 工具
            │   │   └─→ 查询平台现有接口、用例、需求
            │   │
            │   └─→ 更新 state.generated_test_cases
            │
            ├─→ Node 3: ReviewGate (条件路由)
            │   │
            │   ├─→ 如果 require_review=true
            │   │   │
            │   │   └─→ code-factory/tools/review_gate.py::HumanReviewGate::submit_for_review()
            │   │       ├─→ 将审核请求存入 PostgreSQL
            │   │       ├─→ 发送 Webhook 通知
            │   │       └─→ 等待人工审核决策 (APPROVED / REJECTED / PENDING)
            │   │
            │   └─→ 如果审核拒绝，路由回 Node 2 重新生成
            │
            ├─→ Node 4: PersistenceAgent
            │   │
            │   └─→ 调用 ATP 后端 API 落库用例
            │       └─→ POST /api/v1/cases/batch_create
            │           └��→ app/models/case.py::TestCase::create()
            │
            ├─→ Node 5: ExecutionAgent
            │   │
            │   └─→ 调用 app/services/executor.py::Executor::execute_case()
            │       └─→ 执行生成的用例
            │
            └─→ Node 6: ResultAgent (汇总)
                └─→ 生成最终报告并返回
                    ├─→ 执行统计 (成功率、耗时等)
                    ├─→ 缺陷登记
                    └─→ 审计日志持久化
```

---

## 4. 🔄 关键模块调用关系

### 环境变量与权限

```
app/utils/permission.py::@permission_required (装饰器)
    │
    ├─→ 从 Flask g 对象获取当前用户
    │
    ├─→ app/models/user.py::User::get_permissions()
    │   └─→ 查询 users / roles / permissions 关联表
    │
    └─→ 检查用户是否有该资源的该操作权限
        ├─→ 有权限 → 继续执行
        └─→ 无权限 → 返回 403 Forbidden


app/services/variable_replacer.py::replace_variables()
    │
    ├─→ 从 app/models/env_variable.py 获取项目级环境变量
    │
    ├─→ 使用正则匹配 {{VAR_NAME}} 占位符
    │
    └─→ 递归替换 (支持嵌套变量)
        └─→ 如果出现循环引用，抛异常
```

### 数据初始化

```
app/init_all.py (完整数据初始化脚本)
    │
    ├─→ python app/init_db.py
    │   └─→ 创建所有数据表 (ORM 基于 SQLAlchemy 自动建表)
    │
    ├─→ python -m app.init_permission
    │   └─→ app/init_permission.py::init_permissions()
    │       ├─→ 创建 RBAC 角色: admin / owner / member / viewer
    │       └─→ 创建权限: resource:action (project:create / api:delete 等)
    │
    └─→ python app/init_api_data.py (可选)
        └─→ 创建示例项目、接口、用例
```

---

## 5. 📁 完整目录树与职责

```
auto_test_platform/
│
├── run.py                           # 应用入口 → create_app()
│
├── app/
│   ├── flask_app.py                 # Flask 应用工厂
│   ├── __init__.py
│   │
│   ├── config/
│   │   └── settings.py              # 配置类 (Development / Production)
│   │
│   ├── models/                      # ORM 数据模型
│   │   ├── base.py                  # BaseModel 基类 + db 实例
│   │   ├── user.py                  # User 用户模型
│   │   ├── api.py                   # API 接口模型
│   │   ├── case.py                  # TestCase 用例模型
│   │   ├── result.py                # TestResult 执行结果模型
│   │   ├── operation_log.py         # OperationLog 操作日志
│   │   └── ... (共15+个模型)
│   │
│   ├── routes/                      # Flask-Smorest 蓝图 (RESTful API)
│   │   ├── auth.py                  # 认证路由
│   │   ├── project.py               # 项目管理
│   │   ├── api.py                   # API 接口管理
│   │   ├── case.py                  # 用例管理
│   │   ├── execute.py               # 用例执行
│   │   ├── ai_chat.py               # AI 对话 (SSE 流式)
│   │   ├── agent_workflow.py        # Agent 工作流
│   │   └── ... (共19个蓝图)
│   │
│   ├── schemas/                     # Marshmallow 请求/响应 Schema
│   │   ├── auth.py                  # 认证 Schema
│   │   ├── case.py                  # 用例 Schema
│   │   ├── execute.py               # 执行请求 Schema
│   │   └── ... (共15+个 Schema)
│   │
│   ├── services/                    # 业务逻辑层
│   │   ├── executor.py              # 用例执行器 (核心)
│   │   ├── request_factory.py       # HTTP 请求构造
│   │   ├── variable_replacer.py     # 环境变量替换
│   │   ├── ai_service.py            # 统一 AI 调用服务
│   │   ├── ai_adapters.py           # AI 提供商适配器
│   │   └── scheduler_service.py     # 定时任务调度
│   │
│   ├── engine/                      # 执行引擎 (按测试类型)
│   │   ├── api_engine/              # API 自动化引擎 (已落地)
│   │   │   ├── api_executor.py      # 核心执行逻辑
│   │   │   ├── assertion/           # 断言模块
│   │   │   ├── extractor/           # 抽取器模块
│   │   │   └── report_generator.py  # 报告生成
│   │   ├── ui_engine/               # Web UI 自动化 (Playwright)
│   │   ├── perf_engine/             # 性能压测 (规划)
│   │   └── _legacy/                 # 已弃用的早期实现
│   │
│   ├── agents/                      # 基于 LangGraph 的 Agent 系统
│   │   ├── orchestration/           # Agent 编排
│   │   ├── business/                # 业务 Agent
│   │   └── workflows/               # 工作流定义
│   │
│   ├── tools/                       # 工具模块
│   │   ├── toolbox/                 # 工具箱 (用例生成器等)
│   │   └── tool_excel_db/           # Excel-DB 对比工具
│   │
│   ├── utils/                       # 工具函数
│   │   ├── permission.py            # RBAC 权限装饰器
│   │   ├── crypto.py                # API Key 加解密
│   │   └── logger_config.py         # 日志配置
│   │
│   └── init_*.py                    # 数据初始化脚本
│       ├── init_db.py               # 建表
│       ├── init_permission.py       # 初始化权限
│       ├── init_api_data.py         # 初始化示例数据
│       └── init_all.py              # 全量初始化
│
├── client/                          # 前端 (Vue 3 + Vite)
│   └── src/
│       ├── api/                     # API 请求封装
│       ├── components/              # 公共组件
│       ├── views/                   # 页面视图
│       ├── router/                  # 路由配置
│       └── main.js                  # 入口文件
│
├── code-factory/                    # Agent 编排系统 (独立)
│   ├── src/
│   │   ├── main.py                  # 应用启动 → create_app()
│   │   └── core/                    # 核心基础设施
│   │       ├── config.py            # Pydantic Settings 配置
│   │       ├── logging.py           # structlog 日志
│   │       ├── exceptions.py        # 异常定义
│   │       └── interfaces.py        # 抽象接口
│   │
│   ├── agents/                      # Multi-Agent 层
│   │   ├── orchestrator.py          # LangGraph 编排
│   │   └── base_agent.py            # Agent 基类
│   │
│   ├── rag/                         # RAG 检索增强
│   │   ├── pipeline.py              # RAG 主管道
│   │   ├── document_loader.py       # 文档加载
│   │   ├── chunker.py               # 语义分块
│   │   ├── vector_store.py          # PGVector 存储
│   │   └── loaders/                 # 各格式加载器
│   │
│   ├── tools/                       # 工具层
│   │   ├── model_router.py          # LiteLLM 模型路由
│   │   └── review_gate.py           # Human-in-the-Loop 审核
│   │
│   ├── config/                      # 配置文件
│   │   ├── settings.yaml            # 通用配置
│   │   ├── routing_rules.yaml       # 模型路由规则
│   │   ├── review_gates.yaml        # 审核节点配置
│   │   └── environments/            # 环境特定配置
│   │
│   └── tests/                       # 测试套件
│       ├── unit/                    # 单元测试
│       ├── property/                # 属性测试
│       └── integration/             # 集成测试
│
└── doc/                             # 文档
    ├── INDEX.md                     # 文档导航
    ├── QUICK_START.md               # 快速开始
    ├── PYTHON_CALL_DIAGRAM.md       # 本文档
    └── 生产部署指南.md
```

---

## 6. ⚙️ 核心调用链示例

### 示例 1: 单接口执行完整链路

```
run.py
 └─→ create_app()
     └─→ 启动 Flask 服务 (:12048)

[客户端] POST /api/v1/execute/run_case
  │
  └─→ routes/execute.py::ExecuteApi::post()
      │
      ├─→ 解析 JSON payload
      ├─→ ExecuteSchema().load() 校验
      │
      ├─→ services/executor.py::Executor::execute_case()
      │   │
      │   ├─→ models/case.py::TestCase.get_by_id()  [查询用例]
      │   │
      │   ├─→ services/variable_replacer.py::replace_variables()
      │   │   └─→ 替换 {{VAR}} 占位符
      │   │
      │   ���─→ services/request_factory.py::RequestFactory::build()
      │   │   └─→ 构造 HTTP 请求 (方法、URL、Header、Body等)
      │   │
      │   ├─→ engine/api_engine/api_executor.py::execute()
      │   │   │
      │   │   ├─→ requests.request() [发送HTTP请求]
      │   │   │
      │   │   ├─→ engine/api_engine/assertion/:assertion_handler.py
      │   │   │   ├─→ 执行多个断言 (json_path, status_code等)
      │   │   │   └─→ 任一断言失败则标记失败
      │   │   │
      │   │   ├─→ engine/api_engine/extractor/:extractor_handler.py
      │   │   │   └─→ 抽取响应字段供后续链式调用
      │   │   │
      │   │   └─→ return { status: 'pass/fail', response, duration, .. }
      │   │
      │   └─→ models/result.py::TestResult.create()
      │       └─→ INSERT INTO test_results ..
      │
      └─→ return Response { code: 200, data: result, message: 'success' }
```

### 示例 2: AI 流式对话完整链路

```
[客户端] POST /api/v1/ai/chat { message: "生成登录模块的测试用例" }
  │
  └─→ routes/ai_chat.py::AIChatApi::post()
      │
      ├─→ 解析 message, model, provider, temperature 等
      ├─→ AIChatSchema().load() 校验
      │
      ├─→ services/ai_service.py::AIService::stream_chat()
      │   │
      │   ├─→ services/ai_adapters.py::get_adapter(provider)
      │   │   ├─→ provider == "openai" → OpenAIAdapter
      │   │   ├─→ provider == "dashscope" → DashScopeAdapter
      │   │   └─→ provider == "ollama" → OllamaAdapter
      │   │
      │   ├─→ adapter.stream_chat(messages, model, temperature, max_tokens)
      │   │   │
      │   │   ├─→ 调用第三方 LLM API (requests.post)
      │   │   │
      │   │   └─→ yield 逐块 tokens
      │   │
      │   └─→ Token 统计: TokenCounter.add_usage()
      │       └─→ INSERT INTO token_records ..
      │
      ├─→ Flask SSE 流式响应:
      │   └─→ yield f"data: {chunk}\n\n"
      │
      └─→ [客户端] JavaScript onmessage 实时展示
```

### 示例 3: Code Factory 用例生成完整链路

```
[Agent系统] 用户在页面描述: "为用户登录功能生成API测试用例"
  │
  └─→ code-factory/src/main.py::create_app() 初始化
      │
      └─→ code-factory/agents/orchestrator.py::LangGraphOrchestrator::run_workflow(
              workflow_name="testcase_generation",
              initial_state={ requirement, context, .. }
          )
          │
          ├─→ [Node 1] RequirementAnalyzer Agent
          │   │
          │   ├─→ rag/pipeline.py::RAGPipeline::query()
          │   │   ├─→ 文档加载: MarkdownLoader.load("user-login.md")
          │   │   ├─→ 分块: SemanticChunker.chunk()
          │   │   ├─→ 向量化: embed_text() [调用LLM Embedding]
          │   │   ├─→ 检索: vector_store.search() [PGVector查询]
          │   │   └─→ 生成: LLM.generate(context + chunks)
          │   │
          │   └─→ return state.analysis_result
          │
          ├─→ [Node 2] TestcaseAgent
          │   │
          │   ├─→ 调用 atp-mcp (ATP MCP 工具集)
          │   │   ├─→ query_apis(project_id, keyword="login")
          │   │   ├─→ query_requirements(project_id)
          │   │   └─→ query_existing_cases(api_id)
          │   │
          │   ├─→ 基于已有知识生成新用例
          │   │
          │   └─→ return state.generated_test_cases
          │
          ├─→ [Node 3] ReviewGate
          │   │
          │   ├─→ tools/review_gate.py::HumanReviewGate::submit_for_review()
          │   │   ├─→ INSERT INTO review_records ..
          │   │   ├─→ POST Webhook https://your-webhook-url
          │   │   └─→ await human review (APPROVED / REJECTED)
          │   │
          │   └─→ if REJECTED: route back to Node 2
          │
          ├─→ [Node 4] PersistenceAgent
          │   │
          │   └─→ POST http://localhost:12048/api/v1/cases/batch_create
          │       └─→ ATP 后端 routes/case.py 落库用例
          │
          ├─→ [Node 5] ExecutionAgent
          │   │
          │   └─→ services/executor.py::Executor::execute_case()
          │       └─→ 执行新生成的用例 (见示例1)
          │
          └─→ [Node 6] ResultAgent
              └─→ return { status: 'success', cases_created: 5, cases_passed: 4, .. }
```

---

## 7. 🔌 MCP (Model Context Protocol) 工具集

### atp-mcp 工具列表 (ATP自建)

```
atp-mcp (ATP 后端能力暴露为 MCP 工具)
├─→ query_projects() - 查询项目列表
├─→ query_apis() - 查询接口定义
├─→ query_requirements() - 查询需求
├─→ query_existing_cases() - 查询已有用例
├─→ query_bugs() - 查询缺陷
├─→ create_case() - 创建用例
├─→ execute_case() - 执行用例
├─→ get_execution_result() - 查询执行结果
└─→ ... (共20+ 个工具)
```

### http-api-mcp 工具列表 (HTTP通用工具)

```
http-api-mcp (13个HTTP工具)
├─→ send_request() - 发送通用HTTP请求
├─→ get_request() - GET 快捷方式
├─→ post_request() - POST 快捷方式
├─→ load_openapi() - 加载OpenAPI定义
├─→ list_endpoints() - 列举接口端点
├─→ call_by_operation_id() - 按operationId调用
├─→ assert_status_code() - 断言状态码
├─→ assert_json_path() - 断言JSONPath
├─→ assert_response_time() - 断言响应时间
├─→ extract_by_json_path() - 抽取JSONPath
├─→ extract_regex() - 正则抽取
├─→ set_session_var() - 设置会话变量
└─→ get_session_var() - 获取会话变量
```

---

## 8. 📊 数据流向总结

```
                    ┌─────────────────────────┐
                    │   Vue 3 前端 (5173)      │
                    │   用户交互 + 实时显示    │
                    └────────────┬──────��──────┘
                                 │ JSON Request/Response
                    ┌────────────▼─────────────┐
                    │  Flask 后端 (12048)      │
                    │  Routes + Schemas        │
                    └────────────┬─────────────┘
                                 │ Business Logic
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │  Services    │  │   Engine     │  │   AI Layer   │
        │(executor,    │  │(api_engine,  │  │(ai_service,  │
        │ variable_    │  │ ui_engine)   │  │ adapters)    │
        │ replacer)    │  └──────────────┘  └──────┬───────┘
        └──────┬───────┘         │                  │
               │                 │                  │
               ├─────────────────┼──────────────────┤
               │                 │                  │
               ▼                 ▼                  ▼
        ┌──────────────────────────────────────────────┐
        │  Models (ORM)                                │
        │  User, Project, API, Case, Result, ..        │
        └──────────────────┬───────────────────────────┘
                           │ SQL
                    ┌──────▼──────────┐
                    │ MySQL 数据库    │
                    │  business DB   │
                    └─────────────────┘


Code Factory 独立架构:
                    ┌─────────────────────────┐
                    │  FastAPI 服务           │
                    │  (Agent编排入口)        │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ Orchestrator │  │ Model Router │  │ RAG Pipeline │
        │ (LangGraph)  │  │ (LiteLLM)    │  │ (LlamaIndex) │
        └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
               │                 │                  │
               └─────────────────┼──────────────────┤
                                 │                  │
                        ┌��───────▼────────┐  ┌────▼───────┐
                        │ LLM APIs        │  │ PGVector   │
                        │(OpenAI/Claude)  │  │(向量存储)  │
                        └─────────────────┘  └────────────┘
                             │
                        ┌────▼────────────────┐
                        │ PostgreSQL 数据库   │
                        │ (code_factory DB)   │
                        └─────────────────────┘
```

---

## 9. 🚦 控制流图

### 权限检查流程

```
Request → @permission_required(resource='api', action='delete')
    │
    ├─→ from g 获取当前 user_id
    │
    ├─→ User.get_permissions(user_id)
    │   │
    │   ├─→ JOIN users u
    │   │   JOIN roles r ON u.role_id = r.id
    │   │   JOIN role_permissions rp ON r.id = rp.role_id
    │   │   JOIN permissions p ON rp.permission_id = p.id
    │   │
    │   └─→ return [(resource, action), ...]
    │
    ├─→ if ('api', 'delete') in permissions:
    │   │
    │   └─→ 继续执行路由处理
    │
    └─→ else:
        └─→ return 403 Forbidden
```

### 异常处理流程

```
try:
    └─→ 执行业务逻辑
catch Exception as e:
    │
    ├─→ app/utils/logger_config.py::log_exception()
    │   └─→ 记录到 logs/error.log
    │
    ├─→ 判断异常类型:
    │   ├─→ ValidationError → 400 Bad Request
    │   ├─→ PermissionError → 403 Forbidden
    │   ├─→ NotFoundError → 404 Not Found
    │   ├─→ DatabaseError → 500 Internal Server Error
    │   └─→ 其他 → 500 Internal Server Error
    │
    └─→ return { code: error_code, message: error_msg, data: null }
```

---

## 10. 📝 关键文件依赖图

```
run.py
  └─→ app/flask_app.py (create_app)
      │
      ├─→ app/config/settings.py
      │   └─→ 配置类 (development, production)
      │
      ├─→ app/models/base.py (db 实例)
      │   └─→ SQLAlchemy ORM 初始化
      │
      ├─→ app/routes/*.py (所有蓝图)
      │   ├─→ app/schemas/*.py (请求校验)
      │   │   └─→ Marshmallow Schema
      │   │
      │   └─→ app/services/*.py (业务逻辑)
      │       └─→ app/engine/*/*.py (执行引擎)
      │
      └─→ app/utils/logger_config.py (日志系统)
          └─→ RotatingFileHandler


code-factory/src/main.py
  └─→ code-factory/src/core/config.py
      ├─→ Pydantic Settings
      └─→ config/*.yaml (YAML 配置文件)
  
  └─→ code-factory/agents/orchestrator.py
      ├─→ LangGraph
      └─→ code-factory/agents/base_agent.py
  
  └─→ code-factory/rag/pipeline.py
      ├─→ DocumentLoader (loaders/*.py)
      ├─→ Chunker
      ├─→ VectorStore
      └─→ LLM Integration
  
  └─→ code-factory/tools/model_router.py
      └─→ LiteLLM 统一接口
```

---

## 总结

| 层级 | 文件位置 | 职责 | 依赖 |
|------|---------|------|------|
| **入口** | `run.py` | 应用启动 | Flask |
| **路由** | `app/routes/*.py` | HTTP 接口 | Flask-Smorest |
| **校验** | `app/schemas/*.py` | 请求/响应 | Marshmallow |
| **业务** | `app/services/*.py` | 核心逻辑 | Models |
| **执行** | `app/engine/*/*.py` | 测试执行 | Requests, Playwright |
| **数据** | `app/models/*.py` | ORM 映射 | SQLAlchemy |
| **AI** | `app/services/ai_*.py` | LLM 调用 | OpenAI/DashScope/Ollama |
| **Agent** | `code-factory/agents/*.py` | 工作流编排 | LangGraph, MCP |
| **RAG** | `code-factory/rag/*.py` | 知识检索 | LlamaIndex, PGVector |

---

**文档作者**: GitHub Copilot  
**最后更新**: 2026-07-17
