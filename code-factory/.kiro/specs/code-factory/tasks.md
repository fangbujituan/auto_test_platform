# Implementation Plan: Code Factory

## Overview

本实现计划将 Code Factory Phase 1 的设计分解为可增量执行的编码任务。每个任务构建在前一个任务之上，确保无孤立代码。实现顺序为：基础设施层 → 配置管理 → 日志 → 文档处理 → 向量存储 → RAG 管道 → 模型路由 → Agent 编排 → 审核机制 → 集成联调。

## Tasks

- [x] 1. Set up project structure and core infrastructure
  - [x] 1.1 Initialize project with pyproject.toml and directory structure
    - Create `pyproject.toml` with Poetry configuration, including all dependencies (litellm, langgraph, llama-index, pgvector, pydantic-settings, structlog, hypothesis)
    - Create directory structure: `src/core/`, `agents/`, `rag/`, `tools/`, `config/`, `tests/unit/`, `tests/property/`, `tests/integration/`
    - Create `__init__.py` files for all packages
    - Create `.env.example` with all required environment variables (DB credentials, API keys, model endpoints)
    - Create `README.md` with project purpose, setup instructions, and directory structure
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Create custom exception hierarchy
    - Implement `src/core/exceptions.py` with `CodeFactoryError`, `ModelRoutingError`, `ModelTierExhaustedError`, `AgentExecutionError`, `SchemaValidationError`, `DocumentLoadError`, `UnsupportedFormatError`, `ConfigurationError`, `MissingConfigError`
    - Each exception carries `correlation_id` for traceability
    - _Requirements: 2.7, 2.8, 3.5, 5.5, 5.6, 9.4_

  - [x] 1.3 Create shared data models and interfaces
    - Implement all dataclasses and enums from design: `ModelTier`, `TaskComplexity`, `RoutingRule`, `LLMRequest`, `LLMResponse`, `AgentState`, `WorkflowStatus`, `ReviewDecision`, `ReviewRequest`, `ReviewRecord`, `DocumentFormat`, `DocumentUnit`, `LoadedDocument`, `ChunkMetadata`, `Chunk`, `ChunkConfig`, `EmbeddingRecord`, `SearchResult`, `IndexUpdateLog`, `RAGQuery`, `RAGContext`, `RAGResponse`, `RetrievalStrategy`
    - Implement all abstract base classes (interfaces): `ModelRouterInterface`, `AgentInterface`, `OrchestratorInterface`, `ReviewGateInterface`, `DocumentLoaderInterface`, `ChunkerInterface`, `VectorStoreInterface`, `IndexManagerInterface`, `RAGPipelineInterface`
    - _Requirements: 2.1, 3.1, 3.3, 4.1, 5.1, 6.1, 7.1, 8.1_

  - [x] 1.4 Create database schema migration
    - Create SQL migration file with all 5 tables: `documents`, `chunks`, `review_records`, `workflow_logs`, `index_update_logs`
    - Include PGVector extension creation, all indexes (ivfflat for embeddings, metadata filtering indexes)
    - _Requirements: 7.1, 7.2, 7.4_

- [x] 2. Implement Configuration Manager
  - [x] 2.1 Implement Pydantic Settings configuration
    - Create `src/core/config.py` with Pydantic Settings classes: `DatabaseConfig`, `ModelConfig`, `AppConfig`
    - Support environment-specific YAML config files (`config/environments/development.yaml`, `testing.yaml`, `production.yaml`)
    - Load sensitive values from environment variables, non-sensitive from YAML
    - Implement startup validation that reports ALL missing/invalid fields with descriptive messages
    - Terminate with non-zero exit code if required config is missing
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 2.2 Write property test for configuration validation
    - **Property 25: Configuration validation reports all issues**
    - **Validates: Requirements 9.3**

  - [x] 2.3 Create configuration YAML files
    - Create `config/settings.yaml` with common settings
    - Create `config/routing_rules.yaml` with model routing rules per task type
    - Create `config/review_gates.yaml` with review point definitions per workflow
    - Create environment-specific overrides in `config/environments/`
    - _Requirements: 2.6, 4.4, 9.2, 9.5_

  - [ ]* 2.4 Write unit tests for Configuration Manager
    - Test loading from environment variables
    - Test environment-specific config selection
    - Test validation error messages for missing fields
    - Test non-zero exit on missing required config
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 3. Implement Structured Logging
  - [x] 3.1 Implement structlog-based logging system
    - Create `src/core/logging.py` with structlog configuration
    - Output JSON format with required fields: timestamp, level, module, message, correlation_id
    - Implement correlation_id context binding and propagation
    - Support configurable log levels per module
    - Implement unhandled exception logging with full stack trace and correlation_id
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 3.2 Write property test for structured log format
    - **Property 26: Structured log format consistency**
    - **Validates: Requirements 10.1, 10.2**

  - [ ]* 3.3 Write property test for exception logging
    - **Property 27: Exception logging preserves context**
    - **Validates: Requirements 10.5**

  - [ ]* 3.4 Write unit tests for logging system
    - Test JSON output format
    - Test correlation_id propagation across calls
    - Test per-module log level configuration
    - Test exception logging with stack trace
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Document Loader
  - [x] 5.1 Implement base Document Loader with format detection
    - Create `rag/document_loader.py` implementing `DocumentLoaderInterface`
    - Implement format detection from file extension
    - Implement unsupported format rejection with descriptive error listing supported formats
    - Implement error handling for corrupted/unreadable files (log and continue)
    - _Requirements: 5.1, 5.5, 5.6_

  - [x] 5.2 Implement PDF and Word loaders
    - Implement PDF loading with text extraction preserving headings, code blocks, tables
    - Implement Word (.docx) loading with structural preservation
    - Extract content as `DocumentUnit` objects with appropriate `unit_type`
    - _Requirements: 5.1, 5.2_

  - [x] 5.3 Implement Markdown loader
    - Parse Markdown preserving headings, code blocks, tables as separate `DocumentUnit` objects
    - Maintain structural information (heading hierarchy, code language)
    - _Requirements: 5.1, 5.2_

  - [x] 5.4 Implement Swagger/OpenAPI loader
    - Support both JSON and YAML OpenAPI formats
    - Extract each API endpoint as a separate `DocumentUnit` with method, path, parameters, response schema
    - _Requirements: 5.1, 5.3_

  - [x] 5.5 Implement source code loader
    - Support Python, Java, JavaScript, TypeScript files
    - Extract functions, classes, and docstrings as separate `DocumentUnit` objects
    - Use AST parsing for Python; regex/tree-sitter for other languages
    - _Requirements: 5.1, 5.4_

  - [ ]* 5.6 Write property test for Swagger endpoint extraction
    - **Property 9: Swagger endpoint extraction as separate units**
    - **Validates: Requirements 5.3**

  - [ ]* 5.7 Write property test for source code extraction
    - **Property 10: Source code logical unit extraction**
    - **Validates: Requirements 5.4**

  - [ ]* 5.8 Write property test for unsupported format rejection
    - **Property 11: Unsupported format rejection**
    - **Validates: Requirements 5.5**

  - [ ]* 5.9 Write unit tests for Document Loader
    - Test each format loader with sample files
    - Test structural preservation (headings, code blocks, tables)
    - Test error handling for corrupted files
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 6. Implement Chunker
  - [x] 6.1 Implement semantic chunking logic
    - Create `rag/chunker.py` implementing `ChunkerInterface`
    - Implement sentence-boundary-aware splitting (never split mid-sentence)
    - Implement code-block-aware splitting (keep code blocks intact up to 2048 tokens)
    - Implement table-aware splitting (keep rows with headers)
    - Implement configurable chunk size (default 512 tokens) with overlap (default 50 tokens)
    - _Requirements: 6.1, 6.3, 6.4, 6.5_

  - [x] 6.2 Implement metadata tagging and chunk ID generation
    - Assign metadata to each chunk: project_name, module_name, document_version, content_type
    - Generate deterministic unique chunk IDs based on source_path + chunk_position + document_version
    - _Requirements: 6.2, 6.6_

  - [ ]* 6.3 Write property test for semantic boundary preservation
    - **Property 12: Semantic chunking preserves boundaries**
    - **Validates: Requirements 6.1**

  - [ ]* 6.4 Write property test for chunk metadata completeness
    - **Property 13: Chunk metadata completeness**
    - **Validates: Requirements 6.2**

  - [ ]* 6.5 Write property test for chunk size limits
    - **Property 14: Chunk size respects type-specific limits**
    - **Validates: Requirements 6.3, 6.4**

  - [ ]* 6.6 Write property test for table header preservation
    - **Property 15: Table rows preserve header context**
    - **Validates: Requirements 6.5**

  - [ ]* 6.7 Write property test for chunk ID determinism
    - **Property 16: Chunk ID determinism and uniqueness**
    - **Validates: Requirements 6.6**

  - [ ]* 6.8 Write unit tests for Chunker
    - Test splitting with various document types
    - Test overlap between adjacent chunks
    - Test code block handling at size boundary
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.6_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Vector Store with PGVector
  - [x] 8.1 Implement PGVector-based Vector Store
    - Create `rag/vector_store.py` implementing `VectorStoreInterface`
    - Implement `upsert` for inserting/updating embedding records
    - Implement `search` with top-K similarity search and metadata filtering
    - Implement `delete_by_document` for removing all chunks of a document
    - Use asyncpg for async database operations
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 8.2 Write property test for vector store round-trip
    - **Property 17: Vector store storage round-trip**
    - **Validates: Requirements 7.2**

  - [ ]* 8.3 Write property test for top-K search ordering
    - **Property 18: Top-K search returns exactly K ordered results**
    - **Validates: Requirements 7.3**

- [x] 9. Implement Index Manager
  - [x] 9.1 Implement incremental index management
    - Create `rag/index_manager.py` implementing `IndexManagerInterface`
    - Implement change detection using content hash (SHA-256) comparison
    - Implement incremental updates: add new chunks, remove outdated, update modified
    - Implement document deletion with full chunk removal
    - Implement version logging for each index update operation
    - _Requirements: 7.5, 7.6, 7.7, 7.8_

  - [ ]* 9.2 Write property test for incremental index change detection
    - **Property 19: Incremental index detects changes correctly**
    - **Validates: Requirements 7.6**

  - [ ]* 9.3 Write property test for document deletion
    - **Property 20: Document deletion removes all chunks**
    - **Validates: Requirements 7.7**

  - [ ]* 9.4 Write property test for index update logging
    - **Property 21: Index update produces complete log entry**
    - **Validates: Requirements 7.8**

  - [ ]* 9.5 Write unit tests for Index Manager
    - Test change detection with modified documents
    - Test incremental update correctness
    - Test version log entries
    - _Requirements: 7.5, 7.6, 7.7, 7.8_

- [x] 10. Implement RAG Pipeline
  - [x] 10.1 Implement RAG Pipeline with LlamaIndex
    - Create `rag/pipeline.py` implementing `RAGPipelineInterface`
    - Implement dense retrieval using vector similarity
    - Implement sparse retrieval using BM25
    - Implement hybrid retrieval combining dense and sparse
    - Implement metadata-filtered retrieval (project, module, content_type)
    - Implement similarity threshold check; mark responses as ungrounded when below threshold
    - Include chunk_id citations in all responses
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 10.2 Write property test for metadata filter correctness
    - **Property 22: Metadata filter returns only matching chunks**
    - **Validates: Requirements 8.3**

  - [ ]* 10.3 Write property test for RAG citations
    - **Property 23: RAG response includes source citations**
    - **Validates: Requirements 8.4**

  - [ ]* 10.4 Write property test for ungrounded response marking
    - **Property 24: Below-threshold queries marked as ungrounded**
    - **Validates: Requirements 8.6**

  - [ ]* 10.5 Write unit tests for RAG Pipeline
    - Test each retrieval strategy independently
    - Test hybrid retrieval combination
    - Test metadata filtering
    - Test ungrounded response handling
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement Model Router
  - [x] 12.1 Implement LiteLLM-based Model Router
    - Create `tools/model_router.py` implementing `ModelRouterInterface`
    - Implement complexity classification based on task_type and context
    - Implement routing logic: low-complexity → local tier, high-complexity → cloud tier
    - Load routing rules from `config/routing_rules.yaml`
    - Implement same-tier retry (up to 3 attempts) on endpoint unavailability
    - Implement tier escalation when all models in a tier are exhausted, with warning log
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 12.2 Write property test for routing respects complexity
    - **Property 1: Model routing respects complexity classification**
    - **Validates: Requirements 2.4, 2.5**

  - [ ]* 12.3 Write property test for same-tier retry
    - **Property 2: Model retry stays within same tier**
    - **Validates: Requirements 2.7**

  - [ ]* 12.4 Write property test for tier escalation
    - **Property 3: Model tier escalation on exhaustion**
    - **Validates: Requirements 2.8**

  - [ ]* 12.5 Write unit tests for Model Router
    - Test complexity classification for various task types
    - Test routing to correct tier
    - Test retry behavior with mock failures
    - Test escalation logging
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 13. Implement Agent Orchestrator
  - [x] 13.1 Implement LangGraph-based Agent Orchestrator
    - Create `agents/orchestrator.py` implementing `OrchestratorInterface`
    - Implement DAG workflow definition with conditional edges
    - Implement structured state passing between agents (AgentState)
    - Implement output schema validation before passing to next agent
    - Implement retry logic (up to 2 retries) on schema validation failure
    - Mark task as failed after all retries exhausted
    - Log each agent invocation with all required fields
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 13.2 Implement base Agent class
    - Create `agents/base_agent.py` with `BaseAgent` implementing `AgentInterface`
    - Implement `execute` method template with logging and error handling
    - Implement `validate_output` method with JSON schema validation
    - _Requirements: 3.3, 3.4, 3.6_

  - [ ]* 13.3 Write property test for agent state integrity
    - **Property 4: Agent state integrity through workflow**
    - **Validates: Requirements 3.3**

  - [ ]* 13.4 Write property test for output validation with retry
    - **Property 5: Agent output validation with retry**
    - **Validates: Requirements 3.4, 3.5**

  - [ ]* 13.5 Write property test for invocation logging completeness
    - **Property 6: Agent invocation logging completeness**
    - **Validates: Requirements 3.6, 10.3**

  - [ ]* 13.6 Write unit tests for Agent Orchestrator
    - Test workflow execution with mock agents
    - Test state passing between agents
    - Test retry on validation failure
    - Test failure marking after retries exhausted
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 14. Implement Human Review Gate
  - [x] 14.1 Implement Human Review Gate mechanism
    - Create `tools/review_gate.py` implementing `ReviewGateInterface`
    - Implement workflow pause at configured review points
    - Implement resume on approval (pass approved content downstream)
    - Implement rejection routing (send task back to originating agent with feedback)
    - Load review point configuration from `config/review_gates.yaml`
    - Implement configurable timeout with reminder notifications
    - Persist all review decisions with reviewer_id, timestamp, comments
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 14.2 Write property test for rejection feedback propagation
    - **Property 7: Rejection feedback propagation**
    - **Validates: Requirements 4.3**

  - [ ]* 14.3 Write property test for review record completeness
    - **Property 8: Review record completeness**
    - **Validates: Requirements 4.6**

  - [ ]* 14.4 Write unit tests for Human Review Gate
    - Test pause and resume workflow
    - Test rejection with feedback routing
    - Test timeout notification triggering
    - Test review record persistence
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 15. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Integration wiring and test configuration
  - [x] 16.1 Wire all components together in application entry point
    - Create `src/main.py` as application entry point
    - Initialize configuration, logging, database connection
    - Wire Model Router, Agent Orchestrator, RAG Pipeline, Review Gate
    - Implement startup validation (config check → DB connection → model availability)
    - _Requirements: 1.5, 9.1, 9.3, 9.4_

  - [x] 16.2 Create test configuration and fixtures
    - Create `tests/conftest.py` with Hypothesis profiles (ci: 200 examples, dev: 100 examples)
    - Create shared test fixtures for database, mock models, sample documents
    - Configure pytest-asyncio for async test support
    - _Requirements: All_

  - [ ]* 16.3 Write integration tests for PGVector operations
    - Test actual vector upsert and similarity search
    - Test metadata filtering with real database
    - Test document deletion cascade
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7_

  - [ ]* 16.4 Write integration tests for RAG pipeline end-to-end
    - Test document load → chunk → index → retrieve → generate flow
    - Test hybrid retrieval with real vector store
    - Test citation inclusion in responses
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 17. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 27 universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- Integration tests validate component interactions with real infrastructure
- All code is Python, using Poetry for dependency management
- Hypothesis is used for property-based testing with minimum 100 examples per property

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4"] },
    { "id": 2, "tasks": ["2.1", "3.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "3.2", "3.3", "3.4"] },
    { "id": 4, "tasks": ["5.1", "6.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4", "5.5", "6.2"] },
    { "id": 6, "tasks": ["5.6", "5.7", "5.8", "5.9", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8"] },
    { "id": 7, "tasks": ["8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3", "9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3", "9.4", "9.5", "10.1"] },
    { "id": 10, "tasks": ["10.2", "10.3", "10.4", "10.5"] },
    { "id": 11, "tasks": ["12.1"] },
    { "id": 12, "tasks": ["12.2", "12.3", "12.4", "12.5", "13.1"] },
    { "id": 13, "tasks": ["13.2"] },
    { "id": 14, "tasks": ["13.3", "13.4", "13.5", "13.6", "14.1"] },
    { "id": 15, "tasks": ["14.2", "14.3", "14.4"] },
    { "id": 16, "tasks": ["16.1", "16.2"] },
    { "id": 17, "tasks": ["16.3", "16.4"] }
  ]
}
```
