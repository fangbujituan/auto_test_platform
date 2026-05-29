"""
冲刺（Sprint）模型。

作者: yandc
创建时间: 2026-03-12
"""
from app.models.base import db, BaseModel


class Sprint(BaseModel):
    """冲刺模型，用于敏捷迭代管理。"""

    __tablename__ = "sprints"

    name = db.Column(db.String(100), nullable=False, comment="冲刺名称")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, comment="关联项目ID")
    start_date = db.Column(db.DateTime, nullable=False, comment="开始时间")
    end_date = db.Column(db.DateTime, nullable=False, comment="结束时间")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, comment="创建人ID")
    status = db.Column(db.String(20), default="planning", comment="状态: planning, active, completed, cancelled")
    goal = db.Column(db.Text, comment="冲刺目标")

    # 关系
    creator = db.relationship("User", foreign_keys=[creator_id], backref="created_sprints")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "start_date": self.start_date.strftime("%Y-%m-%d %H:%M:%S") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d %H:%M:%S") if self.end_date else None,
            "creator_id": self.creator_id,
            "creator_name": self.creator.username if self.creator else None,
            "status": self.status,
            "goal": self.goal,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
