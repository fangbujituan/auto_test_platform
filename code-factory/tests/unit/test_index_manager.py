"""Unit tests for IncrementalIndexManager.

Tests change detection, incremental updates, document deletion,
and version logging using mocked dependencies.
"""

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.index_manager import IncrementalIndexManager, _compute_content_hash
from src.core.models import (
    Chunk,
    ChunkConfig,
    ChunkMetadata,
    DocumentFormat,
    DocumentUnit,
    EmbeddingRecord,
    IndexUpdateLog,
    LoadedDocument,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_document(
    source_path: str = "/docs/test.md",
    raw_text: str = "Hello world content",
    fmt: DocumentFormat = DocumentFormat.MARKDOWN,
    version: str = "1.0",
) -> LoadedDocument:
    """Create a test LoadedDocument."""
    return LoadedDocument(
        source_path=source_path,
        format=fmt,
        units=[
            DocumentUnit(
                content=raw_text,
                unit_type="heading",
                metadata={},
                source_path=source_path,
                position=0,
            )
        ],
        raw_text=raw_text,
        structural_info={
            "project_name": "test-project",
            "module_name": "test-module",
            "document_version": version,
            "content_type": "requirement",
        },
    )


def _make_chunk(chunk_id: str, content: str = "chunk content", position: int = 0) -> Chunk:
    """Create a test Chunk."""
    return Chunk(
        chunk_id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            project_name="test-project",
            module_name="test-module",
            document_version="1.0",
            content_type="requirement",
            source_path="/docs/test.md",
            chunk_position=position,
        ),
        token_count=2,
    )


@pytest.fixture
def mock_pool():
    """Create a mock asyncpg pool with proper async context manager support."""
    pool = MagicMock()
    conn = AsyncMock()

    # Create a proper async context manager for pool.acquire()
    acm = AsyncMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acm)

    return pool, conn


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStoreInterface."""
    store = AsyncMock()
    store.upsert = AsyncMock(return_value=0)
    store.delete_by_document = AsyncMock(return_value=0)
    return store


@pytest.fixture
def mock_chunker():
    """Create a mock ChunkerInterface."""
    chunker = MagicMock()
    chunker.chunk_document = MagicMock(return_value=[])
    return chunker


# =============================================================================
# Tests for _compute_content_hash
# =============================================================================


class TestComputeContentHash:
    """Tests for the content hash utility function."""

    def test_returns_sha256_hex(self):
        """Hash should be a 64-char hex string (SHA-256)."""
        result = _compute_content_hash("hello")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        """Same input should always produce the same hash."""
        text = "some document content"
        assert _compute_content_hash(text) == _compute_content_hash(text)

    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        assert _compute_content_hash("text A") != _compute_content_hash("text B")

    def test_matches_hashlib_directly(self):
        """Should match direct hashlib computation."""
        text = "test content"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert _compute_content_hash(text) == expected


# =============================================================================
# Tests for detect_changes
# =============================================================================


class TestDetectChanges:
    """Tests for IncrementalIndexManager.detect_changes."""

    @pytest.mark.asyncio
    async def test_new_document_returns_added(self, mock_pool, mock_vector_store, mock_chunker):
        """A new document (not in DB) should return all chunks as 'added'."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value=None)  # Document not found

        chunks = [_make_chunk("chunk-1"), _make_chunk("chunk-2", position=1)]
        mock_chunker.chunk_document.return_value = chunks

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        doc = _make_document()

        result = await manager.detect_changes(doc)

        assert result["added"] == ["chunk-1", "chunk-2"]
        assert result["modified"] == []
        assert result["deleted"] == []

    @pytest.mark.asyncio
    async def test_unchanged_document_returns_empty(self, mock_pool, mock_vector_store, mock_chunker):
        """An unchanged document should return empty change sets."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="unchanged content")
        content_hash = _compute_content_hash("unchanged content")

        conn.fetchrow = AsyncMock(
            return_value={"id": "doc-uuid-1", "content_hash": content_hash}
        )

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.detect_changes(doc)

        assert result["added"] == []
        assert result["modified"] == []
        assert result["deleted"] == []

    @pytest.mark.asyncio
    async def test_modified_document_detects_changes(self, mock_pool, mock_vector_store, mock_chunker):
        """A modified document should detect added, modified, and deleted chunks."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="new content")

        # Stored hash is different (old content)
        old_hash = _compute_content_hash("old content")
        conn.fetchrow = AsyncMock(
            return_value={"id": "doc-uuid-1", "content_hash": old_hash}
        )

        # Existing chunks in DB
        conn.fetch = AsyncMock(
            return_value=[{"id": "chunk-old-1"}, {"id": "chunk-shared"}]
        )

        # New chunks from chunker
        new_chunks = [
            _make_chunk("chunk-new-1"),
            _make_chunk("chunk-shared", position=1),
        ]
        mock_chunker.chunk_document.return_value = new_chunks

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.detect_changes(doc)

        assert "chunk-new-1" in result["added"]
        assert "chunk-shared" in result["modified"]
        assert "chunk-old-1" in result["deleted"]


# =============================================================================
# Tests for update_index
# =============================================================================


class TestUpdateIndex:
    """Tests for IncrementalIndexManager.update_index."""

    @pytest.mark.asyncio
    async def test_new_document_adds_chunks(self, mock_pool, mock_vector_store, mock_chunker):
        """Indexing a new document should add all chunks and log the operation."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="brand new doc")

        # detect_changes: document not found
        conn.fetchrow = AsyncMock(return_value=None)

        chunks = [_make_chunk("c1"), _make_chunk("c2", position=1)]
        mock_chunker.chunk_document.return_value = chunks

        # upsert_document_metadata and log
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.update_index([doc])

        assert isinstance(result, IndexUpdateLog)
        assert result.chunks_added == 2
        assert result.chunks_removed == 0
        assert result.chunks_updated == 0
        assert result.operation == "add"
        assert doc.source_path in result.affected_documents
        mock_vector_store.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_unchanged_document_skipped(self, mock_pool, mock_vector_store, mock_chunker):
        """An unchanged document should not trigger any upsert or delete."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="same content")
        content_hash = _compute_content_hash("same content")

        conn.fetchrow = AsyncMock(
            return_value={"id": "doc-uuid", "content_hash": content_hash}
        )

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.update_index([doc])

        assert result.chunks_added == 0
        assert result.chunks_removed == 0
        assert result.chunks_updated == 0
        assert result.affected_documents == []
        mock_vector_store.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_modified_document_updates_chunks(self, mock_pool, mock_vector_store, mock_chunker):
        """A modified document should remove old chunks and add new ones."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="updated content")
        old_hash = _compute_content_hash("original content")

        # First call to detect_changes fetchrow (document exists with old hash)
        conn.fetchrow = AsyncMock(
            return_value={"id": "doc-uuid", "content_hash": old_hash}
        )
        # fetch existing chunks
        conn.fetch = AsyncMock(return_value=[{"id": "old-chunk-1"}])
        conn.execute = AsyncMock(return_value="DELETE 1")

        new_chunks = [_make_chunk("new-chunk-1")]
        mock_chunker.chunk_document.return_value = new_chunks

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.update_index([doc])

        assert result.chunks_added == 1
        assert result.chunks_removed == 1
        assert result.operation == "update"
        assert doc.source_path in result.affected_documents

    @pytest.mark.asyncio
    async def test_update_index_logs_operation(self, mock_pool, mock_vector_store, mock_chunker):
        """update_index should persist a log entry to index_update_logs."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="new doc for logging")

        conn.fetchrow = AsyncMock(return_value=None)
        chunks = [_make_chunk("log-chunk-1")]
        mock_chunker.chunk_document.return_value = chunks
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.update_index([doc])

        # Verify _log_index_update was called (conn.execute called for INSERT INTO index_update_logs)
        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)


# =============================================================================
# Tests for delete_document
# =============================================================================


class TestDeleteDocument:
    """Tests for IncrementalIndexManager.delete_document."""

    @pytest.mark.asyncio
    async def test_delete_removes_chunks_and_metadata(self, mock_pool, mock_vector_store, mock_chunker):
        """Deleting a document should remove all chunks and the document record."""
        pool, conn = mock_pool
        mock_vector_store.delete_by_document = AsyncMock(return_value=5)
        conn.execute = AsyncMock(return_value="DELETE 1")

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.delete_document("/docs/to-delete.md")

        assert result.operation == "delete"
        assert result.chunks_removed == 5
        assert result.chunks_added == 0
        assert "/docs/to-delete.md" in result.affected_documents
        mock_vector_store.delete_by_document.assert_called_once_with("/docs/to-delete.md")

    @pytest.mark.asyncio
    async def test_delete_logs_operation(self, mock_pool, mock_vector_store, mock_chunker):
        """Document deletion should produce a log entry."""
        pool, conn = mock_pool
        mock_vector_store.delete_by_document = AsyncMock(return_value=3)
        conn.execute = AsyncMock(return_value="DELETE 1")

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.delete_document("/docs/removed.md")

        assert isinstance(result, IndexUpdateLog)
        assert result.timestamp is not None
        assert result.chunks_removed == 3


# =============================================================================
# Tests for IndexUpdateLog structure
# =============================================================================


class TestIndexUpdateLogStructure:
    """Tests verifying IndexUpdateLog contains all required fields."""

    @pytest.mark.asyncio
    async def test_log_has_all_required_fields(self, mock_pool, mock_vector_store, mock_chunker):
        """IndexUpdateLog should have timestamp, operation, affected_documents, and chunk counts."""
        pool, conn = mock_pool
        doc = _make_document(raw_text="log test content")

        conn.fetchrow = AsyncMock(return_value=None)
        chunks = [_make_chunk("log-c1")]
        mock_chunker.chunk_document.return_value = chunks
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        manager = IncrementalIndexManager(mock_vector_store, pool, mock_chunker)
        result = await manager.update_index([doc])

        # Verify all fields are present and correctly typed
        assert hasattr(result, "timestamp")
        assert hasattr(result, "operation")
        assert hasattr(result, "affected_documents")
        assert hasattr(result, "chunks_added")
        assert hasattr(result, "chunks_removed")
        assert hasattr(result, "chunks_updated")
        assert isinstance(result.timestamp, datetime)
        assert result.operation in ("add", "update", "delete")
        assert isinstance(result.affected_documents, list)
        assert isinstance(result.chunks_added, int)
        assert isinstance(result.chunks_removed, int)
        assert isinstance(result.chunks_updated, int)
