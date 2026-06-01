"""源代码加载器 / Source code loader for Code Factory.

支持 Python、Java、JavaScript 和 TypeScript 文件。
Supports Python, Java, JavaScript, and TypeScript files.
- Python: 使用 AST 解析提取函数、类和文档字符串 / Uses AST parsing to extract functions, classes, and docstrings.
- Java/JavaScript/TypeScript: 使用正则表达式进行基本提取 / Uses regex patterns for basic extraction.

每个提取的元素成为具有顺序位置的 DocumentUnit。
Each extracted element becomes a DocumentUnit with sequential position.

需求 / Requirements: 5.1, 5.4
"""

import ast
import re
from typing import Any

from rag.document_loader import FormatLoader
from src.core.exceptions import DocumentLoadError
from src.core.logging import get_logger
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument

logger = get_logger("rag.loaders.source_code_loader")

# Language detection from file extension
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
}

EXTENSION_TO_FORMAT: dict[str, DocumentFormat] = {
    ".py": DocumentFormat.PYTHON,
    ".java": DocumentFormat.JAVA,
    ".js": DocumentFormat.JAVASCRIPT,
    ".ts": DocumentFormat.TYPESCRIPT,
}


class SourceCodeLoader(FormatLoader):
    """源代码文件加载器（Python、Java、JavaScript、TypeScript）/ Loader for source code files (Python, Java, JavaScript, TypeScript).

    对于 Python 文件，使用 ast 模块进行精确提取。
    For Python files, uses the ast module for accurate extraction.
    对于 Java/JavaScript/TypeScript，使用正则表达式进行基本提取。
    For Java/JavaScript/TypeScript, uses regex patterns for basic extraction.
    """

    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        """Load a source code file and extract logical units.

        Args:
            file_path: Path to the source file.
            content: Raw file content as bytes.

        Returns:
            A LoadedDocument with extracted functions, classes, and docstrings.

        Raises:
            DocumentLoadError: If the file cannot be parsed.
        """
        # Determine language from file extension
        ext = _get_extension(file_path)
        language = EXTENSION_TO_LANGUAGE.get(ext)
        doc_format = EXTENSION_TO_FORMAT.get(ext)

        if language is None or doc_format is None:
            raise DocumentLoadError(
                f"Unsupported source code extension '{ext}' for file '{file_path}'"
            )

        # Decode content to text
        try:
            source_text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DocumentLoadError(
                f"Failed to decode source file '{file_path}' as UTF-8: {e}"
            )

        # Extract units based on language
        if language == "python":
            units = _extract_python_units(file_path, source_text)
        else:
            units = _extract_regex_units(file_path, source_text, language)

        # Count functions and classes
        num_functions = sum(1 for u in units if u.unit_type == "function")
        num_classes = sum(1 for u in units if u.unit_type == "class")

        structural_info: dict[str, Any] = {
            "language": language,
            "num_functions": num_functions,
            "num_classes": num_classes,
        }

        return LoadedDocument(
            source_path=file_path,
            format=doc_format,
            units=units,
            raw_text=source_text,
            structural_info=structural_info,
        )


def _get_extension(file_path: str) -> str:
    """Extract the lowercase file extension from a path."""
    import os

    _, ext = os.path.splitext(file_path)
    return ext.lower()


# =============================================================================
# Python AST-based extraction
# =============================================================================


def _extract_python_units(file_path: str, source_text: str) -> list[DocumentUnit]:
    """Extract functions, classes, and docstrings from Python source using AST.

    Args:
        file_path: Path to the source file.
        source_text: The Python source code as a string.

    Returns:
        List of DocumentUnit objects for each extracted element.

    Raises:
        DocumentLoadError: If the Python source cannot be parsed.
    """
    try:
        tree = ast.parse(source_text)
    except SyntaxError as e:
        raise DocumentLoadError(
            f"Failed to parse Python file '{file_path}': {e}"
        )

    units: list[DocumentUnit] = []
    position = 0

    # Extract module-level docstring
    module_docstring = ast.get_docstring(tree)
    if module_docstring:
        units.append(
            DocumentUnit(
                content=module_docstring,
                unit_type="docstring",
                metadata={"parent": "module"},
                source_path=file_path,
                position=position,
            )
        )
        position += 1

    # Walk top-level nodes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # Extract function
            func_source = ast.get_source_segment(source_text, node)
            if func_source is None:
                func_source = _get_node_source_fallback(source_text, node)

            decorators = [
                _decorator_to_string(d) for d in node.decorator_list
            ]

            units.append(
                DocumentUnit(
                    content=func_source,
                    unit_type="function",
                    metadata={
                        "function_name": node.name,
                        "decorators": decorators,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    },
                    source_path=file_path,
                    position=position,
                )
            )
            position += 1

            # Extract function docstring
            func_docstring = ast.get_docstring(node)
            if func_docstring:
                units.append(
                    DocumentUnit(
                        content=func_docstring,
                        unit_type="docstring",
                        metadata={
                            "parent": f"function:{node.name}",
                        },
                        source_path=file_path,
                        position=position,
                    )
                )
                position += 1

        elif isinstance(node, ast.ClassDef):
            # Extract class
            class_source = ast.get_source_segment(source_text, node)
            if class_source is None:
                class_source = _get_node_source_fallback(source_text, node)

            bases = [_base_to_string(b) for b in node.bases]

            units.append(
                DocumentUnit(
                    content=class_source,
                    unit_type="class",
                    metadata={
                        "class_name": node.name,
                        "bases": bases,
                    },
                    source_path=file_path,
                    position=position,
                )
            )
            position += 1

            # Extract class docstring
            class_docstring = ast.get_docstring(node)
            if class_docstring:
                units.append(
                    DocumentUnit(
                        content=class_docstring,
                        unit_type="docstring",
                        metadata={
                            "parent": f"class:{node.name}",
                        },
                        source_path=file_path,
                        position=position,
                    )
                )
                position += 1

            # Extract methods within the class
            for class_node in ast.iter_child_nodes(node):
                if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_source = ast.get_source_segment(source_text, class_node)
                    if method_source is None:
                        method_source = _get_node_source_fallback(
                            source_text, class_node
                        )

                    method_decorators = [
                        _decorator_to_string(d) for d in class_node.decorator_list
                    ]

                    units.append(
                        DocumentUnit(
                            content=method_source,
                            unit_type="function",
                            metadata={
                                "function_name": class_node.name,
                                "decorators": method_decorators,
                                "is_async": isinstance(
                                    class_node, ast.AsyncFunctionDef
                                ),
                                "parent_class": node.name,
                            },
                            source_path=file_path,
                            position=position,
                        )
                    )
                    position += 1

                    # Extract method docstring
                    method_docstring = ast.get_docstring(class_node)
                    if method_docstring:
                        units.append(
                            DocumentUnit(
                                content=method_docstring,
                                unit_type="docstring",
                                metadata={
                                    "parent": f"method:{node.name}.{class_node.name}",
                                },
                                source_path=file_path,
                                position=position,
                            )
                        )
                        position += 1

    return units


def _decorator_to_string(node: ast.expr) -> str:
    """Convert a decorator AST node to its string representation."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_decorator_to_string(node.value)}.{node.attr}"
    elif isinstance(node, ast.Call):
        func_str = _decorator_to_string(node.func)
        return f"{func_str}(...)"
    return ast.dump(node)


def _base_to_string(node: ast.expr) -> str:
    """Convert a base class AST node to its string representation."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_base_to_string(node.value)}.{node.attr}"
    elif isinstance(node, ast.Subscript):
        return f"{_base_to_string(node.value)}[...]"
    return ast.dump(node)


def _get_node_source_fallback(source_text: str, node: ast.AST) -> str:
    """Fallback to extract source from line numbers when get_source_segment fails."""
    lines = source_text.splitlines()
    start = node.lineno - 1  # 0-indexed
    end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 1
    return "\n".join(lines[start:end])


# =============================================================================
# Regex-based extraction for Java, JavaScript, TypeScript
# =============================================================================

# Java patterns
_JAVA_CLASS_PATTERN = re.compile(
    r"(?P<comment>/\*\*[\s\S]*?\*/\s*)?"
    r"(?P<modifiers>(?:public|private|protected|abstract|static|final)\s+)*"
    r"class\s+(?P<name>\w+)"
    r"(?:\s+extends\s+(?P<extends>\w+))?"
    r"(?:\s+implements\s+(?P<implements>[\w\s,]+))?"
    r"\s*\{",
    re.MULTILINE,
)

_JAVA_METHOD_PATTERN = re.compile(
    r"(?P<comment>/\*\*[\s\S]*?\*/\s*)?"
    r"(?P<modifiers>(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*)"
    r"(?P<return_type>[\w<>\[\],\s]+?)\s+"
    r"(?P<name>\w+)\s*\("
    r"(?P<params>[^)]*)\)\s*"
    r"(?:throws\s+[\w\s,]+)?\s*\{",
    re.MULTILINE,
)

# JavaScript/TypeScript patterns
_JS_FUNCTION_PATTERN = re.compile(
    r"(?P<comment>/\*\*[\s\S]*?\*/\s*)?"
    r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\([^)]*\)",
    re.MULTILINE,
)

_JS_ARROW_FUNCTION_PATTERN = re.compile(
    r"(?P<comment>/\*\*[\s\S]*?\*/\s*)?"
    r"(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
    re.MULTILINE,
)

_JS_CLASS_PATTERN = re.compile(
    r"(?P<comment>/\*\*[\s\S]*?\*/\s*)?"
    r"(?:export\s+)?(?:abstract\s+)?class\s+(?P<name>\w+)"
    r"(?:\s+extends\s+(?P<extends>\w+))?"
    r"(?:\s+implements\s+(?P<implements>[\w\s,]+))?"
    r"\s*\{",
    re.MULTILINE,
)

_JS_METHOD_PATTERN = re.compile(
    r"(?P<comment>/\*\*[\s\S]*?\*/\s*)?"
    r"(?:(?:public|private|protected|static|async|abstract)\s+)*"
    r"(?P<name>\w+)\s*\([^)]*\)\s*(?::\s*[\w<>\[\]|&\s]+)?\s*\{",
    re.MULTILINE,
)

# JSDoc/block comment pattern
_JSDOC_PATTERN = re.compile(
    r"/\*\*\s*([\s\S]*?)\*/",
    re.MULTILINE,
)


def _extract_regex_units(
    file_path: str, source_text: str, language: str
) -> list[DocumentUnit]:
    """Extract functions, classes, and comments from Java/JS/TS using regex.

    Args:
        file_path: Path to the source file.
        source_text: The source code as a string.
        language: One of "java", "javascript", "typescript".

    Returns:
        List of DocumentUnit objects for each extracted element.
    """
    units: list[DocumentUnit] = []
    seen_spans: list[tuple[int, int]] = []  # Track matched spans to avoid duplicates

    if language == "java":
        units.extend(
            _extract_java_units(file_path, source_text, seen_spans)
        )
    else:
        # JavaScript and TypeScript share similar syntax
        units.extend(
            _extract_js_ts_units(file_path, source_text, language, seen_spans)
        )

    # Extract standalone JSDoc/block comments not already captured
    units.extend(
        _extract_standalone_comments(file_path, source_text, seen_spans)
    )

    # Assign sequential positions
    units.sort(key=lambda u: u.position)
    for i, unit in enumerate(units):
        unit.position = i

    return units


def _extract_java_units(
    file_path: str, source_text: str, seen_spans: list[tuple[int, int]]
) -> list[DocumentUnit]:
    """Extract classes and methods from Java source code."""
    units: list[DocumentUnit] = []

    # Track class spans separately so methods inside classes are still extracted
    class_spans: list[tuple[int, int]] = []

    # Extract classes
    for match in _JAVA_CLASS_PATTERN.finditer(source_text):
        class_name = match.group("name")
        extends = match.group("extends") or ""
        implements = match.group("implements") or ""
        comment = match.group("comment") or ""

        # Get the class body (find matching brace)
        class_body = _extract_braced_block(source_text, match.start())
        content = class_body if class_body else match.group(0)

        class_span = (match.start(), match.start() + len(content))
        class_spans.append(class_span)
        seen_spans.append(class_span)

        units.append(
            DocumentUnit(
                content=content,
                unit_type="class",
                metadata={
                    "class_name": class_name,
                    "extends": extends.strip(),
                    "implements": [
                        s.strip() for s in implements.split(",") if s.strip()
                    ],
                },
                source_path=file_path,
                position=match.start(),
            )
        )

        # If there's a preceding comment, add it as docstring
        if comment.strip():
            comment_text = _clean_block_comment(comment)
            units.append(
                DocumentUnit(
                    content=comment_text,
                    unit_type="docstring",
                    metadata={"parent": f"class:{class_name}"},
                    source_path=file_path,
                    position=match.start() - len(comment),
                )
            )
            seen_spans.append(
                (match.start() - len(comment), match.start())
            )

    # Track method spans to avoid duplicate method extraction
    method_seen_spans: list[tuple[int, int]] = []

    # Extract methods (allowed inside class bodies)
    for match in _JAVA_METHOD_PATTERN.finditer(source_text):
        method_name = match.group("name")
        # Skip if this is a constructor matching a class name or common keywords
        if method_name in ("if", "for", "while", "switch", "catch", "class", "new"):
            continue

        comment = match.group("comment") or ""
        params = match.group("params") or ""

        # Check if this method overlaps with an already-extracted method
        if _overlaps(match.start(), match.end(), method_seen_spans):
            continue

        method_body = _extract_braced_block(source_text, match.start())
        content = method_body if method_body else match.group(0)

        method_span = (match.start(), match.start() + len(content))
        method_seen_spans.append(method_span)
        seen_spans.append(method_span)

        units.append(
            DocumentUnit(
                content=content,
                unit_type="function",
                metadata={
                    "function_name": method_name,
                    "parameters": params.strip(),
                },
                source_path=file_path,
                position=match.start(),
            )
        )

        if comment.strip():
            comment_text = _clean_block_comment(comment)
            units.append(
                DocumentUnit(
                    content=comment_text,
                    unit_type="docstring",
                    metadata={"parent": f"function:{method_name}"},
                    source_path=file_path,
                    position=match.start() - len(comment),
                )
            )
            seen_spans.append(
                (match.start() - len(comment), match.start())
            )

    return units


def _extract_js_ts_units(
    file_path: str,
    source_text: str,
    language: str,
    seen_spans: list[tuple[int, int]],
) -> list[DocumentUnit]:
    """Extract classes, functions, and arrow functions from JS/TS source code."""
    units: list[DocumentUnit] = []

    # Extract classes
    for match in _JS_CLASS_PATTERN.finditer(source_text):
        class_name = match.group("name")
        extends = match.group("extends") or ""
        comment = match.group("comment") or ""

        class_body = _extract_braced_block(source_text, match.start())
        content = class_body if class_body else match.group(0)

        seen_spans.append((match.start(), match.start() + len(content)))

        units.append(
            DocumentUnit(
                content=content,
                unit_type="class",
                metadata={
                    "class_name": class_name,
                    "extends": extends.strip(),
                },
                source_path=file_path,
                position=match.start(),
            )
        )

        if comment.strip():
            comment_text = _clean_block_comment(comment)
            units.append(
                DocumentUnit(
                    content=comment_text,
                    unit_type="docstring",
                    metadata={"parent": f"class:{class_name}"},
                    source_path=file_path,
                    position=match.start() - len(comment),
                )
            )
            seen_spans.append(
                (match.start() - len(comment), match.start())
            )

    # Extract regular functions
    for match in _JS_FUNCTION_PATTERN.finditer(source_text):
        func_name = match.group("name")
        comment = match.group("comment") or ""

        if _overlaps(match.start(), match.end(), seen_spans):
            continue

        # Try to get the full function body
        func_body = _extract_braced_block(source_text, match.start())
        content = func_body if func_body else match.group(0)

        seen_spans.append((match.start(), match.start() + len(content)))

        units.append(
            DocumentUnit(
                content=content,
                unit_type="function",
                metadata={"function_name": func_name},
                source_path=file_path,
                position=match.start(),
            )
        )

        if comment.strip():
            comment_text = _clean_block_comment(comment)
            units.append(
                DocumentUnit(
                    content=comment_text,
                    unit_type="docstring",
                    metadata={"parent": f"function:{func_name}"},
                    source_path=file_path,
                    position=match.start() - len(comment),
                )
            )
            seen_spans.append(
                (match.start() - len(comment), match.start())
            )

    # Extract arrow functions
    for match in _JS_ARROW_FUNCTION_PATTERN.finditer(source_text):
        func_name = match.group("name")
        comment = match.group("comment") or ""

        if _overlaps(match.start(), match.end(), seen_spans):
            continue

        # For arrow functions, try to find the end (either braced block or single expression)
        arrow_pos = source_text.find("=>", match.start())
        if arrow_pos != -1:
            after_arrow = source_text[arrow_pos + 2:].lstrip()
            if after_arrow.startswith("{"):
                brace_start = source_text.index("{", arrow_pos)
                func_body = _extract_braced_block(
                    source_text, match.start(), brace_start
                )
                content = func_body if func_body else match.group(0)
            else:
                # Single expression - take until semicolon or newline
                end_pos = _find_expression_end(source_text, arrow_pos + 2)
                content = source_text[match.start():end_pos]
        else:
            content = match.group(0)

        seen_spans.append((match.start(), match.start() + len(content)))

        units.append(
            DocumentUnit(
                content=content,
                unit_type="function",
                metadata={"function_name": func_name},
                source_path=file_path,
                position=match.start(),
            )
        )

        if comment.strip():
            comment_text = _clean_block_comment(comment)
            units.append(
                DocumentUnit(
                    content=comment_text,
                    unit_type="docstring",
                    metadata={"parent": f"function:{func_name}"},
                    source_path=file_path,
                    position=match.start() - len(comment),
                )
            )
            seen_spans.append(
                (match.start() - len(comment), match.start())
            )

    return units


def _extract_standalone_comments(
    file_path: str, source_text: str, seen_spans: list[tuple[int, int]]
) -> list[DocumentUnit]:
    """Extract standalone JSDoc/block comments not already captured."""
    units: list[DocumentUnit] = []

    for match in _JSDOC_PATTERN.finditer(source_text):
        if _overlaps(match.start(), match.end(), seen_spans):
            continue

        comment_text = _clean_block_comment(match.group(0))
        if comment_text.strip():
            seen_spans.append((match.start(), match.end()))
            units.append(
                DocumentUnit(
                    content=comment_text,
                    unit_type="docstring",
                    metadata={"parent": "module"},
                    source_path=file_path,
                    position=match.start(),
                )
            )

    return units


# =============================================================================
# Helper functions
# =============================================================================


def _extract_braced_block(
    source_text: str, search_start: int, brace_start: int | None = None
) -> str | None:
    """Extract a complete braced block {...} from source text.

    Args:
        source_text: The full source text.
        search_start: Position to start searching for the opening brace.
        brace_start: If provided, the exact position of the opening brace.

    Returns:
        The complete text from search_start to the matching closing brace,
        or None if no matching brace is found.
    """
    if brace_start is None:
        brace_pos = source_text.find("{", search_start)
    else:
        brace_pos = brace_start

    if brace_pos == -1:
        return None

    depth = 0
    i = brace_pos
    in_string = False
    string_char = ""
    in_line_comment = False
    in_block_comment = False

    while i < len(source_text):
        char = source_text[i]

        # Handle line comments
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        # Handle block comments
        if in_block_comment:
            if char == "*" and i + 1 < len(source_text) and source_text[i + 1] == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Handle strings
        if in_string:
            if char == "\\" and i + 1 < len(source_text):
                i += 2  # Skip escaped character
                continue
            if char == string_char:
                in_string = False
            i += 1
            continue

        # Check for comment starts
        if char == "/" and i + 1 < len(source_text):
            next_char = source_text[i + 1]
            if next_char == "/":
                in_line_comment = True
                i += 2
                continue
            elif next_char == "*":
                in_block_comment = True
                i += 2
                continue

        # Check for string starts
        if char in ('"', "'", "`"):
            in_string = True
            string_char = char
            i += 1
            continue

        # Track braces
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source_text[search_start:i + 1]

        i += 1

    return None


def _find_expression_end(source_text: str, start: int) -> int:
    """Find the end of a single-expression arrow function."""
    i = start
    depth = 0  # Track parentheses/brackets

    while i < len(source_text):
        char = source_text[i]
        if char in ("(", "["):
            depth += 1
        elif char in (")", "]"):
            depth -= 1
        elif char == ";" and depth == 0:
            return i + 1
        elif char == "\n" and depth == 0:
            # Check if next non-whitespace is not a continuation
            rest = source_text[i + 1:].lstrip()
            if not rest or not rest[0] in (".", "+", "-", "*", "/", "?", ":"):
                return i
        i += 1

    return len(source_text)


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """Check if a span overlaps with any existing spans."""
    for s_start, s_end in spans:
        if start < s_end and end > s_start:
            return True
    return False


def _clean_block_comment(comment: str) -> str:
    """Clean a block comment by removing comment markers and leading asterisks."""
    # Remove /** and */
    text = comment.strip()
    if text.startswith("/**"):
        text = text[3:]
    elif text.startswith("/*"):
        text = text[2:]
    if text.endswith("*/"):
        text = text[:-2]

    # Remove leading * from each line
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("* "):
            cleaned_lines.append(stripped[2:])
        elif stripped.startswith("*"):
            cleaned_lines.append(stripped[1:])
        else:
            cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines).strip()
