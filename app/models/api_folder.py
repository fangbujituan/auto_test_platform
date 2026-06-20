"""
API目录模型。

作者: yandc
创建时间: 2026-01-16
"""
from app.models.base import db, BaseModel


class ApiFolder(BaseModel):
    """API目录模型，按 type 区分接口/用例/Bug/自动化等不同维度的目录。"""

    __tablename__ = "api_folders"

    # 目录类型：api / testcase / bug / automation
    # 老数据无该字段时按 'api' 处理（迁移脚本会回填）
    TYPE_API = "api"
    TYPE_TESTCASE = "testcase"
    TYPE_BUG = "bug"
    TYPE_AUTOMATION = "automation"

    name = db.Column(db.String(200), nullable=False, comment="目录名称")
    description = db.Column(db.Text, comment="目录描述")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), comment="父目录ID")
    sort_order = db.Column(db.Integer, default=0, comment="排序")
    type = db.Column(
        db.String(20),
        nullable=False,
        default=TYPE_API,
        server_default=TYPE_API,
        index=True,
        comment="目录类型: api/testcase/bug/automation",
    )

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
            "type": self.type or self.TYPE_API,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if include_children:
            result["children"] = [
                child.to_dict(include_children=True)
                for child in self.children.order_by(ApiFolder.sort_order)
            ]

        return result
