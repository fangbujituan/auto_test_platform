"""
API接口模型。

作者: yandc
创建时间: 2026-01-16
"""
from app.models.base import db, BaseModel


class Api(BaseModel):
    """API接口模型。"""

    __tablename__ = "apis"

    name = db.Column(db.String(200), nullable=False, comment="接口名称")
    description = db.Column(db.Text, comment="接口描述")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), comment="所属目录ID")
    
    # API基本信息
    method = db.Column(db.String(10), default="GET", comment="HTTP方法")
    path = db.Column(db.String(500), nullable=False, comment="接口路径")
    base_url = db.Column(db.String(200), comment="基础URL")
    
    # 请求信息
    headers = db.Column(db.JSON, comment="请求头")
    params = db.Column(db.JSON, comment="查询参数")
    body = db.Column(db.JSON, comment="请求体")
    body_type = db.Column(db.String(20), default="json", comment="请求体类型: json, form, raw")
    
    # 响应信息
    response_example = db.Column(db.JSON, comment="响应示例")
    
    # 模块/服务（用于前置URL匹配）
    module = db.Column(db.String(200), nullable=True, comment="所属模块")
    service = db.Column(db.String(200), nullable=True, comment="所属服务")
    
    # 绑定的前置URL（持久化记忆）
    prefix_url_id = db.Column(db.Integer, db.ForeignKey("prefix_urls.id", ondelete="SET NULL"),
                              nullable=True, comment="绑定的前置URL ID")

    # === api_engine 引擎能力字段（Phase 2 新增）===
    # 与 app/engine/api_engine/specs.py 的 AssertionRule / ExtractRule 一一对应
    assertions = db.Column(db.JSON, nullable=True,
                           comment="断言规则数组：[{type, config, name?}]")
    extracts = db.Column(db.JSON, nullable=True,
                         comment="抽取规则数组：[{name, type, expression, default?}]")
    timeout = db.Column(db.Integer, nullable=True,
                        comment="单接口超时秒数；为空时使用引擎默认 30 秒")

    # 其他
    status = db.Column(db.Integer, default=1, comment="1: 启用, 0: 禁用")
    category = db.Column(db.String(50), comment="接口分类")
    tags = db.Column(db.JSON, comment="标签")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "project_id": self.project_id,
            "folder_id": self.folder_id,
            "method": self.method,
            "path": self.path,
            "base_url": self.base_url,
            "headers": self.headers or {},
            "params": self.params or {},
            "body": self.body or {},
            "body_type": self.body_type,
            "response_example": self.response_example or {},
            "module": self.module,
            "service": self.service,
            "prefix_url_id": self.prefix_url_id,
            # api_engine 字段：未配置时返回空数组 / None，前端不感知 NULL 与 [] 差异
            "assertions": self.assertions or [],
            "extracts": self.extracts or [],
            "timeout": self.timeout,
            "status": self.status,
            "category": self.category,
            "tags": self.tags or [],
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
