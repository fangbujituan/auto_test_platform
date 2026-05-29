"""API 接口管理相关 Schema。"""
from marshmallow import Schema, fields


class ApiCreateSchema(Schema):
    """创建 API 接口请求"""
    name = fields.String(required=True, metadata={"description": "接口名称"})
    description = fields.String(metadata={"description": "接口描述"})
    folder_id = fields.Integer(metadata={"description": "所属目录ID"})
    method = fields.String(load_default="GET", metadata={"description": "HTTP方法"})
    path = fields.String(required=True, metadata={"description": "接口路径"})
    base_url = fields.String(metadata={"description": "基础URL"})
    headers = fields.Dict(load_default={}, metadata={"description": "请求头"})
    params = fields.Dict(load_default={}, metadata={"description": "查询参数"})
    body = fields.Dict(load_default={}, metadata={"description": "请求体"})
    body_type = fields.String(load_default="json", metadata={"description": "请求体类型"})
    response_example = fields.Dict(load_default={}, metadata={"description": "响应示例"})
    status = fields.Integer(load_default=1, metadata={"description": "状态"})
    category = fields.String(metadata={"description": "分类"})
    tags = fields.List(fields.String(), load_default=[], metadata={"description": "标签"})


class ApiUpdateSchema(Schema):
    """更新 API 接口请求"""
    name = fields.String(metadata={"description": "接口名称"})
    description = fields.String(metadata={"description": "接口描述"})
    folder_id = fields.Integer(metadata={"description": "所属目录ID"})
    method = fields.String(metadata={"description": "HTTP方法"})
    path = fields.String(metadata={"description": "接口路径"})
    base_url = fields.String(metadata={"description": "基础URL"})
    headers = fields.Dict(metadata={"description": "请求头"})
    params = fields.Dict(metadata={"description": "查询参数"})
    body = fields.Dict(metadata={"description": "请求体"})
    body_type = fields.String(metadata={"description": "请求体类型"})
    response_example = fields.Dict(metadata={"description": "响应示例"})
    status = fields.Integer(metadata={"description": "状态"})
    category = fields.String(metadata={"description": "分类"})
    tags = fields.List(fields.String(), metadata={"description": "标签"})


class ApiTestSchema(Schema):
    """测试 API 接口请求"""
    method = fields.String(metadata={"description": "HTTP方法（覆盖）"})
    base_url = fields.String(metadata={"description": "基础URL（覆盖）"})
    path = fields.String(metadata={"description": "接口路径（覆盖）"})
    headers = fields.Dict(metadata={"description": "请求头（覆盖）"})
    params = fields.Dict(metadata={"description": "查询参数（覆盖）"})
    body = fields.Dict(metadata={"description": "请求体（覆盖）"})
    body_type = fields.String(metadata={"description": "请求体类型（覆盖）"})


class ApiQuerySchema(Schema):
    """查询 API 接口参数"""
    category = fields.String(metadata={"description": "分类"})
    status = fields.Integer(metadata={"description": "状态"})
    keyword = fields.String(metadata={"description": "搜索关键词"})


class FolderCreateSchema(Schema):
    """创建目录请求"""
    name = fields.String(required=True, metadata={"description": "目录名称"})
    description = fields.String(metadata={"description": "目录描述"})
    parent_id = fields.Integer(metadata={"description": "父目录ID"})
    sort_order = fields.Integer(load_default=0, metadata={"description": "排序"})


class FolderUpdateSchema(Schema):
    """更新目录请求"""
    name = fields.String(metadata={"description": "目录名称"})
    description = fields.String(metadata={"description": "目录描述"})
    parent_id = fields.Integer(metadata={"description": "父目录ID"})
    sort_order = fields.Integer(metadata={"description": "排序"})
