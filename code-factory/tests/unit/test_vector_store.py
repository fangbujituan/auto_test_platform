"""Unit tests for PGVectorStore implementation.

Tests the vector store logic using mocked asyncpg connections.
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from rag.vector_store import PGVectorStore, _format_embedding
from src.core.models import EmbeddingRecord, SearchResult


def _make_mock_pool(conn=None):
    """Create a mock asyncpg pool with proper async context manager for acquire()."""
    if conn is None:
        conn = AsyncMock()

    pool = MagicMock()

    @asynccontextmanager
    async def mock_acquire():
        yield conn

    pool.acquire = mock_acquire
    return pool, conn


class TestFormatEmbedding:
    """Tests for the _format_embedding helper function."""

    def test_formats_simple_vector(self):
        embedding = [0.1, 0.2, 0.3]
        result = _format_embedding(embedding)
        assert result == "[0.1,0.2,0.3]"

    def test_formats_empty_vector(self):
        result = _format_embedding([])
        assert result == "[]"

    def test_formats_single_element(self):
        result = _format_embedding([1.0])
        assert result == "[1.0]"

    def test_formats_negative_values(self):
        result = _format_embedding([-0.5, 0.0, 0.5])
        assert result == "[-0.5,0.0,0.5]"


class TestPGVectorStoreInit:
    """Tests for PGVectorStore initialization."""

    def test_raises_if_no_pool_or_dsn(self):
        with pytest.raises(ValueError, match="Either 'pool' or 'dsn' must be provided"):
            PGVectorStore()

    def test_accepts_pool(self):
        mock_pool = MagicMock()
        store = PGVectorStore(pool=mock_pool)
        assert store._pool is mock_pool

    def test_accepts_dsn(self):
        store = PGVectorStore(dsn="postgresql://localhost/test")
        assert store._dsn == "postgresql://localhost/test"
        assert store._pool is None


class TestPGVectorStoreUpsert:
    """Tests for the upsert method."""

    @pytest.mark.asyncio
    async def test_upsert_empty_list_returns_zero(self):
        pool, _ = _make_mock_pool()
        store = PGVectorStore(pool=pool)
        result = await store.upsert([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_upsert_single_record(self):
        conn = AsyncMock()
        # Mock the transaction context manager
        transaction = AsyncMock()
        conn.transaction = MagicMock(return_value=transaction)
        transaction.__aenter__ = AsyncMock(return_value=transaction)
        transaction.__aexit__ = AsyncMock(return_value=False)

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        record = EmbeddingRecord(
            chunk_id="chunk-001",
            embedding=[0.1, 0.2, 0.3],
            content="Test content",
            metadata={
                "source_path": "/docs/test.md",
                "token_count": 10,
                "chunk_position": 0,
                "project_name": "test-project",
                "module_name": "auth",
                "document_version": "1.0",
                "content_type": "requirement",
            },
        )

        result = await store.upsert([record])
        assert result == 1
        conn.execute.assert_called_once()

        # Verify the SQL contains ON CONFLICT DO UPDATE
        call_args = conn.execute.call_args[0]
        sql = call_args[0]
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql

    @pytest.mark.asyncio
    async def test_upsert_multiple_records(self):
        conn = AsyncMock()
        transaction = AsyncMock()
        conn.transaction = MagicMock(return_value=transaction)
        transaction.__aenter__ = AsyncMock(return_value=transaction)
        transaction.__aexit__ = AsyncMock(return_value=False)

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        records = [
            EmbeddingRecord(
                chunk_id=f"chunk-{i:03d}",
                embedding=[0.1 * i, 0.2 * i, 0.3 * i],
                content=f"Content {i}",
                metadata={
                    "source_path": "/docs/test.md",
                    "token_count": 10,
                    "chunk_position": i,
                    "project_name": "proj",
                    "module_name": "mod",
                    "document_version": "1.0",
                    "content_type": "api",
                },
            )
            for i in range(3)
        ]

        result = await store.upsert(records)
        assert result == 3
        assert conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_upsert_passes_correct_parameters(self):
        conn = AsyncMock()
        transaction = AsyncMock()
        conn.transaction = MagicMock(return_value=transaction)
        transaction.__aenter__ = AsyncMock(return_value=transaction)
        transaction.__aexit__ = AsyncMock(return_value=False)

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        record = EmbeddingRecord(
            chunk_id="test-id",
            embedding=[1.0, 2.0],
            content="Hello world",
            metadata={
                "source_path": "/src/main.py",
                "token_count": 5,
                "chunk_position": 2,
                "project_name": "myproj",
                "module_name": "core",
                "document_version": "2.0",
                "content_type": "code_specification",
            },
        )

        await store.upsert([record])

        call_args = conn.execute.call_args[0]
        # Positional params after SQL: chunk_id, source_path, content, embedding_str, ...
        assert call_args[1] == "test-id"
        assert call_args[2] == "/src/main.py"
        assert call_args[3] == "Hello world"
        assert call_args[4] == "[1.0,2.0]"


class TestPGVectorStoreSearch:
    """Tests for the search method."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "id": "chunk-001",
                "content": "Test content",
                "project_name": "proj",
                "module_name": "mod",
                "document_version": "1.0",
                "content_type": "requirement",
                "chunk_position": 0,
                "token_count": 10,
                "similarity_score": 0.95,
            }
        ]

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        results = await store.search(query_embedding=[0.1, 0.2, 0.3], top_k=5)

        assert len(results) == 1
        assert results[0].chunk_id == "chunk-001"
        assert results[0].content == "Test content"
        assert results[0].similarity_score == 0.95
        assert results[0].metadata["project_name"] == "proj"
        assert results[0].metadata["module_name"] == "mod"
        assert results[0].metadata["content_type"] == "requirement"

    @pytest.mark.asyncio
    async def test_search_with_metadata_filter(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        await store.search(
            query_embedding=[0.1, 0.2, 0.3],
            top_k=3,
            metadata_filter={"project_name": "my-project", "content_type": "api"},
        )

        # Verify the query was called with filter parameters
        call_args = conn.fetch.call_args[0]
        query = call_args[0]
        assert "WHERE" in query
        assert "project_name = $4" in query
        assert "content_type = $5" in query
        # Check params include filter values
        params = call_args[1:]
        assert "my-project" in params
        assert "api" in params

    @pytest.mark.asyncio
    async def test_search_with_all_filters(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        await store.search(
            query_embedding=[0.1],
            top_k=2,
            metadata_filter={
                "project_name": "proj-a",
                "module_name": "auth",
                "content_type": "requirement",
            },
        )

        call_args = conn.fetch.call_args[0]
        query = call_args[0]
        assert "project_name = $4" in query
        assert "module_name = $5" in query
        assert "content_type = $6" in query

    @pytest.mark.asyncio
    async def test_search_without_filter(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        await store.search(query_embedding=[0.1, 0.2, 0.3], top_k=10)

        call_args = conn.fetch.call_args[0]
        query = call_args[0]
        assert "WHERE" not in query

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        results = await store.search(query_embedding=[0.1, 0.2, 0.3])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_uses_cosine_similarity(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        await store.search(query_embedding=[0.5, 0.5], top_k=3)

        call_args = conn.fetch.call_args[0]
        query = call_args[0]
        # Verify cosine similarity formula
        assert "1 - (embedding <=> $1::vector)" in query
        # Verify ordering by distance (ascending = most similar first)
        assert "ORDER BY embedding <=> $2::vector" in query


class TestPGVectorStoreDeleteByDocument:
    """Tests for the delete_by_document method."""

    @pytest.mark.asyncio
    async def test_delete_returns_count(self):
        conn = AsyncMock()
        conn.execute.return_value = "DELETE 5"

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        result = await store.delete_by_document("/docs/test.md")
        assert result == 5

    @pytest.mark.asyncio
    async def test_delete_no_matching_document(self):
        conn = AsyncMock()
        conn.execute.return_value = "DELETE 0"

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        result = await store.delete_by_document("/docs/nonexistent.md")
        assert result == 0

    @pytest.mark.asyncio
    async def test_delete_uses_source_path_param(self):
        conn = AsyncMock()
        conn.execute.return_value = "DELETE 3"

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        await store.delete_by_document("/path/to/doc.pdf")

        call_args = conn.execute.call_args[0]
        # The source_path should be passed as a parameter
        assert "/path/to/doc.pdf" in call_args

    @pytest.mark.asyncio
    async def test_delete_uses_subquery_on_documents_table(self):
        conn = AsyncMock()
        conn.execute.return_value = "DELETE 1"

        pool, _ = _make_mock_pool(conn)
        store = PGVectorStore(pool=pool)

        await store.delete_by_document("/any/path.md")

        call_args = conn.execute.call_args[0]
        sql = call_args[0]
        assert "DELETE FROM chunks" in sql
        assert "documents" in sql
        assert "source_path" in sql


class TestPGVectorStoreClose:
    """Tests for the close method."""

    @pytest.mark.asyncio
    async def test_close_closes_pool(self):
        mock_pool = AsyncMock()
        store = PGVectorStore(pool=mock_pool)

        await store.close()
        mock_pool.close.assert_called_once()
        assert store._pool is None

    @pytest.mark.asyncio
    async def test_close_when_no_pool(self):
        store = PGVectorStore(dsn="postgresql://localhost/test")
        # Should not raise
        await store.close()


class TestPGVectorStoreGetPool:
    """Tests for the _get_pool method."""

    @pytest.mark.asyncio
    async def test_get_pool_returns_existing_pool(self):
        mock_pool = MagicMock()
        store = PGVectorStore(pool=mock_pool)

        result = await store._get_pool()
        assert result is mock_pool

    @pytest.mark.asyncio
    @patch("rag.vector_store.asyncpg.create_pool", new_callable=AsyncMock)
    async def test_get_pool_creates_pool_from_dsn(self, mock_create_pool):
        new_pool = MagicMock()
        mock_create_pool.return_value = new_pool

        store = PGVectorStore(dsn="postgresql://localhost/test")
        result = await store._get_pool()

        assert result is new_pool
        mock_create_pool.assert_called_once_with(dsn="postgresql://localhost/test")
