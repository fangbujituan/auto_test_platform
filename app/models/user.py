"""
用户模型。

作者: yandc
创建时间: 2026-01-14
"""
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.base import db, BaseModel


class User(BaseModel):
    """用于身份验证的用户模型。"""

    __tablename__ = "users"

    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    is_active = db.Column(db.Integer, default=1, comment="1: active, 0: inactive")

    def set_password(self, password):
        """哈希并设置密码。"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码。"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
