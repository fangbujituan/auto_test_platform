"""API 导入相关 Schema —— 用于 Swagger 文档自动生成。"""
from marshmallow import Schema, fields


# ── cURL 相关 ──────────────────────────────────────────────

class CurlPreviewRequestSchema(Schema):
    """cURL 预览请求"""
    curl_command = fields.String(
        required=True, metadata={"description": "cURL 命令字符串"}
    )


class CurlImportRequestSchema(Schema):
    """cURL 导入请求"""
    curl_command = fields.String(
        required=True, metadata={"description": "cURL 命令字符串"}
    )
    folder_id = fields.Integer(
        required=True, metadata={"description": "目标目录 ID"}
    )
    name = fields.String(
        metadata={"description": "自定义接口名称（留空则自动提取）"}
    )


class ParsedApiSchema(Schema):
    """解析后的单个 API 信息"""
    method = fields.String(metadata={"description": "HTTP 方法"})
    path = fields.String(metadata={"description": "接口路径"})
    base_url = fields.String(metadata={"description": "基础 URL"})
    name = fields.String(metadata={"description": "接口名称"})
    description = fields.String(metadata={"description": "接口描述"})
    headers = fields.Dict(metadata={"description": "请求头"})
    params = fields.Dict(metadata={"description": "查询参数"})
    body = fields.Dict(metadata={"description": "请求体"})
    body_type = fields.String(metadata={"description": "请求体类型"})


class CurlPreviewResponseSchema(Schema):
    """cURL 预览响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    data = fields.Nested(ParsedApiSchema, metadata={"description": "解析结果"})


class CurlImportResponseSchema(Schema):
    """cURL 导入成功响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    message = fields.String(metadata={"description": "提示信息"})
    data = fields.Dict(metadata={"description": "创建的 API 详情"})


# ── Swagger 相关 ───────────────────────────────────────────

class SwaggerPreviewRequestSchema(Schema):
    """Swagger 预览请求"""
    swagger_data = fields.Dict(
        required=True, metadata={"description": "Swagger/OpenAPI JSON 对象"}
    )


class SwaggerImportRequestSchema(Schema):
    """Swagger 批量导入请求"""
    swagger_data = fields.Dict(
        required=True, metadata={"description": "Swagger/OpenAPI JSON 对象"}
    )
    folder_id = fields.Integer(
        load_default=None, allow_none=True,
        metadata={"description": "默认目标目录 ID（不传则自动使用项目第一个根目录）"}
    )
    create_folders = fields.Boolean(
        load_default=True,
        metadata={"description": "是否按 tag 自动创建目录"}
    )
    selected_apis = fields.List(
        fields.Integer(),
        metadata={"description": "选中要导入的接口索引列表（不传则全部导入）"}
    )
    override_base_url = fields.String(
        metadata={"description": "覆盖 base_url（留空则使用 Swagger 中的值）"}
    )


class SwaggerPreviewApiItemSchema(Schema):
    """Swagger 预览中的单个 API 条目"""
    method = fields.String(metadata={"description": "HTTP 方法"})
    path = fields.String(metadata={"description": "接口路径"})
    base_url = fields.String(metadata={"description": "基础 URL"})
    name = fields.String(metadata={"description": "接口名称"})
    description = fields.String(metadata={"description": "接口描述"})
    headers = fields.Dict(metadata={"description": "请求头"})
    params = fields.Dict(metadata={"description": "查询参数"})
    body = fields.Dict(metadata={"description": "请求体"})
    body_type = fields.String(metadata={"description": "请求体类型"})
    tag = fields.String(metadata={"description": "所属分组"})
    tags = fields.List(fields.String(), metadata={"description": "标签列表"})


class SwaggerPreviewDataSchema(Schema):
    """Swagger 预览响应 data 字段"""
    apis = fields.List(
        fields.Nested(SwaggerPreviewApiItemSchema),
        metadata={"description": "解析出的接口列表"}
    )
    total = fields.Integer(metadata={"description": "接口总数"})
    tags = fields.List(
        fields.String(), metadata={"description": "所有分组名称"}
    )


class SwaggerPreviewResponseSchema(Schema):
    """Swagger 预览响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    data = fields.Nested(SwaggerPreviewDataSchema)


class SwaggerImportDataSchema(Schema):
    """Swagger 导入响应 data 字段"""
    created_count = fields.Integer(metadata={"description": "成功导入数量"})
    skipped_count = fields.Integer(metadata={"description": "跳过数量（已存在）"})
    total = fields.Integer(metadata={"description": "总数"})
    created_folders = fields.List(
        fields.String(), metadata={"description": "新建的目录名称列表"}
    )


class SwaggerImportResponseSchema(Schema):
    """Swagger 导入成功响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    message = fields.String(metadata={"description": "提示信息"})
    data = fields.Nested(SwaggerImportDataSchema)


# ── Swagger URL 获取相关 ──────────────────────────────────

class SwaggerFetchUrlRequestSchema(Schema):
    """通过 URL 获取 Swagger 文档"""
    url = fields.String(
        required=True, metadata={"description": "Swagger 文档 URL 地址"}
    )


class SwaggerFetchUrlResponseSchema(Schema):
    """URL 获取响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    data = fields.Dict(metadata={"description": "解析后的 Swagger JSON 数据"})
    message = fields.String(metadata={"description": "提示信息"})
