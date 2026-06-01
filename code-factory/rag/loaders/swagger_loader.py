"""Swagger/OpenAPI 文档加载器 / Swagger/OpenAPI document loader for Code Factory.

支持 JSON 和 YAML OpenAPI 格式（2.x 和 3.x）。
Supports both JSON and YAML OpenAPI formats (2.x and 3.x).
将每个 API 端点提取为单独的 DocumentUnit，包含方法、路径、
Extracts each API endpoint as a separate DocumentUnit with method, path,
参数和响应模式信息。
parameters, and response schema information.

需求 / Requirements: 5.1, 5.3
"""

import json
from typing import Any

import yaml

from rag.document_loader import FormatLoader
from src.core.exceptions import DocumentLoadError
from src.core.logging import get_logger
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument

logger = get_logger("rag.loaders.swagger_loader")


class SwaggerLoader(FormatLoader):
    """Swagger/OpenAPI 规范文件加载器 / Loader for Swagger/OpenAPI specification files.

    支持 JSON 和 YAML 格式，以及 OpenAPI 2.x (Swagger)
    Supports both JSON and YAML formats, and both OpenAPI 2.x (Swagger)
    和 OpenAPI 3.x 规范。
    and OpenAPI 3.x specifications.

    每个 API 端点（路径 + 方法组合）被提取为单独的
    Each API endpoint (path + method combination) is extracted as a separate
    DocumentUnit，unit_type="api_endpoint"。
    DocumentUnit with unit_type="api_endpoint".
    """

    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        """Load and parse an OpenAPI/Swagger specification.

        Args:
            file_path: Path to the source file.
            content: Raw file content as bytes.

        Returns:
            A LoadedDocument with each endpoint as a separate DocumentUnit.

        Raises:
            DocumentLoadError: If the file cannot be parsed as valid JSON/YAML
                or does not contain a valid OpenAPI structure.
        """
        spec = self._parse_content(file_path, content)
        self._validate_spec(file_path, spec)

        units: list[DocumentUnit] = []
        position = 0

        # Extract API info/description as a heading unit if present
        info = spec.get("info", {})
        if info:
            info_content = self._format_info(info, spec)
            units.append(
                DocumentUnit(
                    content=info_content,
                    unit_type="heading",
                    metadata={
                        "title": info.get("title", ""),
                        "version": info.get("version", ""),
                        "description": info.get("description", ""),
                    },
                    source_path=file_path,
                    position=position,
                )
            )
            position += 1

        # Extract each endpoint
        paths = spec.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                # Skip non-HTTP method keys (e.g., "parameters", "$ref")
                if method.lower() not in (
                    "get", "post", "put", "delete", "patch", "head", "options", "trace"
                ):
                    continue

                if not isinstance(operation, dict):
                    continue

                endpoint_content = self._format_endpoint(
                    method, path, operation, spec
                )
                operation_id = operation.get("operationId", "")
                tags = operation.get("tags", [])
                summary = operation.get("summary", "")

                units.append(
                    DocumentUnit(
                        content=endpoint_content,
                        unit_type="api_endpoint",
                        metadata={
                            "method": method.upper(),
                            "path": path,
                            "operation_id": operation_id,
                            "tags": tags,
                            "summary": summary,
                        },
                        source_path=file_path,
                        position=position,
                    )
                )
                position += 1

        # Determine format
        doc_format = self._detect_format(file_path)

        # Build structural info
        structural_info = self._build_structural_info(spec)

        # Build raw text representation
        raw_text = "\n\n".join(unit.content for unit in units)

        return LoadedDocument(
            source_path=file_path,
            format=doc_format,
            units=units,
            raw_text=raw_text,
            structural_info=structural_info,
        )

    def _parse_content(self, file_path: str, content: bytes) -> dict[str, Any]:
        """Parse raw bytes as JSON or YAML.

        Tries JSON first, then falls back to YAML.

        Args:
            file_path: Path for error reporting.
            content: Raw file bytes.

        Returns:
            Parsed specification as a dictionary.

        Raises:
            DocumentLoadError: If content cannot be parsed.
        """
        text = content.decode("utf-8", errors="replace")

        # Try JSON first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Try YAML
        try:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError as e:
            raise DocumentLoadError(
                f"Failed to parse '{file_path}' as JSON or YAML: {e}"
            )

        raise DocumentLoadError(
            f"Failed to parse '{file_path}': content is not a valid JSON/YAML object"
        )

    def _validate_spec(self, file_path: str, spec: dict[str, Any]) -> None:
        """Validate that the parsed content looks like an OpenAPI spec.

        Args:
            file_path: Path for error reporting.
            spec: Parsed specification dictionary.

        Raises:
            DocumentLoadError: If the spec doesn't have required OpenAPI fields.
        """
        # OpenAPI 3.x uses "openapi" key, Swagger 2.x uses "swagger" key
        has_openapi = "openapi" in spec
        has_swagger = "swagger" in spec

        if not has_openapi and not has_swagger:
            raise DocumentLoadError(
                f"'{file_path}' does not appear to be a valid OpenAPI/Swagger specification. "
                f"Missing 'openapi' or 'swagger' version field."
            )

        if "paths" not in spec and "webhooks" not in spec:
            logger.warning(
                "OpenAPI spec has no paths defined",
                file_path=file_path,
            )

    def _detect_format(self, file_path: str) -> DocumentFormat:
        """Detect whether this is a JSON or YAML swagger file.

        Args:
            file_path: Path to the file.

        Returns:
            DocumentFormat.SWAGGER_JSON or DocumentFormat.SWAGGER_YAML.
        """
        lower_path = file_path.lower()
        if lower_path.endswith(".json"):
            return DocumentFormat.SWAGGER_JSON
        return DocumentFormat.SWAGGER_YAML

    def _format_info(self, info: dict[str, Any], spec: dict[str, Any]) -> str:
        """Format the API info section as readable text.

        Args:
            info: The "info" object from the spec.
            spec: The full spec (for base path extraction).

        Returns:
            Formatted text representation of the API info.
        """
        parts: list[str] = []

        title = info.get("title", "Untitled API")
        version = info.get("version", "")
        parts.append(f"# {title}")
        if version:
            parts.append(f"Version: {version}")

        description = info.get("description", "")
        if description:
            parts.append(f"\n{description}")

        # Base path info
        base_path = self._get_base_path(spec)
        if base_path:
            parts.append(f"\nBase Path: {base_path}")

        return "\n".join(parts)

    def _get_base_path(self, spec: dict[str, Any]) -> str:
        """Extract the base path/URL from the spec.

        Handles both OpenAPI 3.x (servers) and Swagger 2.x (basePath).

        Args:
            spec: The full specification dictionary.

        Returns:
            Base path string, or empty string if not found.
        """
        # OpenAPI 3.x: servers array
        servers = spec.get("servers", [])
        if servers and isinstance(servers, list) and isinstance(servers[0], dict):
            return servers[0].get("url", "")

        # Swagger 2.x: host + basePath
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        if host or base_path:
            scheme = ""
            schemes = spec.get("schemes", [])
            if schemes:
                scheme = f"{schemes[0]}://"
            return f"{scheme}{host}{base_path}"

        return ""

    def _format_endpoint(
        self,
        method: str,
        path: str,
        operation: dict[str, Any],
        spec: dict[str, Any],
    ) -> str:
        """Format a single API endpoint as readable text.

        Args:
            method: HTTP method (get, post, etc.).
            path: URL path.
            operation: The operation object from the spec.
            spec: The full spec (for resolving references).

        Returns:
            Formatted text representation of the endpoint.
        """
        parts: list[str] = []

        # Method and path
        parts.append(f"{method.upper()} {path}")

        # Summary and description
        summary = operation.get("summary", "")
        if summary:
            parts.append(f"Summary: {summary}")

        description = operation.get("description", "")
        if description:
            parts.append(f"Description: {description}")

        # Operation ID
        operation_id = operation.get("operationId", "")
        if operation_id:
            parts.append(f"Operation ID: {operation_id}")

        # Tags
        tags = operation.get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        # Parameters
        parameters = operation.get("parameters", [])
        if parameters:
            parts.append("\nParameters:")
            for param in parameters:
                if not isinstance(param, dict):
                    continue
                param_str = self._format_parameter(param)
                parts.append(f"  - {param_str}")

        # Request body (OpenAPI 3.x)
        request_body = operation.get("requestBody", {})
        if request_body and isinstance(request_body, dict):
            parts.append("\nRequest Body:")
            rb_desc = request_body.get("description", "")
            if rb_desc:
                parts.append(f"  Description: {rb_desc}")
            required = request_body.get("required", False)
            parts.append(f"  Required: {required}")
            content_types = request_body.get("content", {})
            if content_types:
                for ct, ct_info in content_types.items():
                    parts.append(f"  Content-Type: {ct}")
                    if isinstance(ct_info, dict) and "schema" in ct_info:
                        schema_str = self._format_schema(ct_info["schema"])
                        parts.append(f"    Schema: {schema_str}")

        # Responses
        responses = operation.get("responses", {})
        if responses:
            parts.append("\nResponses:")
            for status_code, response in responses.items():
                if not isinstance(response, dict):
                    continue
                resp_desc = response.get("description", "")
                parts.append(f"  {status_code}: {resp_desc}")

                # OpenAPI 3.x response content
                resp_content = response.get("content", {})
                if resp_content and isinstance(resp_content, dict):
                    for ct, ct_info in resp_content.items():
                        if isinstance(ct_info, dict) and "schema" in ct_info:
                            schema_str = self._format_schema(ct_info["schema"])
                            parts.append(f"    Content-Type: {ct}")
                            parts.append(f"    Schema: {schema_str}")

                # Swagger 2.x response schema
                resp_schema = response.get("schema", {})
                if resp_schema and isinstance(resp_schema, dict):
                    schema_str = self._format_schema(resp_schema)
                    parts.append(f"    Schema: {schema_str}")

        return "\n".join(parts)

    def _format_parameter(self, param: dict[str, Any]) -> str:
        """Format a single parameter as a readable string.

        Args:
            param: Parameter object from the spec.

        Returns:
            Formatted parameter string.
        """
        name = param.get("name", "unknown")
        location = param.get("in", "unknown")
        required = param.get("required", False)
        param_type = param.get("type", "")
        description = param.get("description", "")

        # OpenAPI 3.x uses "schema" for type info
        schema = param.get("schema", {})
        if schema and isinstance(schema, dict) and not param_type:
            param_type = schema.get("type", "")

        parts = [f"{name} (in: {location}"]
        if param_type:
            parts[0] += f", type: {param_type}"
        parts[0] += f", required: {required})"
        if description:
            parts[0] += f" - {description}"

        return parts[0]

    def _format_schema(self, schema: dict[str, Any]) -> str:
        """Format a schema object as a compact readable string.

        Args:
            schema: JSON Schema object.

        Returns:
            Compact string representation of the schema.
        """
        if not isinstance(schema, dict):
            return str(schema)

        # Handle $ref
        ref = schema.get("$ref", "")
        if ref:
            return f"$ref: {ref}"

        schema_type = schema.get("type", "object")

        # Array type
        if schema_type == "array":
            items = schema.get("items", {})
            items_str = self._format_schema(items) if isinstance(items, dict) else str(items)
            return f"array[{items_str}]"

        # Object type with properties
        if schema_type == "object" or "properties" in schema:
            properties = schema.get("properties", {})
            if properties:
                props = []
                for prop_name, prop_schema in properties.items():
                    prop_type = prop_schema.get("type", "any") if isinstance(prop_schema, dict) else "any"
                    props.append(f"{prop_name}: {prop_type}")
                return "{" + ", ".join(props) + "}"
            return "object"

        return schema_type

    def _build_structural_info(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Build structural information about the API spec.

        Args:
            spec: The full specification dictionary.

        Returns:
            Dictionary with API title, version, base path, and endpoint count.
        """
        info = spec.get("info", {})
        paths = spec.get("paths", {})

        # Count total endpoints
        endpoint_count = 0
        for path_item in paths.values():
            if isinstance(path_item, dict):
                for key in path_item:
                    if key.lower() in (
                        "get", "post", "put", "delete", "patch", "head", "options", "trace"
                    ):
                        endpoint_count += 1

        return {
            "api_title": info.get("title", ""),
            "api_version": info.get("version", ""),
            "base_path": self._get_base_path(spec),
            "endpoint_count": endpoint_count,
            "openapi_version": spec.get("openapi", spec.get("swagger", "")),
        }
