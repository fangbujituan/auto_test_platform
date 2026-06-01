"""Code Factory 配置管理。

从环境变量（敏感信息）和 YAML 文件（非敏感信息）加载配置。
支持通过 APP_ENV 环境变量选择特定环境的配置文件。
启动时验证所有必需字段，并一次性报告所有问题。
"""

import sys
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.exceptions import MissingConfigError


class Environment(str, Enum):
    """支持的部署环境"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


# =============================================================================
# Pydantic Settings Models
# =============================================================================


class DatabaseConfig(BaseModel):
    """数据库连接配置。

    - host, port, database, user: 从 YAML 加载（非敏感信息）
    - password: 从环境变量加载（敏感信息）
    """

    host: str = Field(..., description="Database host address")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password (from env var DB_PASSWORD)")


class ModelConfig(BaseModel):
    """模型路由配置。

    - local_endpoint: 从 YAML 加载（非敏感信息）
    - cloud_api_keys: 从环境变量加载（敏感信息）
    - default_temperature, default_max_tokens: 从 YAML 加载
    """

    local_endpoint: str = Field(..., description="Local model endpoint (Ollama/vLLM)")
    cloud_api_keys: dict[str, str] = Field(
        default_factory=dict,
        description="Cloud provider API keys (provider -> key)",
    )
    default_temperature: float = Field(default=0.7, description="Default LLM temperature")
    default_max_tokens: int = Field(default=4096, description="Default max tokens for LLM")


class AppConfig(BaseSettings):
    """主应用配置。

    结合环境变量（敏感信息）和 YAML 配置（非敏感信息）。
    APP_ENV 变量选择要加载的环境 YAML 文件。
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Environment selection
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment",
    )

    # Nested configs
    database: DatabaseConfig
    model: ModelConfig

    # App-level settings (non-sensitive, from YAML)
    log_level: str = Field(default="INFO", description="Application log level")
    vector_store_collection: str = Field(
        default="knowledge_base",
        description="Vector store collection name",
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Minimum similarity score for RAG retrieval",
    )
    review_timeout_seconds: int = Field(
        default=3600,
        description="Timeout for human review in seconds",
    )


# =============================================================================
# YAML Loading
# =============================================================================


def _find_config_dir() -> Path:
    """查找相对于项目根目录的配置目录。"""
    # Try common locations
    candidates = [
        Path.cwd() / "config" / "environments",
        Path(__file__).resolve().parent.parent.parent / "config" / "environments",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return Path.cwd() / "config" / "environments"


def load_yaml_config(environment: str, config_dir: Optional[Path] = None) -> dict[str, Any]:
    """加载特定环境的 YAML 配置文件。

    Args:
        environment: 环境名称（development, testing, production）。
        config_dir: 可选的 config/environments 目录路径。

    Returns:
        YAML 文件中的配置值字典。

    Raises:
        MissingConfigError: 如果环境的 YAML 文件不存在。
    """
    if config_dir is None:
        config_dir = _find_config_dir()

    yaml_path = config_dir / f"{environment}.yaml"

    if not yaml_path.exists():
        raise MissingConfigError(
            missing_fields=[f"config file: {yaml_path}"],
        )

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data


# =============================================================================
# Environment Variable Loading
# =============================================================================


def _load_sensitive_env_vars() -> dict[str, Any]:
    """从环境变量加载敏感值。

    返回一个包含敏感配置值的字典，这些值应覆盖 YAML 配置。
    """
    import os

    sensitive = {}

    # Database password
    db_password = os.environ.get("DB_PASSWORD")
    if db_password:
        sensitive.setdefault("database", {})["password"] = db_password

    # Cloud API keys
    cloud_keys: dict[str, str] = {}
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        cloud_keys["anthropic"] = anthropic_key
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        cloud_keys["deepseek"] = deepseek_key

    if cloud_keys:
        sensitive.setdefault("model", {})["cloud_api_keys"] = cloud_keys

    return sensitive


# =============================================================================
# Configuration Validation
# =============================================================================


def validate_config(config_dict: dict[str, Any]) -> list[str]:
    """验证配置字典并返回所有发现的错误。

    此函数不会在第一个错误时抛出异常。相反，它会收集所有验证问题，
    并将它们作为描述性错误消息列表返回。

    Args:
        config_dict: 合并后的配置字典。

    Returns:
        错误消息列表。空列表表示配置有效。
    """
    errors: list[str] = []

    # Check database section
    db = config_dict.get("database")
    if db is None:
        errors.append("Missing required section: 'database'")
    else:
        if not isinstance(db, dict):
            errors.append("'database' must be a mapping")
        else:
            for field in ("host", "database", "user", "password"):
                value = db.get(field)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    errors.append(f"Missing required field: 'database.{field}'")
            port = db.get("port")
            if port is not None:
                try:
                    port_int = int(port)
                    if port_int < 1 or port_int > 65535:
                        errors.append(
                            f"Invalid value for 'database.port': {port} (must be 1-65535)"
                        )
                except (ValueError, TypeError):
                    errors.append(f"Invalid value for 'database.port': {port} (must be an integer)")

    # Check model section
    model = config_dict.get("model")
    if model is None:
        errors.append("Missing required section: 'model'")
    else:
        if not isinstance(model, dict):
            errors.append("'model' must be a mapping")
        else:
            local_endpoint = model.get("local_endpoint")
            if local_endpoint is None or (
                isinstance(local_endpoint, str) and local_endpoint.strip() == ""
            ):
                errors.append("Missing required field: 'model.local_endpoint'")

            temperature = model.get("default_temperature")
            if temperature is not None:
                try:
                    temp_float = float(temperature)
                    if temp_float < 0.0 or temp_float > 2.0:
                        errors.append(
                            f"Invalid value for 'model.default_temperature': {temperature} "
                            f"(must be between 0.0 and 2.0)"
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"Invalid value for 'model.default_temperature': {temperature} "
                        f"(must be a number)"
                    )

            max_tokens = model.get("default_max_tokens")
            if max_tokens is not None:
                try:
                    tokens_int = int(max_tokens)
                    if tokens_int < 1:
                        errors.append(
                            f"Invalid value for 'model.default_max_tokens': {max_tokens} "
                            f"(must be positive)"
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"Invalid value for 'model.default_max_tokens': {max_tokens} "
                        f"(must be an integer)"
                    )

    # Check environment
    env = config_dict.get("environment")
    if env is not None:
        valid_envs = [e.value for e in Environment]
        if env not in valid_envs:
            errors.append(
                f"Invalid value for 'environment': '{env}' "
                f"(must be one of: {valid_envs})"
            )

    # Check log_level
    log_level = config_dict.get("log_level")
    if log_level is not None:
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if str(log_level).upper() not in valid_levels:
            errors.append(
                f"Invalid value for 'log_level': '{log_level}' "
                f"(must be one of: {list(valid_levels)})"
            )

    # Check similarity_threshold
    threshold = config_dict.get("similarity_threshold")
    if threshold is not None:
        try:
            thresh_float = float(threshold)
            if thresh_float < 0.0 or thresh_float > 1.0:
                errors.append(
                    f"Invalid value for 'similarity_threshold': {threshold} "
                    f"(must be between 0.0 and 1.0)"
                )
        except (ValueError, TypeError):
            errors.append(
                f"Invalid value for 'similarity_threshold': {threshold} "
                f"(must be a number)"
            )

    return errors


# =============================================================================
# Configuration Loading Entry Point
# =============================================================================


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典。覆盖值优先。"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    config_dir: Optional[Path] = None,
    env_override: Optional[str] = None,
) -> AppConfig:
    """加载并验证应用配置。

    加载顺序（后加载的覆盖先加载的）：
    1. 环境特定的 YAML 文件（非敏感默认值）
    2. 环境变量（敏感值）

    Args:
        config_dir: 可选的 config/environments 目录路径。
        env_override: 可选的环境名称覆盖（替代 APP_ENV 环境变量）。

    Returns:
        验证后的 AppConfig 实例。

    Raises:
        MissingConfigError: 如果必需的配置缺失或无效。
        SystemExit: 如果通过 load_config_or_exit 调用且配置无效。
    """
    import os

    # Determine environment
    environment = env_override or os.environ.get("APP_ENV", "development")

    # Load YAML config
    yaml_config = load_yaml_config(environment, config_dir)

    # Load sensitive env vars
    env_vars = _load_sensitive_env_vars()

    # Merge: YAML base + env var overrides
    merged = _deep_merge(yaml_config, env_vars)
    merged["environment"] = environment

    # Validate all fields and collect errors
    errors = validate_config(merged)
    if errors:
        raise MissingConfigError(missing_fields=errors)

    # Build the AppConfig using Pydantic
    try:
        config = AppConfig(**merged)
    except ValidationError as e:
        # Convert Pydantic validation errors to our format
        pydantic_errors = []
        for err in e.errors():
            loc = ".".join(str(part) for part in err["loc"])
            pydantic_errors.append(f"{loc}: {err['msg']}")
        raise MissingConfigError(missing_fields=pydantic_errors) from e

    return config


def load_config_or_exit(
    config_dir: Optional[Path] = None,
    env_override: Optional[str] = None,
) -> AppConfig:
    """加载配置或以非零退出码终止进程。

    这是应用启动的推荐入口点。
    如果配置无效，它会打印所有验证错误并退出。

    Args:
        config_dir: 可选的 config/environments 目录路径。
        env_override: 可选的环境名称覆盖。

    Returns:
        成功时返回验证后的 AppConfig 实例。
    """
    try:
        return load_config(config_dir=config_dir, env_override=env_override)
    except MissingConfigError as e:
        print("=" * 60, file=sys.stderr)
        print("CONFIGURATION ERROR - Application cannot start", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        print("The following configuration issues were found:", file=sys.stderr)
        print("", file=sys.stderr)
        for i, field in enumerate(e.missing_fields, 1):
            print(f"  {i}. {field}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Please check your environment variables and YAML config files.",
            file=sys.stderr,
        )
        print("=" * 60, file=sys.stderr)
        sys.exit(1)
