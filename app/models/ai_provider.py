"""
AI 提供商配置模型。

作者: yandc
创建时间: 2026-02-10
"""
from app.models.base import db, BaseModel


class AIProviderConfig(BaseModel):
    """AI 提供商配置模型，存储不同大模型提供商的连接信息。"""

    __tablename__ = "ai_provider_configs"

    name = db.Column(db.String(100), nullable=False, comment="配置名称")
    provider_type = db.Column(db.String(50), nullable=False, comment="提供商类型: openai, dashscope, ollama")
    api_key_encrypted = db.Column(db.Text, nullable=True, comment="加密后的 API Key")
    base_url = db.Column(db.String(500), nullable=False, comment="API 基础地址")
    model_name = db.Column(db.String(100), nullable=False, comment="模型名称")
    is_default = db.Column(db.Boolean, default=False, comment="是否为默认提供商")
    is_enabled = db.Column(db.Boolean, default=True, comment="是否启用")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "provider_type": self.provider_type,
            "api_key_encrypted": self.api_key_encrypted,
            "base_url": self.base_url,
            "model_name": self.model_name,
            "is_default": self.is_default,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
