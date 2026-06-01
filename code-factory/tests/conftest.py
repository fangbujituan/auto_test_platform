"""Shared test configuration and fixtures for Code Factory.

Configures:
- Hypothesis profiles (ci: 200 examples, dev: 100 examples)
- pytest-asyncio for async test support
- Shared fixtures for database, mock models, sample documents
"""

from datetime import datetime
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, settings

from src.core.config import AppConfig, DatabaseConfig, Environment, ModelConfig
from src.core.interfaces import ModelRouterInterface, VectorStoreInterface
from src.core.models import (
    Chunk,
    ChunkMetadata,
    DocumentFormat,
    DocumentUnit,
    EmbeddingRecord,
    LLMRequest,
    LLMResponse,
    LoadedDocument,
    ModelTier,
    SearchResult,
    TaskComplexity,
)


# =============================================================================
# Hypothesis Profiles
# =============================================================================

# CI profile: more examples for thorough testing in CI pipelines
settings.register_profile(
    "ci",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Dev profile: fewer examples for faster local development iteration
settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Default profile: same as dev for general use
settings.load_profile("dev")


# =============================================================================
# Sample Document Fixtures
# =============================================================================


@pytest.fixture
def sample_markdown_document() -> LoadedDocument:
    """A LoadedDocument fixture with markdown content."""
    units = [
        DocumentUnit(
            content="# Introduction",
            unit_type="heading",
            metadata={"level": 1},
            source_path="docs/guide.md",
            position=0,
        ),
        DocumentUnit(
            content="This is the introduction paragraph with important details about the system.",
            unit_type="paragraph",
            metadata={},
            source_path="docs/guide.md",
            position=1,
        ),
        DocumentUnit(
            content="## Getting Started",
            unit_type="heading",
            metadata={"level": 2},
            source_path="docs/guide.md",
            position=2,
        ),
        DocumentUnit(
            content="```python\ndef hello():\n    return 'world'\n```",
            unit_type="code_block",
            metadata={"language": "python"},
            source_path="docs/guide.md",
            position=3,
        ),
        DocumentUnit(
            content="| Name | Type | Description |\n|------|------|-------------|\n| id | int | Primary key |\n| name | str | User name |",
            unit_type="table",
            metadata={"columns": ["Name", "Type", "Description"]},
            source_path="docs/guide.md",
            position=4,
        ),
    ]
    return LoadedDocument(
        source_path="docs/guide.md",
        format=DocumentFormat.MARKDOWN,
        units=units,
        raw_text="# Introduction\nThis is the introduction...\n## Getting Started\n...",
        structural_info={
            "project_name": "code-factory",
            "module_name": "documentation",
            "document_version": "1.0.0",
            "content_type": "requirement",
        },
    )


@pytest.fixture
def sample_python_document() -> LoadedDocument:
    """A LoadedDocument fixture with Python source code."""
    units = [
        DocumentUnit(
            content='"""Module docstring for the auth module."""',
            unit_type="docstring",
            metadata={"scope": "module"},
            source_path="src/auth/login.py",
            position=0,
        ),
        DocumentUnit(
            content="class AuthManager:\n    \"\"\"Manages authentication flows.\"\"\"\n\n    def __init__(self, secret_key: str):\n        self.secret_key = secret_key",
            unit_type="class",
            metadata={"name": "AuthManager", "bases": []},
            source_path="src/auth/login.py",
            position=1,
        ),
        DocumentUnit(
            content="def validate_token(token: str) -> bool:\n    \"\"\"Validate a JWT token.\"\"\"\n    return len(token) > 0",
            unit_type="function",
            metadata={"name": "validate_token", "args": ["token"]},
            source_path="src/auth/login.py",
            position=2,
        ),
    ]
    return LoadedDocument(
        source_path="src/auth/login.py",
        format=DocumentFormat.PYTHON,
        units=units,
        raw_text='"""Module docstring..."""\n\nclass AuthManager:\n    ...\n\ndef validate_token(token):\n    ...',
        structural_info={
            "project_name": "code-factory",
            "module_name": "auth",
            "document_version": "2.1.0",
            "content_type": "code_specification",
        },
    )


# =============================================================================
# Configuration Fixture
# =============================================================================


@pytest.fixture
def sample_config() -> AppConfig:
    """A valid AppConfig fixture for testing."""
    return AppConfig(
        environment=Environment.TESTING,
        database=DatabaseConfig(
            host="localhost",
            port=5432,
            database="code_factory_test",
            user="test_user",
            password="test_password",
        ),
        model=ModelConfig(
            local_endpoint="http://localhost:11434",
            cloud_api_keys={"anthropic": "sk-test-key", "deepseek": "ds-test-key"},
            default_temperature=0.7,
            default_max_tokens=4096,
        ),
        log_level="DEBUG",
        vector_store_collection="test_knowledge_base",
        similarity_threshold=0.7,
        review_timeout_seconds=60,
    )


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_vector_store() -> VectorStoreInterface:
    """A mock VectorStoreInterface for testing without a real database."""
    mock = AsyncMock(spec=VectorStoreInterface)

    # Default behaviors
    mock.upsert.return_value = 0
    mock.search.return_value = []
    mock.delete_by_document.return_value = 0

    return mock


@pytest.fixture
def mock_model_router() -> ModelRouterInterface:
    """A mock ModelRouterInterface for testing without real LLM calls."""
    mock = AsyncMock(spec=ModelRouterInterface)

    # Default: return a simple response for any route call
    mock.route.return_value = LLMResponse(
        content="Mock LLM response content",
        model_used="mock-model-v1",
        tier=ModelTier.LOCAL,
        token_count={"input": 50, "output": 25},
        latency_ms=100.0,
    )

    # Default: classify as medium complexity
    mock.classify_complexity.return_value = TaskComplexity.MEDIUM

    return mock


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """A list of Chunk objects for testing."""
    return [
        Chunk(
            chunk_id="chunk_001_abc123",
            content="This is the first chunk containing requirements for the login module.",
            metadata=ChunkMetadata(
                project_name="code-factory",
                module_name="auth",
                document_version="1.0.0",
                content_type="requirement",
                source_path="docs/requirements.md",
                chunk_position=0,
            ),
            token_count=12,
        ),
        Chunk(
            chunk_id="chunk_002_def456",
            content="def authenticate(user, password):\n    return check_credentials(user, password)",
            metadata=ChunkMetadata(
                project_name="code-factory",
                module_name="auth",
                document_version="1.0.0",
                content_type="code_specification",
                source_path="src/auth/login.py",
                chunk_position=0,
            ),
            token_count=8,
        ),
        Chunk(
            chunk_id="chunk_003_ghi789",
            content="The API endpoint /api/v1/login accepts POST requests with username and password fields.",
            metadata=ChunkMetadata(
                project_name="code-factory",
                module_name="api",
                document_version="2.0.0",
                content_type="api",
                source_path="docs/api-spec.yaml",
                chunk_position=3,
            ),
            token_count=15,
        ),
    ]


@pytest.fixture
def sample_embedding_records() -> list[EmbeddingRecord]:
    """A list of EmbeddingRecord objects for testing vector store operations."""
    return [
        EmbeddingRecord(
            chunk_id="emb_001",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5] * 10,  # 50-dim vector
            content="Requirements for user authentication module.",
            metadata={
                "project_name": "code-factory",
                "module_name": "auth",
                "content_type": "requirement",
                "source_path": "docs/requirements.md",
            },
        ),
        EmbeddingRecord(
            chunk_id="emb_002",
            embedding=[0.5, 0.4, 0.3, 0.2, 0.1] * 10,  # 50-dim vector
            content="Implementation of the login endpoint with JWT tokens.",
            metadata={
                "project_name": "code-factory",
                "module_name": "auth",
                "content_type": "api",
                "source_path": "docs/api-spec.yaml",
            },
        ),
        EmbeddingRecord(
            chunk_id="emb_003",
            embedding=[0.3, 0.3, 0.3, 0.3, 0.3] * 10,  # 50-dim vector
            content="Bug report: login fails when password contains special characters.",
            metadata={
                "project_name": "code-factory",
                "module_name": "auth",
                "content_type": "bug",
                "source_path": "docs/bugs/BUG-123.md",
            },
        ),
    ]
