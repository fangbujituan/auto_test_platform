"""
项目模型。

作者: yandc
创建时间: 2026-01-13
"""
from app.models.base import db, BaseModel


class Project(BaseModel):
    """用于组织测试用例的项目模型。"""

    __tablename__ = "projects"

    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    status = db.Column(db.Integer, default=1, comment="1: active, 0: inactive")

    cases = db.relationship("TestCase", backref="project", lazy="dynamic")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
