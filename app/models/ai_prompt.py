"""
AI 提示词模板模型。

作者: yandc
创建时间: 2026-02-10
"""
from app.models.base import db, BaseModel


class AIPromptTemplate(BaseModel):
    """AI 提示词模板模型，存储不同业务场景的提示词模板。"""

    __tablename__ = "ai_prompt_templates"

    name = db.Column(db.String(100), nullable=False, comment="模板名称")
    scene = db.Column(
        db.String(100), nullable=False, unique=True, comment="场景标识"
    )
    system_prompt = db.Column(db.Text, nullable=False, comment="系统提示词")
    user_prompt_template = db.Column(
        db.Text, nullable=False, comment="用户提示词模板，含 {variable} 占位符"
    )
    description = db.Column(db.String(500), nullable=True, comment="模板描述")
    is_builtin = db.Column(
        db.Boolean, default=False, comment="是否为内置模板"
    )

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "scene": self.scene,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "description": self.description,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
