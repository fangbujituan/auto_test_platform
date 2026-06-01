# Requirements Document

## Introduction

QA Code Factory 是一个企业级智能测试自动化平台，通过 Multi-Agent 协作与 RAG（检索增强生成）技术，实现测试用例智能生成、高质量测试数据构造、自动化测试脚本编写。系统严格遵循公司代码规范，支持 Human-in-the-Loop 审核机制，优先使用本地模型以保障数据安全，复杂任务可路由至云端模型。

本文档覆盖 Phase 1：项目初始化与基础架构、技术栈集成、公司知识库 RAG 系统建设。

## Glossary

- **Code_Factory**: QA Code Factory 系统整体，包含所有 Agent、RAG 管道、工具链
- **Agent_Orchestrator**: 基于 LangGraph 的 Multi-Agent 编排引擎，负责任务分发与 Agent 间协作
- **RAG_Pipeline**: 检索增强生成管道，包含文档加载、分块、索引、检索、生成全流程
- **Document_Loader**: 文档加载组件，负责从多种格式文件中提取结构化文本
- **Chunker**: 智能分块组件，将文档拆分为语义完整的片段并附加元数据
- **Vector_Store**: 向量数据库（PGVector），存储文档嵌入向量与元数据
- **Model_Router**: 基于 LiteLLM 的模型路由组件，根据任务复杂度选择本地或云端模型
- **Knowledge_Base**: 公司知识库，包含需求文档、Bug 记录、接口定义、测试用例、代码规范等
- **Index_Manager**: 索引管理组件，负责知识库索引的构建、更新与版本管理
- **Human_Review_Gate**: Human-in-the-Loop 审核节点，在关键决策点暂停执行等待人工确认

## Requirements

### Requirement 1: 项目结构初始化

**User Story:** As a 开发者, I want 一个清晰规范的项目目录结构, so that 团队成员能快速理解项目组织并高效协作。

#### Acceptance Criteria

1. THE Code_Factory SHALL provide a Python project managed by Poetry or uv with a valid pyproject.toml configuration file
2. THE Code_Factory SHALL organize source code into the following top-level directories: src, agents, rag, tools, config, tests
3. THE Code_Factory SHALL include a .env.example file documenting all required environment variables with placeholder values
4. THE Code_Factory SHALL include a README.md file describing project purpose, setup instructions, and directory structure
5. WHEN a new developer clones the repository, THE Code_Factory SHALL allow project setup completion within a single command (e.g., `poetry install` or `uv sync`)

---

### Requirement 2: 模型路由与 LLM 集成

**User Story:** As a 系统管理员, I want 灵活的模型路由能力, so that 系统能根据任务复杂度和数据安全要求选择合适的模型。

#### Acceptance Criteria

1. THE Model_Router SHALL integrate LiteLLM as the unified interface for all LLM calls
2. THE Model_Router SHALL support routing requests to local models via Ollama or vLLM
3. THE Model_Router SHALL support routing requests to cloud models including Claude and DeepSeek
4. WHEN a task is classified as low-complexity, THE Model_Router SHALL route the request to a local model
5. WHEN a task is classified as high-complexity, THE Model_Router SHALL route the request to a cloud model
6. THE Model_Router SHALL expose a configuration file allowing administrators to define routing rules without code changes
7. IF a model endpoint is unavailable, THEN THE Model_Router SHALL retry with an alternative model from the same tier within 3 attempts
8. IF all model endpoints in a tier are unavailable, THEN THE Model_Router SHALL escalate to the next tier and log a warning

---

### Requirement 3: Multi-Agent 编排引擎

**User Story:** As a QA 工程师, I want 多个专业 Agent 协同工作, so that 复杂的测试任务能被分解并高效完成。

#### Acceptance Criteria

1. THE Agent_Orchestrator SHALL use LangGraph as the framework for defining and executing multi-agent workflows
2. THE Agent_Orchestrator SHALL support defining agent workflows as directed acyclic graphs with conditional edges
3. THE Agent_Orchestrator SHALL pass structured state objects between agents in a workflow
4. WHEN an agent completes its task, THE Agent_Orchestrator SHALL validate the output schema before passing it to the next agent
5. IF an agent produces invalid output, THEN THE Agent_Orchestrator SHALL retry the agent up to 2 times before marking the task as failed
6. THE Agent_Orchestrator SHALL log each agent invocation with input, output, model used, and execution duration

---

### Requirement 4: Human-in-the-Loop 审核机制

**User Story:** As a QA 负责人, I want 在关键决策点进行人工审核, so that 自动生成的内容经过人工确认后才进入下游流程。

#### Acceptance Criteria

1. THE Human_Review_Gate SHALL pause workflow execution at configured review points and wait for human approval
2. WHEN a human reviewer approves the output, THE Agent_Orchestrator SHALL resume workflow execution with the approved content
3. WHEN a human reviewer rejects the output, THE Agent_Orchestrator SHALL route the task back to the originating agent with reviewer feedback
4. THE Human_Review_Gate SHALL support configuring review points per workflow via a YAML configuration file
5. IF a review request receives no response within a configurable timeout period, THEN THE Human_Review_Gate SHALL send a reminder notification
6. THE Human_Review_Gate SHALL record all review decisions with reviewer identity, timestamp, and comments

---

### Requirement 5: 文档加载与处理管道

**User Story:** As a 知识库管理员, I want 支持多种文档格式的加载能力, so that 公司各类技术文档都能被纳入知识库。

#### Acceptance Criteria

1. THE Document_Loader SHALL support loading documents in the following formats: PDF, Markdown, Word (.docx), Swagger/OpenAPI (JSON and YAML), and source code files (Python, Java, JavaScript, TypeScript)
2. WHEN a document is loaded, THE Document_Loader SHALL extract plain text content while preserving structural information (headings, code blocks, tables)
3. WHEN a Swagger/OpenAPI file is loaded, THE Document_Loader SHALL extract each API endpoint as a separate logical unit with method, path, parameters, and response schema
4. WHEN a source code file is loaded, THE Document_Loader SHALL extract functions, classes, and docstrings as separate logical units
5. IF a document format is unsupported, THEN THE Document_Loader SHALL reject the document with a descriptive error message indicating supported formats
6. IF a document is corrupted or unreadable, THEN THE Document_Loader SHALL log the error with file path and failure reason, and continue processing remaining documents

---

### Requirement 6: 智能分块与元数据标注

**User Story:** As a RAG 系统, I want 语义完整的文档分块并附带丰富元数据, so that 检索结果精准且可追溯。

#### Acceptance Criteria

1. THE Chunker SHALL split documents into chunks that preserve semantic completeness (not splitting mid-sentence or mid-code-block)
2. THE Chunker SHALL assign metadata tags to each chunk including: project name, module name, document version, and content type (requirement, bug, API, test case, code specification)
3. THE Chunker SHALL maintain configurable chunk size limits with a default maximum of 512 tokens and an overlap of 50 tokens between adjacent chunks
4. WHEN a document contains code blocks, THE Chunker SHALL keep each code block as a single chunk regardless of size up to 2048 tokens
5. WHEN a document contains tables, THE Chunker SHALL keep each table row with its header as context
6. THE Chunker SHALL generate a unique identifier for each chunk based on source document path, chunk position, and document version

---

### Requirement 7: 向量数据库与索引管理

**User Story:** As a 系统架构师, I want 高效的向量存储与索引管理, so that 知识库检索响应快速且支持持续更新。

#### Acceptance Criteria

1. THE Vector_Store SHALL use PGVector as the primary vector database for storing document embeddings
2. THE Vector_Store SHALL store each chunk's embedding vector alongside its metadata and original text content
3. THE Vector_Store SHALL support similarity search returning top-K results with configurable K value (default K=5)
4. WHEN a similarity search is performed, THE Vector_Store SHALL return results within 500 milliseconds for a knowledge base containing up to 100,000 chunks
5. THE Index_Manager SHALL support incremental index updates without requiring full re-indexing of unchanged documents
6. WHEN a document is updated, THE Index_Manager SHALL detect changed sections, remove outdated chunks, and index only the new or modified chunks
7. WHEN a document is deleted from the knowledge base, THE Index_Manager SHALL remove all associated chunks and embeddings from the Vector_Store
8. THE Index_Manager SHALL maintain a version log recording each index update with timestamp, affected documents, and chunk count changes

---

### Requirement 8: RAG 检索与生成集成

**User Story:** As a QA 工程师, I want 基于公司知识库的智能检索与生成, so that 生成的测试内容符合公司规范和业务上下文。

#### Acceptance Criteria

1. THE RAG_Pipeline SHALL integrate LlamaIndex or LangChain as the retrieval-augmented generation framework
2. WHEN a query is submitted, THE RAG_Pipeline SHALL retrieve relevant chunks from the Vector_Store and include them as context for the LLM generation
3. THE RAG_Pipeline SHALL support metadata-filtered retrieval allowing queries scoped to specific projects, modules, or content types
4. WHEN generating output, THE RAG_Pipeline SHALL cite source documents by including chunk identifiers in the response
5. THE RAG_Pipeline SHALL support configurable retrieval strategies including dense retrieval, sparse retrieval (BM25), and hybrid retrieval
6. IF no relevant chunks are found above a configurable similarity threshold (default 0.7), THEN THE RAG_Pipeline SHALL inform the user that insufficient context is available and proceed with a general-knowledge response clearly marked as ungrounded

---

### Requirement 9: 配置管理与环境隔离

**User Story:** As a DevOps 工程师, I want 集中化的配置管理与环境隔离, so that 系统能在开发、测试、生产环境间安全切换。

#### Acceptance Criteria

1. THE Code_Factory SHALL load all sensitive configuration (API keys, database credentials) from environment variables
2. THE Code_Factory SHALL support environment-specific configuration files (development, testing, production) selectable via an environment variable
3. THE Code_Factory SHALL validate all required configuration values at startup and report missing or invalid values with descriptive error messages before proceeding
4. IF a required configuration value is missing at startup, THEN THE Code_Factory SHALL terminate with a non-zero exit code and a log message identifying the missing value
5. THE Code_Factory SHALL provide a configuration schema file documenting all configuration options with types, defaults, and descriptions

---

### Requirement 10: 日志与可观测性

**User Story:** As a 运维工程师, I want 结构化日志与可观测性支持, so that 系统运行状态可追踪、问题可快速定位。

#### Acceptance Criteria

1. THE Code_Factory SHALL output structured logs in JSON format with fields: timestamp, level, module, message, and correlation_id
2. THE Code_Factory SHALL assign a unique correlation_id to each user request and propagate the correlation_id across all agent invocations within that request
3. WHEN an agent is invoked, THE Code_Factory SHALL log the agent name, input summary, output summary, model used, token count, and latency
4. THE Code_Factory SHALL support configurable log levels (DEBUG, INFO, WARNING, ERROR) selectable per module
5. IF an unhandled exception occurs, THEN THE Code_Factory SHALL log the full stack trace at ERROR level with the correlation_id and continue serving other requests
