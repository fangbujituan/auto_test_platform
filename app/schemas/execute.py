"""执行相关 Schema。"""
from marshmallow import Schema, fields


class BatchExecuteSchema(Schema):
    """批量执行请求"""
    case_ids = fields.List(fields.Integer(), required=True, metadata={"description": "用例ID列表"})
