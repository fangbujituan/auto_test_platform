"""测试结果相关 Schema。"""
from marshmallow import Schema, fields


class ResultQuerySchema(Schema):
    """查询结果参数"""
    case_id = fields.Integer(metadata={"description": "用例ID"})
    page = fields.Integer(load_default=1, metadata={"description": "页码"})
    per_page = fields.Integer(load_default=20, metadata={"description": "每页数量"})
