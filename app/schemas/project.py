"""项目相关 Schema。"""
from marshmallow import Schema, fields


class ProjectCreateSchema(Schema):
    """创建项目请求"""
    name = fields.String(required=True, metadata={"description": "项目名称"})
    description = fields.String(metadata={"description": "项目描述"})


class ProjectUpdateSchema(Schema):
    """更新项目请求"""
    name = fields.String(metadata={"description": "项目名称"})
    description = fields.String(metadata={"description": "项目描述"})
    status = fields.Integer(metadata={"description": "状态: 1启用 0禁用"})
