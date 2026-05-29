"""
模块模型（支持树形结构）。

作者: yandc
创建时间: 2026-01-19
"""
from app.models.base import db, BaseModel


class Module(BaseModel):
    """测试模块模型，支持多层级树形结构。"""

    __tablename__ = "modules"

    module_no = db.Column(db.String(50), nullable=False, comment="模块编号")
    name = db.Column(db.String(200), nullable=False, comment="模块名称")
    description = db.Column(db.Text, comment="模块描述")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("modules.id"), comment="父模块ID")
    status = db.Column(db.Integer, default=1, comment="1: 启用, 0: 禁用")
    sort_order = db.Column(db.Integer, default=0, comment="排序")

    # 关系
    children = db.relationship("Module", backref=db.backref("parent", remote_side="Module.id"), lazy="dynamic")
    test_cases = db.relationship("TestCaseManagement", backref="module", lazy="dynamic")

    def to_dict(self, include_children=False):
        """转换为字典。"""
        result = {
            "id": self.id,
            "module_no": self.module_no,
            "name": self.name,
            "description": self.description,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "status": self.status,
            "sort_order": self.sort_order,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        if include_children:
            result["children"] = [child.to_dict(include_children=True) for child in self.children.order_by(Module.sort_order)]
        
        return result
