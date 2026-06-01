"""Base Agent 类实现 AgentInterface 模板方法模式。

提供：
- execute(): 模板方法，包含日志、计时、状态保留和历史跟踪
- validate_output(): 针对 agent 定义的 output_schema 的 JSON schema 验证
- _process(): 子类实现实际逻辑的抽象方法

Requirements: 3.3, 3.4, 3.6
"""

import time
from abc import abstractmethod
from typing import Any

from src.core.exceptions import AgentExecutionError, SchemaValidationError
from src.core.interfaces import AgentInterface
from src.core.logging import get_logger
from src.core.models import AgentState


class BaseAgent(AgentInterface):
    """Code Factory 系统中所有 Agent 的抽象基类。

    实现模板方法模式：子类只需实现 `_process()` 和可选地重写 `output_schema` 属性。

    基类处理：
    - 执行开始/完成的结构化日志记录
    - 计时和延迟测量
    - 不可变状态字段保留（task_id, correlation_id, workflow_id）
    - 仅追加历史跟踪
    - 带 correlation_id 传播的错误处理
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 名称标识符。子类必须定义此属性。"""
        ...

    @property
    def output_schema(self) -> dict[str, Any]:
        """JSON schema for validating output_data.

        Subclasses can override this to define their expected output structure.
        Default schema accepts any non-empty dict.

        Returns:
            A dict describing the expected output schema with 'type' and
            optional 'required' and 'properties' keys.
        """
        return {"type": "object"}

    def __init__(self) -> None:
        self._logger = get_logger(f"agents.{self.name}")

    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent task using the template method pattern.

        Steps:
        1. Log execution start with agent name and input summary
        2. Preserve immutable state fields
        3. Call _process() (implemented by subclass)
        4. Log completion with output summary, latency, and model used
        5. Append invocation record to state.history
        6. Return updated state

        Args:
            state: The current agent state with input_data populated.

        Returns:
            Updated AgentState with output_data populated and history appended.

        Raises:
            AgentExecutionError: If _process() raises an unexpected error.
        """
        # Capture immutable fields for preservation
        task_id = state.task_id
        correlation_id = state.correlation_id
        workflow_id = state.workflow_id

        # Summarize input for logging
        input_summary = self._summarize(state.input_data)

        self._logger.info(
            "Agent execution started",
            agent_name=self.name,
            task_id=task_id,
            correlation_id=correlation_id,
            input_summary=input_summary,
        )

        start_time = time.perf_counter()
        model_used = "unknown"

        try:
            # Delegate to subclass implementation
            updated_state = await self._process(state)

            # Preserve immutable fields
            updated_state.task_id = task_id
            updated_state.correlation_id = correlation_id
            updated_state.workflow_id = workflow_id

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract model_used from metadata if available
            model_used = updated_state.metadata.get("model_used", "unknown")

            # Summarize output for logging
            output_summary = self._summarize(updated_state.output_data)

            self._logger.info(
                "Agent execution completed",
                agent_name=self.name,
                task_id=task_id,
                correlation_id=correlation_id,
                output_summary=output_summary,
                latency_ms=round(latency_ms, 2),
                model_used=model_used,
            )

            # Append to history (append-only)
            history_entry = {
                "agent_name": self.name,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "model_used": model_used,
                "latency_ms": round(latency_ms, 2),
                "status": "completed",
            }
            updated_state.history.append(history_entry)

            return updated_state

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000

            self._logger.error(
                "Agent execution failed",
                agent_name=self.name,
                task_id=task_id,
                correlation_id=correlation_id,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )

            # Append failure to history
            history_entry = {
                "agent_name": self.name,
                "input_summary": input_summary,
                "output_summary": "",
                "model_used": model_used,
                "latency_ms": round(latency_ms, 2),
                "status": "failed",
                "error": str(exc),
            }
            state.history.append(history_entry)

            raise AgentExecutionError(
                f"Agent '{self.name}' failed: {exc}",
                correlation_id=correlation_id,
            ) from exc

    def validate_output(self, state: AgentState) -> bool:
        """Validate the agent's output_data against the defined output_schema.

        Uses simple dict-based validation checking:
        - output_data is a dict (type: object)
        - All required fields are present
        - Field types match if 'properties' with 'type' are specified

        Args:
            state: The agent state with output_data to validate.

        Returns:
            True if output_data conforms to the schema, False otherwise.
        """
        schema = self.output_schema
        output = state.output_data

        errors = self._validate_against_schema(output, schema)

        if errors:
            self._logger.warning(
                "Output validation failed",
                agent_name=self.name,
                correlation_id=state.correlation_id,
                errors=errors,
            )
            return False

        return True

    @abstractmethod
    async def _process(self, state: AgentState) -> AgentState:
        """Process the agent task. Subclasses implement actual logic here.

        Args:
            state: The current agent state with input_data.

        Returns:
            Updated AgentState with output_data populated.
        """
        ...

    def _summarize(self, data: dict[str, Any], max_length: int = 200) -> str:
        """Create a brief summary of a data dict for logging.

        Args:
            data: The dict to summarize.
            max_length: Maximum length of the summary string.

        Returns:
            A truncated string representation of the data.
        """
        if not data:
            return "{}"
        summary = str(data)
        if len(summary) > max_length:
            return summary[:max_length] + "..."
        return summary

    def _validate_against_schema(
        self, data: Any, schema: dict[str, Any]
    ) -> list[str]:
        """Validate data against a simple JSON-schema-like dict.

        Supports:
        - "type": "object" — checks data is a dict
        - "required": [...] — checks required keys exist
        - "properties": {key: {"type": ...}} — checks field types

        Args:
            data: The data to validate.
            schema: The schema definition.

        Returns:
            A list of validation error messages (empty if valid).
        """
        errors: list[str] = []

        # Type check
        expected_type = schema.get("type")
        if expected_type == "object":
            if not isinstance(data, dict):
                errors.append(
                    f"Expected type 'object' (dict), got '{type(data).__name__}'"
                )
                return errors  # Can't validate further if not a dict

        # Required fields check
        required_fields = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in data:
                errors.append(f"Missing required field: '{field_name}'")

        # Properties type check
        properties = schema.get("properties", {})
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        for prop_name, prop_schema in properties.items():
            if prop_name not in data:
                continue  # Only validate present fields (required handles missing)

            prop_type = prop_schema.get("type")
            if prop_type and prop_type in type_map:
                expected = type_map[prop_type]
                if not isinstance(data[prop_name], expected):
                    errors.append(
                        f"Field '{prop_name}' expected type '{prop_type}', "
                        f"got '{type(data[prop_name]).__name__}'"
                    )

        return errors
