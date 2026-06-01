"""语义分块器实现 / Semantic chunker implementation.

将文档分割成语义完整的块，具有以下感知能力：
Splits documents into semantically complete chunks with awareness of:
- 句子边界（绝不从句子中间分割）/ Sentence boundaries (never splits mid-sentence)
- 代码块（保持完整，最多 2048 个 token）/ Code blocks (kept intact up to 2048 tokens)
- 表格（行与标题上下文一起保留）/ Tables (rows kept with header context)
- 可配置的块大小及相邻块之间的重叠 / Configurable chunk size with overlap between adjacent chunks
"""

import hashlib
import re
from typing import Any

from src.core.interfaces import ChunkerInterface
from src.core.models import (
    Chunk,
    ChunkConfig,
    ChunkMetadata,
    DocumentUnit,
    LoadedDocument,
)


def count_tokens(text: str) -> int:
    """Count tokens using whitespace splitting as approximation."""
    return len(text.split())


def split_sentences(text: str) -> list[str]:
    """Split text into sentences at sentence boundaries.

    Sentence boundaries are detected as: `. `, `! `, `? ` followed by
    an uppercase letter or newline. Also splits on double newlines.
    """
    if not text.strip():
        return []

    # Split on sentence-ending punctuation followed by space and uppercase,
    # or on double newlines (paragraph boundaries).
    # We use a regex that keeps the delimiter with the preceding sentence.
    pattern = r'(?<=[.!?])\s+(?=[A-Z\n])|(?<=\n)\n+'
    parts = re.split(pattern, text)

    sentences = []
    for part in parts:
        stripped = part.strip()
        if stripped:
            sentences.append(stripped)

    return sentences


def _build_chunks_from_sentences(
    sentences: list[str],
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Build chunk texts from a list of sentences with overlap.

    Each chunk respects max_tokens. Overlap is achieved by including
    trailing sentences from the previous chunk at the start of the next.
    """
    if not sentences:
        return []

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_token_count = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        # If a single sentence exceeds max_tokens, it becomes its own chunk
        if sentence_tokens > max_tokens:
            # Flush current buffer first
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_token_count = 0
            chunks.append(sentence)
            continue

        # Check if adding this sentence would exceed the limit
        if current_token_count + sentence_tokens > max_tokens and current_sentences:
            # Flush current chunk
            chunks.append(" ".join(current_sentences))

            # Build overlap: take sentences from the end of current chunk
            # until we reach overlap_tokens
            overlap_sentences: list[str] = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = count_tokens(s)
                if overlap_count + s_tokens > overlap_tokens:
                    break
                overlap_sentences.insert(0, s)
                overlap_count += s_tokens

            current_sentences = overlap_sentences
            current_token_count = overlap_count

        current_sentences.append(sentence)
        current_token_count += sentence_tokens

    # Flush remaining
    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


def _split_code_block_at_boundaries(content: str, max_tokens: int) -> list[str]:
    """Split a large code block at function/class boundaries.

    Looks for lines starting with `def `, `class `, `function `, `async def `,
    or similar patterns to find logical split points.
    """
    lines = content.split("\n")
    boundary_pattern = re.compile(
        r"^\s*(def |class |async def |function |export function |export class |"
        r"public |private |protected )"
    )

    # Find boundary line indices (skip the first line if it's a boundary)
    boundaries = []
    for i, line in enumerate(lines):
        if i > 0 and boundary_pattern.match(line):
            boundaries.append(i)

    if not boundaries:
        # No logical boundaries found; split by line count approximation
        return _split_code_by_lines(content, max_tokens)

    # Split at boundaries, keeping each segment under max_tokens
    chunks: list[str] = []
    current_start = 0

    for boundary_idx in boundaries:
        segment = "\n".join(lines[current_start:boundary_idx])
        segment_tokens = count_tokens(segment)

        if segment_tokens > max_tokens and current_start < boundary_idx:
            # This segment is too large; add what we have and start fresh
            if segment.strip():
                chunks.append(segment)
            current_start = boundary_idx
        elif segment_tokens > 0:
            # Check if adding next segment would exceed limit
            next_boundary = boundaries[boundaries.index(boundary_idx) + 1] if boundary_idx != boundaries[-1] else len(lines)
            next_segment = "\n".join(lines[current_start:next_boundary])
            if count_tokens(next_segment) > max_tokens:
                if segment.strip():
                    chunks.append(segment)
                current_start = boundary_idx

    # Add remaining lines
    remaining = "\n".join(lines[current_start:])
    if remaining.strip():
        chunks.append(remaining)

    return chunks if chunks else [content]


def _split_code_by_lines(content: str, max_tokens: int) -> list[str]:
    """Fallback: split code by accumulating lines up to max_tokens."""
    lines = content.split("\n")
    chunks: list[str] = []
    current_lines: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_tokens = 0
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks if chunks else [content]


def _chunk_table_unit(unit: DocumentUnit, config: ChunkConfig) -> list[str]:
    """Chunk a table unit, keeping each row with its header.

    Strategy: The first row is treated as the header. Each subsequent row
    is paired with the header to form a chunk. If multiple rows fit within
    max_tokens together with the header, they are grouped.
    """
    lines = unit.content.strip().split("\n")
    if not lines:
        return []

    # Identify header: first non-empty line (and separator line if markdown table)
    header_lines: list[str] = []
    data_lines: list[str] = []
    header_done = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not header_done:
            header_lines.append(line)
            # Check if next line is a separator (e.g., |---|---|)
            if i + 1 < len(lines) and re.match(r"^\s*\|?[\s\-:]+\|", lines[i + 1]):
                header_lines.append(lines[i + 1])
                header_done = True
            elif i == 0:
                # If no separator follows, just use first line as header
                header_done = True
        else:
            # Skip separator lines that were already added
            if stripped and not re.match(r"^\s*\|?[\s\-:]+\|$", stripped):
                data_lines.append(line)

    if not data_lines:
        return [unit.content]

    header_text = "\n".join(header_lines)
    header_tokens = count_tokens(header_text)

    # Group data rows with header, respecting max_tokens
    chunks: list[str] = []
    current_rows: list[str] = []
    current_tokens = header_tokens

    for row in data_lines:
        row_tokens = count_tokens(row)
        if current_tokens + row_tokens > config.max_tokens and current_rows:
            chunk_text = header_text + "\n" + "\n".join(current_rows)
            chunks.append(chunk_text)
            current_rows = []
            current_tokens = header_tokens

        current_rows.append(row)
        current_tokens += row_tokens

    if current_rows:
        chunk_text = header_text + "\n" + "\n".join(current_rows)
        chunks.append(chunk_text)

    return chunks


class SemanticChunker(ChunkerInterface):
    """尊重内容边界的语义文档分块器 / Semantic document chunker that respects content boundaries.

    关键行为 / Key behaviors:
    - 绝不从句子中间分割 / Never splits mid-sentence
    - 保持代码块完整（最多 2048 个 token）/ Keeps code blocks intact (up to 2048 tokens)
    - 保持表格行与其标题在一起 / Keeps table rows with their headers
    - 可配置的块大小及相邻块之间的重叠 / Configurable chunk size with overlap between adjacent chunks
    """

    def chunk_document(self, document: LoadedDocument, config: ChunkConfig) -> list[Chunk]:
        """Split a LoadedDocument into semantically complete Chunks.

        Args:
            document: The loaded document with structural units.
            config: Chunking configuration (max_tokens, overlap, code_block_max).

        Returns:
            List of Chunk objects with metadata and content.
        """
        if not document.units:
            return []

        chunks: list[Chunk] = []
        chunk_position = 0

        # Extract metadata from document structural_info
        project_name = document.structural_info.get("project_name", "")
        module_name = document.structural_info.get("module_name", "")
        document_version = document.structural_info.get("document_version", "")
        content_type = document.structural_info.get("content_type", "")

        for unit in document.units:
            unit_chunks = self._chunk_unit(unit, config)

            for chunk_text in unit_chunks:
                token_count = count_tokens(chunk_text)
                metadata = ChunkMetadata(
                    project_name=project_name,
                    module_name=module_name,
                    document_version=document_version,
                    content_type=content_type,
                    source_path=document.source_path,
                    chunk_position=chunk_position,
                )
                chunk_id = self.generate_chunk_id(
                    document.source_path, chunk_position, document_version
                )
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        content=chunk_text,
                        metadata=metadata,
                        token_count=token_count,
                    )
                )
                chunk_position += 1

        return chunks

    def generate_chunk_id(self, source_path: str, position: int, version: str) -> str:
        """Generate a deterministic unique chunk identifier.

        Uses SHA-256 hash of the concatenation of source_path, chunk_position,
        and document_version to produce a deterministic, unique ID.

        The same (source_path, position, version) tuple always produces the
        same chunk_id. Different tuples produce different chunk_ids.

        Args:
            source_path: Path to the source document.
            position: The chunk's position index within the document.
            version: The document version string.

        Returns:
            A 64-character hex string (full SHA-256 digest).
        """
        key = f"{source_path}|{position}|{version}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _chunk_unit(self, unit: DocumentUnit, config: ChunkConfig) -> list[str]:
        """Chunk a single DocumentUnit based on its type.

        Args:
            unit: The document unit to chunk.
            config: Chunking configuration.

        Returns:
            List of chunk text strings.
        """
        if unit.unit_type == "code_block":
            return self._chunk_code_block(unit, config)
        elif unit.unit_type == "table":
            return self._chunk_table(unit, config)
        else:
            return self._chunk_text(unit, config)

    def _chunk_code_block(self, unit: DocumentUnit, config: ChunkConfig) -> list[str]:
        """Handle code block chunking.

        Code blocks are kept intact as single chunks up to code_block_max_tokens.
        If they exceed that limit, split at function/class boundaries.
        """
        token_count = count_tokens(unit.content)

        if token_count <= config.code_block_max_tokens:
            # Keep as single chunk
            return [unit.content]
        else:
            # Split at function/class boundaries
            return _split_code_block_at_boundaries(
                unit.content, config.code_block_max_tokens
            )

    def _chunk_table(self, unit: DocumentUnit, config: ChunkConfig) -> list[str]:
        """Handle table chunking — keep rows with headers."""
        return _chunk_table_unit(unit, config)

    def _chunk_text(self, unit: DocumentUnit, config: ChunkConfig) -> list[str]:
        """Handle regular text chunking with sentence boundary awareness."""
        content = unit.content
        token_count = count_tokens(content)

        # If content fits in a single chunk, return as-is
        if token_count <= config.max_tokens:
            return [content]

        # Split into sentences and build chunks with overlap
        sentences = split_sentences(content)
        if not sentences:
            return [content]

        return _build_chunks_from_sentences(
            sentences, config.max_tokens, config.overlap_tokens
        )
