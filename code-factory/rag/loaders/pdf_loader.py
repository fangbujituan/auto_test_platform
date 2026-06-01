"""PDF 文档加载器 / PDF document loader for the RAG pipeline.

从 PDF 文件中提取文本，同时尝试保留结构信息，
Extracts text from PDF files while attempting to preserve structural
如标题、代码块和表格。
information such as headings, code blocks, and tables.

使用 PyPDF2 进行文本提取，配合基于启发式的结构检测。
Uses PyPDF2 for text extraction with heuristic-based structure detection.

需求 / Requirements: 5.1, 5.2
"""

import re
from typing import Any

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

from rag.document_loader import FormatLoader
from src.core.exceptions import DocumentLoadError
from src.core.logging import get_logger
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument

logger = get_logger("rag.loaders.pdf_loader")

# Heuristic patterns for detecting structure in extracted PDF text
# Code blocks: lines that start with common code indicators or are indented with 4+ spaces
CODE_BLOCK_INDICATORS = re.compile(
    r"^(\s{4,}|\t+)(.*)", re.MULTILINE
)

# Table-like patterns: lines with multiple pipe separators or tab-separated columns
TABLE_LINE_PATTERN = re.compile(
    r"^.*(\|.*\||\t.*\t).*$"
)

# Heading heuristics: short lines (< 80 chars) that are ALL CAPS or end without punctuation
# and are preceded/followed by blank lines
HEADING_MAX_LENGTH = 100


def _is_likely_heading(line: str) -> bool:
    """Heuristic to detect if a line is likely a heading.

    A line is considered a heading if:
    - It's relatively short (< 100 chars)
    - It doesn't end with typical sentence punctuation
    - It's either all uppercase, or starts with a number followed by a dot (e.g., "1.2 Section")
    """
    stripped = line.strip()
    if not stripped or len(stripped) > HEADING_MAX_LENGTH:
        return False

    # All uppercase lines are likely headings
    if stripped.isupper() and len(stripped) > 2:
        return True

    # Lines starting with numbered patterns like "1.", "1.2", "Chapter 1"
    if re.match(r"^(\d+\.?\d*\.?\s+|Chapter\s+\d+|Section\s+\d+)", stripped, re.IGNORECASE):
        # And doesn't end with sentence punctuation
        if not stripped.endswith((".", ",", ";", ":", "?", "!")):
            return True

    # Short lines that don't end with punctuation and aren't code
    if (
        len(stripped) < 60
        and not stripped.endswith((".", ",", ";", ":", "?", "!"))
        and not stripped.startswith((" ", "\t", "#", "//", "/*", "*"))
        and stripped[0].isupper()
    ):
        return True

    return False


def _is_likely_table_line(line: str) -> bool:
    """Check if a line looks like part of a table."""
    stripped = line.strip()
    if not stripped:
        return False
    # Pipe-delimited tables
    if "|" in stripped and stripped.count("|") >= 2:
        return True
    # Tab-separated with multiple columns
    if "\t" in stripped and stripped.count("\t") >= 2:
        return True
    return False


def _is_likely_code_line(line: str) -> bool:
    """Check if a line looks like code (indented or has code-like patterns)."""
    # Lines with 4+ leading spaces or tabs
    if line.startswith("    ") or line.startswith("\t"):
        return True
    # Lines with common code patterns
    stripped = line.strip()
    code_patterns = [
        r"^(def |class |import |from |if |for |while |return |raise )",
        r"^(public |private |protected |static |void |int |String )",
        r"^(function |const |let |var |export |import )",
        r"^[{}()\[\];]$",
        r".*[{};]$",
        r"^#include",
        r"^>>>",
    ]
    for pattern in code_patterns:
        if re.match(pattern, stripped):
            return True
    return False


def _detect_heading_level(line: str) -> int:
    """Estimate heading level from text characteristics.

    Returns 1 for top-level headings, 2 for sub-headings, etc.
    """
    stripped = line.strip()
    # All caps = level 1
    if stripped.isupper():
        return 1
    # Numbered with single digit = level based on depth
    match = re.match(r"^(\d+)(\.(\d+))?(\.(\d+))?", stripped)
    if match:
        if match.group(5):
            return 3
        if match.group(3):
            return 2
        return 1
    # Default to level 2
    return 2


def _parse_text_into_units(text: str, source_path: str) -> list[DocumentUnit]:
    """Parse extracted PDF text into structured DocumentUnit objects.

    Uses heuristics to detect headings, code blocks, tables, and paragraphs.
    """
    units: list[DocumentUnit] = []
    lines = text.split("\n")
    position = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Detect table blocks (consecutive table-like lines)
        if _is_likely_table_line(line):
            table_lines = []
            while i < len(lines) and (_is_likely_table_line(lines[i]) or not lines[i].strip()):
                if lines[i].strip():
                    table_lines.append(lines[i])
                i += 1
            if table_lines:
                units.append(DocumentUnit(
                    content="\n".join(table_lines),
                    unit_type="table",
                    metadata={"row_count": len(table_lines)},
                    source_path=source_path,
                    position=position,
                ))
                position += 1
            continue

        # Detect code blocks (consecutive indented/code-like lines)
        if _is_likely_code_line(line):
            code_lines = []
            while i < len(lines) and (_is_likely_code_line(lines[i]) or not lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            # Only treat as code block if we have multiple lines
            if len(code_lines) >= 2:
                # Strip trailing empty lines
                while code_lines and not code_lines[-1].strip():
                    code_lines.pop()
                units.append(DocumentUnit(
                    content="\n".join(code_lines),
                    unit_type="code_block",
                    metadata={"line_count": len(code_lines)},
                    source_path=source_path,
                    position=position,
                ))
                position += 1
                continue
            else:
                # Single code-like line, treat as paragraph
                # Reset i to re-process
                i -= len(code_lines)

        # Detect headings
        if _is_likely_heading(line):
            level = _detect_heading_level(line)
            units.append(DocumentUnit(
                content=stripped,
                unit_type="heading",
                metadata={"heading_level": level},
                source_path=source_path,
                position=position,
            ))
            position += 1
            i += 1
            continue

        # Default: collect paragraph text (consecutive non-empty, non-special lines)
        para_lines = []
        while i < len(lines):
            current = lines[i]
            current_stripped = current.strip()
            if not current_stripped:
                i += 1
                break
            if _is_likely_heading(current) and para_lines:
                break
            if _is_likely_table_line(current) and para_lines:
                break
            if _is_likely_code_line(current) and para_lines:
                break
            para_lines.append(current_stripped)
            i += 1

        if para_lines:
            units.append(DocumentUnit(
                content=" ".join(para_lines),
                unit_type="paragraph",
                metadata={},
                source_path=source_path,
                position=position,
            ))
            position += 1

    return units


class PdfLoader(FormatLoader):
    """PDF 格式加载器，使用 PyPDF2 / PDF format loader using PyPDF2.

    从 PDF 文件中提取文本，并使用启发式方法检测
    Extracts text from PDF files and uses heuristics to detect
    结构元素，如标题、代码块和表格。
    structural elements like headings, code blocks, and tables.
    """

    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        """Load a PDF document and extract structured content.

        Args:
            file_path: Path to the source PDF file.
            content: Raw PDF file content as bytes.

        Returns:
            A LoadedDocument with extracted units and structural info.

        Raises:
            DocumentLoadError: If the PDF cannot be parsed.
        """
        import io

        try:
            reader = PdfReader(io.BytesIO(content))
        except (PdfReadError, Exception) as e:
            raise DocumentLoadError(
                f"Failed to parse PDF file '{file_path}': {e}"
            )

        # Extract text from all pages
        page_texts: list[str] = []
        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                page_texts.append(text)
            except Exception as e:
                logger.warning(
                    "Failed to extract text from PDF page",
                    file_path=file_path,
                    page_number=page_num,
                    error=str(e),
                )
                page_texts.append("")

        raw_text = "\n\n".join(page_texts)

        # Parse text into structured units
        units = _parse_text_into_units(raw_text, file_path)

        # If no units were detected, create a single paragraph unit
        if not units and raw_text.strip():
            units = [DocumentUnit(
                content=raw_text.strip(),
                unit_type="paragraph",
                metadata={},
                source_path=file_path,
                position=0,
            )]

        structural_info: dict[str, Any] = {
            "page_count": len(reader.pages),
            "unit_count": len(units),
            "unit_types": list(set(u.unit_type for u in units)),
        }

        logger.info(
            "PDF document loaded",
            file_path=file_path,
            page_count=len(reader.pages),
            unit_count=len(units),
        )

        return LoadedDocument(
            source_path=file_path,
            format=DocumentFormat.PDF,
            units=units,
            raw_text=raw_text,
            structural_info=structural_info,
        )
