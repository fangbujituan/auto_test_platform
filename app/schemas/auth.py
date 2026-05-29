"""
身份验证相关的 Schema 定义。

用于请求参数校验和 Swagger 文档生成。
"""
from marshmallow import Schema, fields, validate


class LoginRequestSchema(Schema):
    """登录请求"""
    username = fields.String(required=True, metadata={"description": "用户名"})
    password = fields.String(required=True, metadata={"description": "密码"})


class LoginDataSchema(Schema):
    """登录成功返回的数据"""
    token = fields.String(metadata={"description": "认证令牌"})
    username = fields.String(metadata={"description": "用户名"})


class LoginResponseSchema(Schema):
    """登录响应"""
    code = fields.Integer(metadata={"description": "状态码，0表示成功"})
    message = fields.String(metadata={"description": "提示信息"})
    data = fields.Nested(LoginDataSchema)


class MessageResponseSchema(Schema):
    """通用消息响应"""
    code = fields.Integer(metadata={"description": "状态码，0表示成功"})
    message = fields.String(metadata={"description": "提示信息"})


class CurrentUserDataSchema(Schema):
    """当前用户信息"""
    id = fields.Integer(metadata={"description": "用户ID"})
    username = fields.String(metadata={"description": "用户名"})
    email = fields.String(metadata={"description": "邮箱"})
    status = fields.Integer(metadata={"description": "状态: 1启用 0禁用"})
    roles = fields.List(fields.String(), metadata={"description": "角色列表"})
    created_at = fields.String(metadata={"description": "创建时间"})
    last_login = fields.String(allow_none=True, metadata={"description": "最后登录时间"})


class CurrentUserResponseSchema(Schema):
    """当前用户响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    data = fields.Nested(CurrentUserDataSchema)


class InitUsersDataSchema(Schema):
    """初始化用户返回的数据"""
    users = fields.List(fields.String(), metadata={"description": "创建的用户列表"})


class InitUsersResponseSchema(Schema):
    """初始化用户响应"""
    code = fields.Integer(metadata={"description": "状态码"})
    message = fields.String(metadata={"description": "提示信息"})
    data = fields.Nested(InitUsersDataSchema)


class UpdateProfileRequestSchema(Schema):
    """更新用户资料请求"""
    email = fields.Email(required=True, metadata={"description": "新邮箱地址"})


class ChangePasswordRequestSchema(Schema):
    """修改密码请求"""
    current_password = fields.String(required=True, metadata={"description": "当前密码"})
    new_password = fields.String(required=True, validate=validate.Length(min=6), metadata={"description": "新密码"})
