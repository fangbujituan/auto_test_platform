"""文档加载器实现 / Document Loader implementation for Code Factory.

实现 DocumentLoaderInterface，支持从文件扩展名检测格式，
Implements DocumentLoaderInterface with format detection from file extension,
使用注册表/策略模式处理特定格式的加载器，并提供适当的错误处理。
a registry/strategy pattern for format-specific loaders, and proper error handling.

需求 / Requirements: 5.1, 5.5, 5.6
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from src.core.exceptions import DocumentLoadError, UnsupportedFormatError
from src.core.interfaces import DocumentLoaderInterface
from src.core.logging import get_logger
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument

logger = get_logger("rag.document_loader")

# Mapping from file extensions to DocumentFormat
EXTENSION_FORMAT_MAP: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".md": DocumentFormat.MARKDOWN,
    ".markdown": DocumentFormat.MARKDOWN,
    ".docx": DocumentFormat.WORD,
    ".json": DocumentFormat.SWAGGER_JSON,
    ".yaml": DocumentFormat.SWAGGER_YAML,
    ".yml": DocumentFormat.SWAGGER_YAML,
    ".py": DocumentFormat.PYTHON,
    ".java": DocumentFormat.JAVA,
    ".js": DocumentFormat.JAVASCRIPT,
    ".ts": DocumentFormat.TYPESCRIPT,
}

# Human-readable list of supported formats for error messages
SUPPORTED_FORMATS_DESCRIPTION: list[str] = [
    "PDF (.pdf)",
    "Markdown (.md, .markdown)",
    "Word (.docx)",
    "Swagger/OpenAPI JSON (.json)",
    "Swagger/OpenAPI YAML (.yaml, .yml)",
    "Python (.py)",
    "Java (.java)",
    "JavaScript (.js)",
    "TypeScript (.ts)",
]


class FormatLoader(ABC):
    """特定格式文档加载器的抽象基类 / Abstract base class for format-specific document loaders.

    每种格式（PDF、Markdown 等）实现此接口以提供
    Each format (PDF, Markdown, etc.) implements this interface to provide
    特定格式的解析逻辑。
    format-specific parsing logic.
    """

    @abstractmethod
    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        """Load and parse a document from raw bytes.

        Args:
            file_path: Path to the source file.
            content: Raw file content as bytes.

        Returns:
            A LoadedDocument with extracted units and structural info.
        """
        ...


class DocumentLoader(DocumentLoaderInterface):
    """主文档加载器，实现格式检测和委托 / Main document loader implementing format detection and delegation.

    使用注册表模式，可以注册特定格式的加载器。
    Uses a registry pattern where format-specific loaders can be registered.
    load() 方法从文件扩展名检测格式，找到合适的加载器，
    The load() method detects format from file extension, finds the appropriate
    并委托实际解析工作。
    loader, and delegates the actual parsing.

    示例 / Example:
        loader = DocumentLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, MarkdownLoader())
        doc = loader.load("path/to/file.md")
    """

    def __init__(self) -> None:
        """Initialize the DocumentLoader with an empty format loader registry."""
        self._format_loaders: dict[DocumentFormat, FormatLoader] = {}

    def register_format_loader(
        self, format: DocumentFormat, loader: FormatLoader
    ) -> None:
        """Register a format-specific loader.

        Args:
            format: The DocumentFormat this loader handles.
            loader: The FormatLoader implementation.
        """
        self._format_loaders[format] = loader
        logger.debug(
            "Registered format loader",
            format=format.value,
            loader_class=type(loader).__name__,
        )

    def supports_format(self, file_path: str) -> bool:
        """Check if the file format is supported based on file extension.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file extension maps to a supported DocumentFormat.
        """
        ext = Path(file_path).suffix.lower()
        return ext in EXTENSION_FORMAT_MAP

    def detect_format(self, file_path: str) -> DocumentFormat:
        """Detect the document format from the file extension.

        Args:
            file_path: Path to the file.

        Returns:
            The detected DocumentFormat.

        Raises:
            UnsupportedFormatError: If the file extension is not supported.
        """
        ext = Path(file_path).suffix.lower()
        if ext not in EXTENSION_FORMAT_MAP:
            raise UnsupportedFormatError(
                file_path=file_path,
                supported_formats=SUPPORTED_FORMATS_DESCRIPTION,
            )
        return EXTENSION_FORMAT_MAP[ext]

    def load(self, file_path: str) -> LoadedDocument:
        """Load a document, detecting format from extension and delegating to the appropriate loader.

        Args:
            file_path: Path to the document file.

        Returns:
            A LoadedDocument with extracted content and structure.

        Raises:
            UnsupportedFormatError: If the file format is not supported.
            DocumentLoadError: If the file cannot be read (corrupted, permissions, etc.).
        """
        # Detect format (raises UnsupportedFormatError if not supported)
        doc_format = self.detect_format(file_path)

        # Read file content with error handling for corrupted/unreadable files
        try:
            content = self._read_file(file_path)
        except (OSError, IOError, PermissionError) as e:
            error_msg = f"Failed to read file '{file_path}': {e}"
            logger.error(
                "Document load failed",
                file_path=file_path,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DocumentLoadError(error_msg)

        # Find the registered format loader
        format_loader = self._format_loaders.get(doc_format)
        if format_loader is None:
            # Format is recognized but no loader is registered yet
            # This happens when format-specific loaders haven't been implemented
            logger.warning(
                "No format loader registered for detected format",
                file_path=file_path,
                format=doc_format.value,
            )
            raise DocumentLoadError(
                f"No loader registered for format '{doc_format.value}'. "
                f"Format-specific loader not yet implemented."
            )

        # Delegate to the format-specific loader
        try:
            return format_loader.load(file_path, content)
        except DocumentLoadError:
            # Re-raise DocumentLoadError as-is
            raise
        except Exception as e:
            error_msg = (
                f"Error parsing file '{file_path}' as {doc_format.value}: {e}"
            )
            logger.error(
                "Document parsing failed",
                file_path=file_path,
                format=doc_format.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DocumentLoadError(error_msg)

    def _read_file(self, file_path: str) -> bytes:
        """Read file content as bytes.

        Args:
            file_path: Path to the file.

        Returns:
            Raw file content as bytes.

        Raises:
            OSError: If the file cannot be read.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not path.is_file():
            raise IsADirectoryError(f"Path is not a file: {file_path}")
        return path.read_bytes()
