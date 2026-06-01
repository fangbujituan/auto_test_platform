"""增量索引管理器实现 / Incremental Index Manager implementation.

通过 SHA-256 内容哈希检测文档变更来管理知识库索引更新，
Manages knowledge base index updates by detecting document changes via SHA-256
执行增量块更新（添加/修改/删除），并记录所有索引操作以进行版本跟踪。
content hashing, performing incremental chunk updates (add/modify/delete), and
logging all index operations for version tracking.

需求 / Requirements: 7.5 (增量更新 / incremental updates), 7.6 (变更检测和选择性重新索引 / change detection and selective re-indexing),
7.7 (文档删除及完整块移除 / document deletion with full chunk removal), 7.8 (版本日志 / version logging)
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from src.core.interfaces import ChunkerInterface, IndexManagerInterface, VectorStoreInterface
from src.core.models import ChunkConfig, EmbeddingRecord, IndexUpdateLog, LoadedDocument


def _compute_content_hash(raw_text: str) -> str:
    """Compute SHA-256 hash of document raw text for change detection.

    Args:
        raw_text: The full raw text content of the document.

    Returns:
        64-character hex string of the SHA-256 digest.
    """
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


class IncrementalIndexManager(IndexManagerInterface):
    """增量索引管理器，检测文档变更并仅更新受影响的块 / Incremental index manager that detects document changes and updates only affected chunks.

    使用 SHA-256 内容哈希检测修改。协调以下组件：
    Uses SHA-256 content hashing to detect modifications. Coordinates between:
    - VectorStoreInterface: 用于块存储/删除操作 / for chunk storage/deletion operations
    - ChunkerInterface: 用于重新分块修改后的文档 / for re-chunking modified documents
    - asyncpg pool: 用于直接查询 documents/index_update_logs 表 / for direct DB queries to documents/index_update_logs tables

    关键行为 / Key behaviors:
    - detect_changes: 比较文档内容哈希与存储的哈希 / compares document content hash against stored hash
    - update_index: 执行块的增量添加/修改/删除 / performs incremental add/modify/delete of chunks
    - 将每个索引操作记录到 index_update_logs 表 / Logs every index operation to the index_update_logs table
    """

    def __init__(
        self,
        vector_store: VectorStoreInterface,
        pool: asyncpg.Pool,
        chunker: ChunkerInterface,
        chunk_config: Optional[ChunkConfig] = None,
    ):
        """Initialize IncrementalIndexManager.

        Args:
            vector_store: Vector store for chunk upsert/delete operations.
            pool: asyncpg connection pool for direct DB queries.
            chunker: Chunker for splitting documents into chunks.
            chunk_config: Optional chunk configuration. Defaults to ChunkConfig().
        """
        self._vector_store = vector_store
        self._pool = pool
        self._chunker = chunker
        self._chunk_config = chunk_config or ChunkConfig()

    async def detect_changes(self, document: LoadedDocument) -> dict[str, list[str]]:
        """Detect changes in a document by comparing content hash.

        Computes SHA-256 of document.raw_text and compares with the stored
        content_hash in the documents table.

        Returns:
            A dict with keys "added", "modified", "deleted":
            - "added": list of chunk_ids for new chunks (document is new)
            - "modified": list of chunk_ids for chunks that need updating (document changed)
            - "deleted": list of chunk_ids for chunks to remove (document changed or removed)

        If the document is new (not in DB), all chunks are "added".
        If the document is unchanged, all lists are empty.
        If the document is modified, existing chunks are "deleted" and new chunks are "added".
        """
        new_hash = _compute_content_hash(document.raw_text)

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, content_hash FROM documents WHERE source_path = $1",
                document.source_path,
            )

        if row is None:
            # Document is new — all chunks will be added
            new_chunks = self._chunker.chunk_document(document, self._chunk_config)
            return {
                "added": [chunk.chunk_id for chunk in new_chunks],
                "modified": [],
                "deleted": [],
            }

        stored_hash = row["content_hash"]

        if stored_hash == new_hash:
            # Document unchanged — no changes needed
            return {"added": [], "modified": [], "deleted": []}

        # Document modified — get existing chunk IDs and compute new chunks
        document_id = row["id"]

        async with self._pool.acquire() as conn:
            existing_rows = await conn.fetch(
                "SELECT id FROM chunks WHERE document_id = $1",
                document_id,
            )

        existing_chunk_ids = [r["id"] for r in existing_rows]
        new_chunks = self._chunker.chunk_document(document, self._chunk_config)
        new_chunk_ids = [chunk.chunk_id for chunk in new_chunks]

        # Determine which chunks are truly new, modified, or deleted
        existing_set = set(existing_chunk_ids)
        new_set = set(new_chunk_ids)

        added = [cid for cid in new_chunk_ids if cid not in existing_set]
        deleted = [cid for cid in existing_chunk_ids if cid not in new_set]
        # Chunks with same ID but potentially different content are "modified"
        modified = [cid for cid in new_chunk_ids if cid in existing_set]

        return {"added": added, "modified": modified, "deleted": deleted}

    async def update_index(self, documents: list[LoadedDocument]) -> IndexUpdateLog:
        """Incrementally update the index for a list of documents.

        For each document:
        1. Detect changes (new, modified, unchanged)
        2. Remove outdated chunks
        3. Add new/modified chunks via vector store upsert
        4. Update the documents table metadata

        Logs the operation to the index_update_logs table.

        Args:
            documents: List of LoadedDocument objects to index.

        Returns:
            IndexUpdateLog with counts of chunks added, removed, and updated.
        """
        total_added = 0
        total_removed = 0
        total_updated = 0
        affected_documents: list[str] = []

        for document in documents:
            new_hash = _compute_content_hash(document.raw_text)
            changes = await self.detect_changes(document)

            # Skip if no changes
            if not changes["added"] and not changes["modified"] and not changes["deleted"]:
                continue

            affected_documents.append(document.source_path)

            # Remove deleted chunks
            if changes["deleted"]:
                await self._delete_chunks_by_ids(changes["deleted"])
                total_removed += len(changes["deleted"])

            # Chunk the document for new/modified content
            new_chunks = self._chunker.chunk_document(document, self._chunk_config)

            # Determine which chunks to upsert (added + modified)
            chunks_to_upsert_ids = set(changes["added"]) | set(changes["modified"])
            chunks_to_upsert = [c for c in new_chunks if c.chunk_id in chunks_to_upsert_ids]

            if chunks_to_upsert:
                # Build EmbeddingRecords (embedding will be empty — caller is responsible
                # for embedding generation before calling update_index, or the vector store
                # handles it). For now we store with empty embeddings as placeholder.
                records = []
                for chunk in chunks_to_upsert:
                    record = EmbeddingRecord(
                        chunk_id=chunk.chunk_id,
                        embedding=[],  # Embedding generation is external
                        content=chunk.content,
                        metadata={
                            "source_path": document.source_path,
                            "token_count": chunk.token_count,
                            "chunk_position": chunk.metadata.chunk_position,
                            "project_name": chunk.metadata.project_name,
                            "module_name": chunk.metadata.module_name,
                            "document_version": chunk.metadata.document_version,
                            "content_type": chunk.metadata.content_type,
                        },
                    )
                    records.append(record)

                await self._vector_store.upsert(records)
                total_added += len(changes["added"])
                total_updated += len(changes["modified"])

            # Update or insert document metadata in the documents table
            await self._upsert_document_metadata(document, new_hash)

        # Determine operation type
        if total_removed > 0 and total_added > 0:
            operation = "update"
        elif total_removed > 0:
            operation = "delete"
        else:
            operation = "add"

        # Log the index update operation
        log_entry = IndexUpdateLog(
            timestamp=datetime.now(timezone.utc),
            operation=operation,
            affected_documents=affected_documents,
            chunks_added=total_added,
            chunks_removed=total_removed,
            chunks_updated=total_updated,
        )

        await self._log_index_update(log_entry)

        return log_entry

    async def delete_document(self, source_path: str) -> IndexUpdateLog:
        """Delete a document and all its chunks from the index.

        Args:
            source_path: The source path of the document to delete.

        Returns:
            IndexUpdateLog recording the deletion operation.
        """
        # Delete chunks via vector store
        chunks_removed = await self._vector_store.delete_by_document(source_path)

        # Delete document metadata
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM documents WHERE source_path = $1",
                source_path,
            )

        log_entry = IndexUpdateLog(
            timestamp=datetime.now(timezone.utc),
            operation="delete",
            affected_documents=[source_path],
            chunks_added=0,
            chunks_removed=chunks_removed,
            chunks_updated=0,
        )

        await self._log_index_update(log_entry)

        return log_entry

    async def _delete_chunks_by_ids(self, chunk_ids: list[str]) -> None:
        """Delete specific chunks by their IDs.

        Args:
            chunk_ids: List of chunk IDs to delete.
        """
        if not chunk_ids:
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM chunks WHERE id = ANY($1::text[])",
                chunk_ids,
            )

    async def _upsert_document_metadata(
        self, document: LoadedDocument, content_hash: str
    ) -> None:
        """Insert or update document metadata in the documents table.

        Args:
            document: The loaded document.
            content_hash: SHA-256 hash of the document's raw_text.
        """
        version = document.structural_info.get("document_version", "1.0")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (source_path, format, version, content_hash, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (source_path) DO UPDATE SET
                    format = EXCLUDED.format,
                    version = EXCLUDED.version,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = NOW()
                """,
                document.source_path,
                document.format.value,
                version,
                content_hash,
            )

    async def _log_index_update(self, log_entry: IndexUpdateLog) -> None:
        """Persist an index update log entry to the index_update_logs table.

        Args:
            log_entry: The IndexUpdateLog to persist.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO index_update_logs
                    (operation, affected_documents, chunks_added, chunks_removed, chunks_updated, executed_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                log_entry.operation,
                log_entry.affected_documents,
                log_entry.chunks_added,
                log_entry.chunks_removed,
                log_entry.chunks_updated,
                log_entry.timestamp,
            )
