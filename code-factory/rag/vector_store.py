"""基于 PGVector 的向量存储实现 / PGVector-based Vector Store implementation.

使用带有 pgvector 扩展的 PostgreSQL 提供异步向量存储和相似度搜索。
Provides async vector storage and similarity search using PostgreSQL with pgvector extension.
使用 asyncpg 进行高性能异步数据库操作。
Uses asyncpg for high-performance async database operations.

需求 / Requirements: 7.1 (PGVector 作为主向量数据库 / PGVector as primary vector database), 7.2 (存储嵌入向量及元数据 / store embeddings with metadata),
7.3 (Top-K 相似度搜索 / top-K similarity search), 7.4 (带元数据过滤的快速相似度搜索 / fast similarity search with metadata filtering)
"""

from typing import Any, Optional

import asyncpg

from src.core.interfaces import VectorStoreInterface
from src.core.models import EmbeddingRecord, SearchResult


class PGVectorStore(VectorStoreInterface):
    """基于 PGVector 的向量存储，用于嵌入向量存储和相似度搜索 / PGVector-based vector store for embedding storage and similarity search.

    使用 asyncpg 连接池进行异步 PostgreSQL 操作。
    Uses asyncpg connection pool for async PostgreSQL operations.
    支持 upsert、带元数据过滤的余弦相似度搜索以及文档级删除。
    Supports upsert, cosine similarity search with metadata filtering,
    and document-level deletion.
    """

    def __init__(self, pool: Optional[asyncpg.Pool] = None, dsn: Optional[str] = None):
        """Initialize PGVectorStore with a connection pool or DSN.

        Args:
            pool: An existing asyncpg connection pool. If provided, dsn is ignored.
            dsn: A PostgreSQL connection string. Used to create a pool if pool is None.

        Raises:
            ValueError: If neither pool nor dsn is provided.
        """
        if pool is None and dsn is None:
            raise ValueError("Either 'pool' or 'dsn' must be provided.")
        self._pool = pool
        self._dsn = dsn

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create the connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(dsn=self._dsn)
        return self._pool

    async def upsert(self, records: list[EmbeddingRecord]) -> int:
        """Insert or update embedding records using ON CONFLICT DO UPDATE.

        Args:
            records: List of EmbeddingRecord objects to upsert.

        Returns:
            Number of records upserted.
        """
        if not records:
            return 0

        pool = await self._get_pool()

        upserted = 0
        async with pool.acquire() as conn:
            # Use a transaction for batch upsert
            async with conn.transaction():
                for record in records:
                    embedding_str = _format_embedding(record.embedding)
                    metadata = record.metadata

                    await conn.execute(
                        """
                        INSERT INTO chunks (id, document_id, content, embedding, token_count,
                                           chunk_position, project_name, module_name,
                                           document_version, content_type)
                        VALUES ($1,
                                (SELECT id FROM documents WHERE source_path = $2),
                                $3,
                                $4::vector,
                                $5,
                                $6,
                                $7,
                                $8,
                                $9,
                                $10)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            token_count = EXCLUDED.token_count,
                            chunk_position = EXCLUDED.chunk_position,
                            project_name = EXCLUDED.project_name,
                            module_name = EXCLUDED.module_name,
                            document_version = EXCLUDED.document_version,
                            content_type = EXCLUDED.content_type
                        """,
                        record.chunk_id,
                        metadata.get("source_path", ""),
                        record.content,
                        embedding_str,
                        metadata.get("token_count", 0),
                        metadata.get("chunk_position", 0),
                        metadata.get("project_name"),
                        metadata.get("module_name"),
                        metadata.get("document_version"),
                        metadata.get("content_type"),
                    )
                    upserted += 1

        return upserted

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """Perform cosine similarity search with optional metadata filtering.

        Uses `1 - (embedding <=> query_embedding)` for cosine similarity score.
        Results are ordered by descending similarity.

        Args:
            query_embedding: The query vector to search against.
            top_k: Number of top results to return (default 5).
            metadata_filter: Optional dict with keys 'project_name', 'module_name',
                           'content_type' to filter results.

        Returns:
            List of SearchResult objects ordered by descending similarity score.
        """
        pool = await self._get_pool()

        embedding_str = _format_embedding(query_embedding)

        # Build query with optional metadata filters
        where_clauses: list[str] = []
        params: list[Any] = [embedding_str, embedding_str, top_k]
        param_idx = 4  # Next parameter index (1-based)

        if metadata_filter:
            if "project_name" in metadata_filter:
                where_clauses.append(f"project_name = ${param_idx}")
                params.append(metadata_filter["project_name"])
                param_idx += 1

            if "module_name" in metadata_filter:
                where_clauses.append(f"module_name = ${param_idx}")
                params.append(metadata_filter["module_name"])
                param_idx += 1

            if "content_type" in metadata_filter:
                where_clauses.append(f"content_type = ${param_idx}")
                params.append(metadata_filter["content_type"])
                param_idx += 1

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT id, content, project_name, module_name, document_version,
                   content_type, chunk_position, token_count,
                   1 - (embedding <=> $1::vector) AS similarity_score
            FROM chunks
            {where_sql}
            ORDER BY embedding <=> $2::vector
            LIMIT $3
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            metadata = {
                "project_name": row["project_name"],
                "module_name": row["module_name"],
                "document_version": row["document_version"],
                "content_type": row["content_type"],
                "chunk_position": row["chunk_position"],
                "token_count": row["token_count"],
            }
            results.append(
                SearchResult(
                    chunk_id=row["id"],
                    content=row["content"],
                    metadata=metadata,
                    similarity_score=float(row["similarity_score"]),
                )
            )

        return results

    async def delete_by_document(self, source_path: str) -> int:
        """Delete all chunks belonging to a document identified by source_path.

        Joins with the documents table to find the document_id, then deletes
        all chunks referencing that document.

        Args:
            source_path: The source path of the document whose chunks to delete.

        Returns:
            Number of chunks deleted.
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM chunks
                WHERE document_id = (
                    SELECT id FROM documents WHERE source_path = $1
                )
                """,
                source_path,
            )
            # asyncpg returns a status string like "DELETE N"
            count = int(result.split(" ")[-1])

        return count

    async def close(self) -> None:
        """Close the connection pool if it was created internally."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def _format_embedding(embedding: list[float]) -> str:
    """Format an embedding vector as a pgvector-compatible string.

    Args:
        embedding: List of float values representing the vector.

    Returns:
        String in pgvector format, e.g. '[0.1,0.2,0.3]'
    """
    return "[" + ",".join(str(v) for v in embedding) + "]"
