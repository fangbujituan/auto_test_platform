"""
操作日志模型。

作者: yandc
创建时间: 2026-03-12
"""
from app.models.base import db, BaseModel


class OperationLog(BaseModel):
    """操作日志模型，记录用户操作行为。"""

    __tablename__ = "operation_logs"

    api_name = db.Column(db.String(200), nullable=False, comment="接口名称")
    action = db.Column(db.String(200), nullable=False, comment="操作事项")
    operator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, comment="操作人ID")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), comment="关联项目ID")
    target_type = db.Column(db.String(50), comment="操作对象类型，如 requirement, sprint")
    target_id = db.Column(db.Integer, comment="操作对象ID")
    detail = db.Column(db.Text, comment="操作详情")

    # 关系
    operator = db.relationship("User", foreign_keys=[operator_id], backref="operation_logs")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "api_name": self.api_name,
            "action": self.action,
            "operator_id": self.operator_id,
            "operator_name": self.operator.username if self.operator else None,
            "project_id": self.project_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "detail": self.detail,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
