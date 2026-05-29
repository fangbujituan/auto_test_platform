"""通用 Schema 定义。"""
from marshmallow import Schema, fields


class MessageResponseSchema(Schema):
    """通用消息响应"""
    code = fields.Integer(metadata={"description": "状态码，0表示成功"})
    message = fields.String(metadata={"description": "提示信息"})


class PaginationSchema(Schema):
    """分页参数"""
    page = fields.Integer(load_default=1, metadata={"description": "页码"})
    per_page = fields.Integer(load_default=20, metadata={"description": "每页数量"})
