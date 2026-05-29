"""
AI 相关 Schema 定义。

包含提供商配置、对话、提示词模板的请求/响应 Schema。
"""
from marshmallow import Schema, fields, validate


# ---------------------------------------------------------------------------
# 提供商配置 Schemas
# ---------------------------------------------------------------------------

class AIProviderCreateSchema(Schema):
    """创建 AI 提供商配置请求"""
    name = fields.String(required=True, metadata={"description": "配置名称"})
    provider_type = fields.String(
        required=True,
        validate=validate.OneOf(["openai", "dashscope", "ollama"]),
        metadata={"description": "提供商类型: openai, dashscope, ollama"},
    )
    api_key = fields.String(
        load_default=None,
        metadata={"description": "API Key（Ollama 可为空）"},
    )
    base_url = fields.String(required=True, metadata={"description": "API 基础地址"})
    model_name = fields.String(required=True, metadata={"description": "模型名称"})
    is_default = fields.Boolean(load_default=False, metadata={"description": "是否为默认提供商"})
    is_enabled = fields.Boolean(load_default=True, metadata={"description": "是否启用"})


class AIProviderUpdateSchema(Schema):
    """更新 AI 提供商配置请求（所有字段可选）"""
    name = fields.String(metadata={"description": "配置名称"})
    provider_type = fields.String(
        validate=validate.OneOf(["openai", "dashscope", "ollama"]),
        metadata={"description": "提供商类型: openai, dashscope, ollama"},
    )
    api_key = fields.String(metadata={"description": "API Key"})
    base_url = fields.String(metadata={"description": "API 基础地址"})
    model_name = fields.String(metadata={"description": "模型名称"})
    is_default = fields.Boolean(metadata={"description": "是否为默认提供商"})
    is_enabled = fields.Boolean(metadata={"description": "是否启用"})


class AIProviderResponseSchema(Schema):
    """AI 提供商配置响应（API Key 脱敏）"""
    id = fields.Integer(metadata={"description": "配置 ID"})
    name = fields.String(metadata={"description": "配置名称"})
    provider_type = fields.String(metadata={"description": "提供商类型"})
    api_key_masked = fields.String(metadata={"description": "脱敏后的 API Key"})
    base_url = fields.String(metadata={"description": "API 基础地址"})
    model_name = fields.String(metadata={"description": "模型名称"})
    is_default = fields.Boolean(metadata={"description": "是否为默认提供商"})
    is_enabled = fields.Boolean(metadata={"description": "是否启用"})
    created_at = fields.String(metadata={"description": "创建时间"})
    updated_at = fields.String(metadata={"description": "更新时间"})


class AIProviderTestSchema(Schema):
    """测试 AI 提供商连接请求（未保存时使用原始参数）"""
    provider_type = fields.String(
        required=True,
        validate=validate.OneOf(["openai", "dashscope", "ollama"]),
        metadata={"description": "提供商类型"},
    )
    api_key = fields.String(
        load_default=None,
        metadata={"description": "API Key（Ollama 可为空）"},
    )
    base_url = fields.String(required=True, metadata={"description": "API 基础地址"})
    model_name = fields.String(required=True, metadata={"description": "模型名称"})


# ---------------------------------------------------------------------------
# 对话 Schemas
# ---------------------------------------------------------------------------

class ChatMessageSchema(Schema):
    """单条对话消息"""
    role = fields.String(
        required=True,
        validate=validate.OneOf(["system", "user", "assistant"]),
        metadata={"description": "角色: system, user, assistant"},
    )
    content = fields.String(required=True, metadata={"description": "消息内容"})


class AIChatRequestSchema(Schema):
    """AI 对话请求"""
    messages = fields.List(
        fields.Nested(ChatMessageSchema),
        required=True,
        metadata={"description": "消息列表"},
    )
    provider_id = fields.Integer(
        load_default=None,
        metadata={"description": "指定提供商 ID（可选，不指定则使用默认）"},
    )
    temperature = fields.Float(
        load_default=0.7,
        validate=validate.Range(min=0.0, max=2.0),
        metadata={"description": "温度参数"},
    )
    max_tokens = fields.Integer(
        load_default=2048,
        validate=validate.Range(min=1),
        metadata={"description": "最大 token 数"},
    )


class AIChatUsageSchema(Schema):
    """对话 token 用量"""
    prompt_tokens = fields.Integer(metadata={"description": "提示 token 数"})
    completion_tokens = fields.Integer(metadata={"description": "回复 token 数"})
    total_tokens = fields.Integer(metadata={"description": "总 token 数"})


class AIChatResponseSchema(Schema):
    """AI 对话响应"""
    content = fields.String(metadata={"description": "AI 回复内容"})
    usage = fields.Nested(AIChatUsageSchema, metadata={"description": "token 用量"})


# ---------------------------------------------------------------------------
# 提示词模板 Schemas
# ---------------------------------------------------------------------------

class AIPromptCreateSchema(Schema):
    """创建提示词模板请求"""
    name = fields.String(required=True, metadata={"description": "模板名称"})
    scene = fields.String(required=True, metadata={"description": "场景标识（唯一）"})
    system_prompt = fields.String(required=True, metadata={"description": "系统提示词"})
    user_prompt_template = fields.String(
        required=True,
        metadata={"description": "用户提示词模板，支持 {variable_name} 占位符"},
    )
    description = fields.String(
        load_default=None,
        metadata={"description": "模板描述"},
    )


class AIPromptUpdateSchema(Schema):
    """更新提示词模板请求（所有字段可选）"""
    name = fields.String(metadata={"description": "模板名称"})
    scene = fields.String(metadata={"description": "场景标识"})
    system_prompt = fields.String(metadata={"description": "系统提示词"})
    user_prompt_template = fields.String(
        metadata={"description": "用户提示词模板"},
    )
    description = fields.String(metadata={"description": "模板描述"})


class AIPromptResponseSchema(Schema):
    """提示词模板响应"""
    id = fields.Integer(metadata={"description": "模板 ID"})
    name = fields.String(metadata={"description": "模板名称"})
    scene = fields.String(metadata={"description": "场景标识"})
    system_prompt = fields.String(metadata={"description": "系统提示词"})
    user_prompt_template = fields.String(metadata={"description": "用户提示词模板"})
    description = fields.String(allow_none=True, metadata={"description": "模板描述"})
    is_builtin = fields.Boolean(metadata={"description": "是否为内置模板"})
    created_at = fields.String(metadata={"description": "创建时间"})
    updated_at = fields.String(metadata={"description": "更新时间"})
