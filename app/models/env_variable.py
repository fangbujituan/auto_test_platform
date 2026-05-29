"""
环境变量模型。

作者: yandc
创建时间: 2026-04-03
"""
from app.models.base import db, BaseModel


class Environment(BaseModel):
    """环境分组模型。"""

    __tablename__ = "environments"

    name = db.Column(db.String(200), nullable=False, comment="环境名称")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    is_shared = db.Column(db.Boolean, default=False, comment="是否共享")

    prefix_urls = db.relationship("PrefixUrl", backref="environment", lazy="dynamic",
                                  cascade="all, delete-orphan")
    variables = db.relationship("EnvironmentVariable", backref="environment", lazy="dynamic")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "is_shared": self.is_shared,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class PrefixUrl(BaseModel):
    """前置URL模型，按模块/服务维度配置。"""

    __tablename__ = "prefix_urls"

    environment_id = db.Column(db.Integer, db.ForeignKey("environments.id"), nullable=False)
    module = db.Column(db.String(200), nullable=False, default="", comment="模块")
    service = db.Column(db.String(200), nullable=False, default="", comment="服务")
    url = db.Column(db.String(500), nullable=False, default="", comment="前置URL")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "environment_id": self.environment_id,
            "module": self.module,
            "service": self.service,
            "url": self.url,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }



class GlobalVariable(BaseModel):
    """全局变量模型，跨环境共享，优先级低于环境变量。"""

    __tablename__ = "global_variables"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False, comment="变量名")
    value = db.Column(db.Text, nullable=False, default="", comment="变量值")

    __table_args__ = (
        db.UniqueConstraint("project_id", "name", name="uq_global_variable_project_name"),
    )

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "value": self.value,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class GlobalParam(BaseModel):
    """全局参数模型，仅支持Header类型，自动附加到所有请求。"""

    __tablename__ = "global_params"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False, comment="参数名")
    value = db.Column(db.Text, nullable=False, default="", comment="参数值")
    description = db.Column(db.String(500), default="", comment="说明")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "value": self.value,
            "description": self.description or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class EnvironmentVariable(BaseModel):
    """环境变量模型。"""

    __tablename__ = "environment_variables"

    name = db.Column(db.String(200), nullable=False, comment="变量名")
    value = db.Column(db.Text, nullable=False, default="", comment="变量值")
    remark = db.Column(db.String(500), default="", comment="备注")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    environment_id = db.Column(db.Integer, db.ForeignKey("environments.id"), nullable=True,
                               comment="所属环境ID，可为空兼容旧数据")

    __table_args__ = (
        db.UniqueConstraint("project_id", "name", name="uq_project_variable_name"),
    )

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "remark": self.remark or "",
            "project_id": self.project_id,
            "environment_id": self.environment_id,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
