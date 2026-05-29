"""
API目录模型。

作者: yandc
创建时间: 2026-01-16
"""
from app.models.base import db, BaseModel


class ApiFolder(BaseModel):
    """API目录模型，用于组织接口。"""

    __tablename__ = "api_folders"

    name = db.Column(db.String(200), nullable=False, comment="目录名称")
    description = db.Column(db.Text, comment="目录描述")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), comment="父目录ID")
    sort_order = db.Column(db.Integer, default=0, comment="排序")
    
    # 自关联：子目录
    children = db.relationship(
        "ApiFolder",
        backref=db.backref("parent", remote_side="ApiFolder.id"),
        lazy="dynamic"
    )

    def to_dict(self, include_children=False):
        """转换为字典。"""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        if include_children:
            result["children"] = [child.to_dict(include_children=True) for child in self.children.order_by(ApiFolder.sort_order)]
        
        return result
