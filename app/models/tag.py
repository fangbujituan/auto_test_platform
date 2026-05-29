"""
标签模型。

作者: yandc
创建时间: 2026-03-12
"""
from app.models.base import db, BaseModel


# 需求-标签关联表
requirement_tags = db.Table(
    "requirement_tags",
    db.Column("requirement_id", db.Integer, db.ForeignKey("requirements.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Tag(BaseModel):
    """标签模型。"""

    __tablename__ = "tags"

    name = db.Column(db.String(50), nullable=False, unique=True, comment="标签名称")
    color = db.Column(db.String(20), default="#409EFF", comment="标签颜色")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
