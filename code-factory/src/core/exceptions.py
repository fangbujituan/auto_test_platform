"""Code Factory 的自定义异常层次结构。

所有异常都携带 correlation_id 用于分布式可追溯性。
"""


class CodeFactoryError(Exception):
    """基础异常类"""

    def __init__(self, message: str, correlation_id: str = None):
        self.correlation_id = correlation_id
        super().__init__(message)


class ModelRoutingError(CodeFactoryError):
    """模型路由错误"""

    pass


class ModelTierExhaustedError(ModelRoutingError):
    """某一层级所有模型不可用"""

    def __init__(self, tier: str, attempts: int, **kwargs):
        self.tier = tier
        self.attempts = attempts
        super().__init__(
            f"All models in tier '{tier}' exhausted after {attempts} attempts",
            **kwargs,
        )


class AgentExecutionError(CodeFactoryError):
    """Agent 执行错误"""

    pass


class SchemaValidationError(AgentExecutionError):
    """输出 schema 校验失败"""

    def __init__(self, agent_name: str, errors: list[str], **kwargs):
        self.agent_name = agent_name
        self.validation_errors = errors
        super().__init__(
            f"Agent '{agent_name}' output validation failed: {errors}",
            **kwargs,
        )


class DocumentLoadError(CodeFactoryError):
    """文档加载错误"""

    pass


class UnsupportedFormatError(DocumentLoadError):
    """不支持的文档格式"""

    def __init__(self, file_path: str, supported_formats: list[str], **kwargs):
        self.file_path = file_path
        self.supported_formats = supported_formats
        super().__init__(
            f"Unsupported format for '{file_path}'. Supported: {supported_formats}",
            **kwargs,
        )


class ConfigurationError(CodeFactoryError):
    """配置错误"""

    pass


class MissingConfigError(ConfigurationError):
    """缺少必需配置"""

    def __init__(self, missing_fields: list[str], **kwargs):
        self.missing_fields = missing_fields
        super().__init__(f"Missing required config: {missing_fields}", **kwargs)
