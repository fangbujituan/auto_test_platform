"""测试用例相关 Schema。"""
from marshmallow import Schema, fields


class CaseCreateSchema(Schema):
    """创建 API 测试用例请求"""
    name = fields.String(required=True, metadata={"description": "用例名称"})
    description = fields.String(metadata={"description": "用例描述"})
    project_id = fields.Integer(required=True, metadata={"description": "项目ID"})
    method = fields.String(load_default="GET", metadata={"description": "HTTP方法"})
    url = fields.String(required=True, metadata={"description": "请求URL"})
    headers = fields.Dict(metadata={"description": "请求头"})
    params = fields.Dict(metadata={"description": "查询参数"})
    body = fields.Dict(metadata={"description": "请求体"})
    expected_status = fields.Integer(load_default=200, metadata={"description": "期望状态码"})
    expected_response = fields.Dict(metadata={"description": "期望响应"})
    priority = fields.Integer(load_default=2, metadata={"description": "优先级: 1高 2中 3低"})


class CaseUpdateSchema(Schema):
    """更新 API 测试用例请求"""
    name = fields.String(metadata={"description": "用例名称"})
    description = fields.String(metadata={"description": "用例描述"})
    method = fields.String(metadata={"description": "HTTP方法"})
    url = fields.String(metadata={"description": "请求URL"})
    headers = fields.Dict(metadata={"description": "请求头"})
    params = fields.Dict(metadata={"description": "查询参数"})
    body = fields.Dict(metadata={"description": "请求体"})
    expected_status = fields.Integer(metadata={"description": "期望状态码"})
    expected_response = fields.Dict(metadata={"description": "期望响应"})
    status = fields.Integer(metadata={"description": "状态: 1启用 0禁用"})
    priority = fields.Integer(metadata={"description": "优先级"})


class CaseQuerySchema(Schema):
    """查询用例参数"""
    project_id = fields.Integer(metadata={"description": "项目ID"})
