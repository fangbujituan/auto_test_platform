"""
角色和权限模型。

作者: yandc
创建时间: 2026-01-15
"""
from app.models.base import db, BaseModel


# 角色权限关联表
role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)


class Role(BaseModel):
    """RBAC角色模型。"""

    __tablename__ = "roles"

    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200))
    is_system = db.Column(db.Integer, default=0, comment="1: system role, 0: custom role")

    permissions = db.relationship(
        'Permission',
        secondary=role_permissions,
        backref=db.backref('roles', lazy='dynamic')
    )

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_system": self.is_system,
            "permissions": [p.to_dict() for p in self.permissions],
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class Permission(BaseModel):
    """RBAC权限模型。"""

    __tablename__ = "permissions"

    name = db.Column(db.String(50), nullable=False, unique=True)
    resource = db.Column(db.String(50), nullable=False, comment="资源类型: project, case, execute")
    action = db.Column(db.String(50), nullable=False, comment="操作: create, read, update, delete, execute")
    description = db.Column(db.String(200))

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "resource": self.resource,
            "action": self.action,
            "description": self.description,
        }
