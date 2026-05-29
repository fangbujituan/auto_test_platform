"""项目成员相关 Schema。"""
from marshmallow import Schema, fields


class MemberAddSchema(Schema):
    """添加成员请求"""
    project_id = fields.Integer(required=True, metadata={"description": "项目ID"})
    user_id = fields.Integer(required=True, metadata={"description": "用户ID"})
    role = fields.String(load_default="member", metadata={"description": "角色名称"})


class MemberUpdateSchema(Schema):
    """更新成员角色请求"""
    role = fields.String(required=True, metadata={"description": "角色名称"})
