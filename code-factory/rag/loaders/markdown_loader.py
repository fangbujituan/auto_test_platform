"""Markdown 文档加载器 / Markdown document loader for Code Factory.

解析 Markdown 内容并保留结构信息：
Parses Markdown content preserving structural information:
- 标题（# 到 ######）作为单独的 DocumentUnit 对象 / Headings (# through ######) as separate DocumentUnit objects
- 带围栏的代码块（```）及语言元数据 / Fenced code blocks (```) with language metadata
- 表格（| ... | 格式）作为单独的单元 / Tables (| ... | format) as separate units
- 常规段落作为单独的单元 / Regular paragraphs as separate units

需求 / Requirements: 5.1, 5.2
"""

import re
from typing import Any

from rag.document_loader import FormatLoader
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument


class MarkdownLoader(FormatLoader):
    """Markdown 文档加载器 / Loader for Markdown documents.

    使用基于正则表达式的提取来解析 Markdown 内容，
    Parses Markdown content using regex-based extraction to identify
    识别标题、代码块、表格和段落。每个结构元素
    headings, code blocks, tables, and paragraphs. Each structural
    成为具有适当元数据的单独 DocumentUnit。
    element becomes a separate DocumentUnit with appropriate metadata.

    加载器在 structural_info 中维护标题层次结构信息，
    The loader maintains heading hierarchy information in structural_info,
    跟踪整个文档中标题的嵌套。
    tracking the nesting of headings throughout the document.
    """

    # Regex patterns for Markdown elements
    _HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    _FENCED_CODE_BLOCK_PATTERN = re.compile(
        r"^```(\w*)\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL
    )
    _TABLE_ROW_PATTERN = re.compile(r"^\|.+\|$", re.MULTILINE)
    _TABLE_SEPARATOR_PATTERN = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)

    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        """Load and parse a Markdown document from raw bytes.

        Args:
            file_path: Path to the source Markdown file.
            content: Raw file content as bytes.

        Returns:
            A LoadedDocument with extracted units and heading hierarchy.
        """
        text = content.decode("utf-8", errors="replace")
        units: list[DocumentUnit] = []
        heading_hierarchy: list[dict[str, Any]] = []
        position = 0

        # Parse the document into structural elements
        elements = self._parse_elements(text)

        for element in elements:
            element_type = element["type"]
            element_content = element["content"]
            metadata: dict[str, Any] = {}

            if element_type == "heading":
                metadata["heading_level"] = element["level"]
                metadata["heading_text"] = element["heading_text"]
                # Track heading hierarchy
                heading_hierarchy.append(
                    {
                        "level": element["level"],
                        "text": element["heading_text"],
                        "position": position,
                    }
                )
            elif element_type == "code_block":
                metadata["language"] = element.get("language", "")
            elif element_type == "table":
                metadata["row_count"] = element.get("row_count", 0)
                metadata["has_header"] = element.get("has_header", False)

            unit = DocumentUnit(
                content=element_content,
                unit_type=element_type,
                metadata=metadata,
                source_path=file_path,
                position=position,
            )
            units.append(unit)
            position += 1

        structural_info: dict[str, Any] = {
            "heading_hierarchy": heading_hierarchy,
            "total_units": len(units),
            "unit_type_counts": self._count_unit_types(units),
        }

        return LoadedDocument(
            source_path=file_path,
            format=DocumentFormat.MARKDOWN,
            units=units,
            raw_text=text,
            structural_info=structural_info,
        )

    def _parse_elements(self, text: str) -> list[dict[str, Any]]:
        """Parse Markdown text into a list of structural elements.

        Processes the document sequentially, identifying code blocks first
        (since they can contain other Markdown-like syntax), then headings,
        tables, and paragraphs in the remaining text.

        Args:
            text: The full Markdown text content.

        Returns:
            A list of element dictionaries with type, content, and metadata.
        """
        elements: list[dict[str, Any]] = []

        # First, identify all fenced code blocks and their positions
        # to avoid parsing Markdown syntax inside code blocks
        code_blocks: list[tuple[int, int, str, str]] = []
        for match in self._FENCED_CODE_BLOCK_PATTERN.finditer(text):
            language = match.group(1) or ""
            code_content = match.group(2)
            code_blocks.append(
                (match.start(), match.end(), language, code_content)
            )

        # Process the text, splitting around code blocks
        current_pos = 0
        for start, end, language, code_content in code_blocks:
            # Process text before this code block
            if current_pos < start:
                segment = text[current_pos:start]
                elements.extend(self._parse_non_code_segment(segment))

            # Add the code block element
            # Include the full fenced block as content for readability
            full_code_block = text[start:end]
            elements.append(
                {
                    "type": "code_block",
                    "content": code_content.rstrip("\n"),
                    "language": language,
                }
            )
            current_pos = end

        # Process any remaining text after the last code block
        if current_pos < len(text):
            segment = text[current_pos:]
            elements.extend(self._parse_non_code_segment(segment))

        return elements

    def _parse_non_code_segment(self, segment: str) -> list[dict[str, Any]]:
        """Parse a segment of text that is not inside a code block.

        Identifies headings, tables, and paragraphs within the segment.

        Args:
            segment: Text segment to parse.

        Returns:
            A list of element dictionaries.
        """
        elements: list[dict[str, Any]] = []
        lines = segment.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                elements.append(
                    {
                        "type": "heading",
                        "content": line,
                        "level": level,
                        "heading_text": heading_text,
                    }
                )
                i += 1
                continue

            # Check for table (starts with |)
            if re.match(r"^\|.+\|$", line.strip()):
                table_lines = []
                while i < len(lines) and re.match(
                    r"^\|.+\|$", lines[i].strip()
                ):
                    table_lines.append(lines[i])
                    i += 1

                if table_lines:
                    # Determine if there's a separator row (header indicator)
                    has_header = False
                    row_count = len(table_lines)
                    for tl in table_lines:
                        if re.match(r"^\|[\s\-:|]+\|$", tl.strip()):
                            has_header = True
                            row_count -= 1  # separator doesn't count as data row
                            break

                    elements.append(
                        {
                            "type": "table",
                            "content": "\n".join(table_lines),
                            "row_count": row_count,
                            "has_header": has_header,
                        }
                    )
                continue

            # Accumulate paragraph lines (non-empty, non-heading, non-table)
            if line.strip():
                paragraph_lines = []
                while i < len(lines):
                    current_line = lines[i]
                    # Stop if we hit a heading, table start, or empty line
                    if not current_line.strip():
                        break
                    if re.match(r"^#{1,6}\s+", current_line):
                        break
                    if re.match(r"^\|.+\|$", current_line.strip()):
                        break
                    paragraph_lines.append(current_line)
                    i += 1

                if paragraph_lines:
                    elements.append(
                        {
                            "type": "paragraph",
                            "content": "\n".join(paragraph_lines),
                        }
                    )
                continue

            # Skip empty lines
            i += 1

        return elements

    def _count_unit_types(self, units: list[DocumentUnit]) -> dict[str, int]:
        """Count the number of units by type.

        Args:
            units: List of DocumentUnit objects.

        Returns:
            Dictionary mapping unit_type to count.
        """
        counts: dict[str, int] = {}
        for unit in units:
            counts[unit.unit_type] = counts.get(unit.unit_type, 0) + 1
        return counts
