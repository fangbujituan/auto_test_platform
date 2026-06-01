-- Migration: 001_initial_schema
-- Description: Initial database schema for Code Factory
-- Creates all core tables for the knowledge base, review system, and workflow logging
-- Requirements: 7.1 (PGVector as primary vector database), 7.2 (store embeddings with metadata), 7.4 (fast similarity search)

-- Enable PGVector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 文档元数据表 (Document Metadata)
-- Stores metadata about loaded documents for change detection and versioning
-- ============================================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path VARCHAR(1024) NOT NULL UNIQUE,
    format VARCHAR(50) NOT NULL,
    version VARCHAR(100) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 for change detection
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 分块表 (Chunks with Vector Embeddings)
-- Stores document chunks with their embedding vectors and metadata
-- Chunk ID is generated from source_path + position + version
-- ============================================================================
CREATE TABLE chunks (
    id VARCHAR(256) PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI ada-002 dimensions, configurable
    token_count INTEGER NOT NULL,
    chunk_position INTEGER NOT NULL,
    project_name VARCHAR(200),
    module_name VARCHAR(200),
    document_version VARCHAR(100),
    content_type VARCHAR(50),  -- requirement, bug, api, test_case, code_specification
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector similarity search index using IVFFlat for cosine distance
-- Requirement 7.4: search within 500ms for up to 100,000 chunks
CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Metadata filtering indexes for scoped retrieval
CREATE INDEX idx_chunks_project ON chunks(project_name);
CREATE INDEX idx_chunks_content_type ON chunks(content_type);
CREATE INDEX idx_chunks_module ON chunks(module_name);

-- ============================================================================
-- 审核记录表 (Review Records)
-- Persists human review decisions for the Human-in-the-Loop mechanism
-- ============================================================================
CREATE TABLE review_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(256) NOT NULL,
    workflow_id VARCHAR(256) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    content JSONB NOT NULL,
    reviewer_id VARCHAR(200),
    decision VARCHAR(20),  -- approved, rejected, pending
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    decided_at TIMESTAMP WITH TIME ZONE,
    timeout_seconds INTEGER NOT NULL DEFAULT 3600
);

-- ============================================================================
-- 工作流执行日志表 (Workflow Execution Logs)
-- Records each agent invocation within a workflow for observability
-- ============================================================================
CREATE TABLE workflow_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id VARCHAR(256) NOT NULL,
    correlation_id VARCHAR(256) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    model_used VARCHAR(100),
    token_count JSONB,  -- {"input": N, "output": M}
    latency_ms FLOAT,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_workflow_logs_correlation ON workflow_logs(correlation_id);
CREATE INDEX idx_workflow_logs_workflow ON workflow_logs(workflow_id);

-- ============================================================================
-- 索引更新日志表 (Index Update Logs)
-- Tracks all index operations for version management and auditing
-- ============================================================================
CREATE TABLE index_update_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation VARCHAR(20) NOT NULL,  -- add, update, delete
    affected_documents TEXT[] NOT NULL,
    chunks_added INTEGER DEFAULT 0,
    chunks_removed INTEGER DEFAULT 0,
    chunks_updated INTEGER DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
