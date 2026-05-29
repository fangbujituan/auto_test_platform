"""环境变量相关 Schema。"""
from marshmallow import Schema, fields


class EnvVariableCreateSchema(Schema):
    """创建环境变量请求"""
    name = fields.String(required=True, metadata={"description": "变量名"})
    value = fields.String(load_default="", metadata={"description": "变量值"})
    remark = fields.String(load_default="", metadata={"description": "备注"})


class EnvVariableUpdateSchema(Schema):
    """更新环境变量请求"""
    name = fields.String(required=True, metadata={"description": "变量名"})
    value = fields.String(load_default="", metadata={"description": "变量值"})
    remark = fields.String(load_default="", metadata={"description": "备注"})
