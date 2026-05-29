"""
项目成员模型，用于项目级访问控制。

作者: yandc
创建时间: 2026-01-15
"""
from app.models.base import db, BaseModel


class ProjectMember(BaseModel):
    """项目成员模型，用于项目级权限管理。"""

    __tablename__ = "project_members"

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)

    # 关系
    project = db.relationship('Project', backref=db.backref('members', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('project_memberships', lazy='dynamic'))
    role = db.relationship('Role')

    # 唯一约束：一个用户在一个项目中只能有一个角色
    __table_args__ = (
        db.UniqueConstraint('project_id', 'user_id', name='unique_project_user'),
    )

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "role_id": self.role_id,
            "role_name": self.role.name if self.role else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
