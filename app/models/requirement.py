"""
需求模型与需求状态枚举。

作者: yandc
创建时间: 2026-03-12
"""
import enum
from app.models.base import db, BaseModel


class RequirementStatus(enum.Enum):
    """需求状态枚举。"""
    DRAFT = "draft"                  # 草稿
    PENDING = "pending"              # 待评审
    APPROVED = "approved"            # 已评审
    IN_PROGRESS = "in_progress"      # 开发中
    TESTING = "testing"              # 测试中
    DONE = "done"                    # 已完成
    CLOSED = "closed"                # 已关闭
    REJECTED = "rejected"            # 已拒绝


class Requirement(BaseModel):
    """需求模型，用于敏捷开发需求管理。"""

    __tablename__ = "requirements"

    # 基本信息
    title = db.Column(db.String(200), nullable=False, comment="需求名称")
    req_number = db.Column(db.String(20), unique=True, nullable=False, comment="需求编号，规则ATP+6位数字递增")
    description = db.Column(db.Text, comment="需求描述（支持图文格式，存储HTML/Markdown）")

    # 关联关系
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, comment="关联项目ID")
    sprint_id = db.Column(db.Integer, db.ForeignKey("sprints.id"), comment="关联冲刺ID")
    assignee_ids = db.Column(db.JSON, default=list, comment="关联人员ID数组")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, comment="创建人ID")

    # 状态与优先级
    status = db.Column(
        db.String(20),
        default=RequirementStatus.DRAFT.value,
        comment="状态: draft, pending, approved, in_progress, testing, done, closed, rejected"
    )
    priority = db.Column(db.String(20), default="medium", comment="优先级: low, medium, high, critical")

    # 标签（多对多）
    tags = db.relationship("Tag", secondary="requirement_tags", backref="requirements")

    # 关系
    creator = db.relationship("User", foreign_keys=[creator_id], backref="created_requirements")
    sprint = db.relationship("Sprint", backref="requirements")

    @staticmethod
    def generate_req_number():
        """自动生成需求编号，规则 ATP + 6位数字递增。"""
        last = Requirement.query.order_by(Requirement.id.desc()).first()
        if last and last.req_number:
            num = int(last.req_number.replace("ATP", "")) + 1
        else:
            num = 1
        return f"ATP{num:06d}"

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "req_number": self.req_number,
            "description": self.description,
            "project_id": self.project_id,
            "sprint_id": self.sprint_id,
            "assignee_ids": self.assignee_ids or [],
            "creator_id": self.creator_id,
            "creator_name": self.creator.username if self.creator else None,
            "status": self.status,
            "priority": self.priority,
            "tags": [tag.to_dict() for tag in self.tags] if self.tags else [],
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
