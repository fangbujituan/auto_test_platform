"""
环境变量替换服务。

作者: yandc
创建时间: 2026-04-03
"""
import re
from app.models.env_variable import EnvironmentVariable, GlobalVariable, PrefixUrl, GlobalParam

# 匹配 {{变量名}} 占位符
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _replace_in_string(text, variables):
    """替换字符串中的变量占位符。"""
    if not isinstance(text, str):
        return text

    def replacer(match):
        var_name = match.group(1)
        return variables.get(var_name, match.group(0))

    return VARIABLE_PATTERN.sub(replacer, text)


def _replace_in_value(value, variables):
    """递归替换值中的变量占位符。"""
    if isinstance(value, str):
        return _replace_in_string(value, variables)
    elif isinstance(value, dict):
        return {k: _replace_in_value(v, variables) for k, v in value.items()}
    elif isinstance(value, list):
        return [_replace_in_value(item, variables) for item in value]
    return value


def replace_in_request(project_id, base_url, path, headers, params, body, body_type,
                       environment_id=None):
    """
    替换请求中所有 {{变量名}} 占位符。

    当 environment_id 为 None 时，回退到原有行为（仅查询 EnvironmentVariable）。
    当 environment_id 有值时，先加载 GlobalVariable，再加载当前环境的 EnvironmentVariable，
    环境变量覆盖同名全局变量。

    返回替换后的 (base_url, path, headers, params, body)。
    如果查询变量失败，返回原始数据。
    """
    try:
        if environment_id is None:
            # 向后兼容：原有行为，查询项目下所有 EnvironmentVariable
            records = EnvironmentVariable.query.filter_by(project_id=project_id).all()
            variables = {r.name: r.value for r in records}
        else:
            # 新逻辑：全局变量 + 环境变量，环境变量覆盖同名全局变量
            variables = {}
            # 1. 先加载全局变量（优先级低）
            global_records = GlobalVariable.query.filter_by(project_id=project_id).all()
            for r in global_records:
                variables[r.name] = r.value
            # 2. 再加载当前环境的环境变量（优先级高，覆盖同名全局变量）
            env_records = EnvironmentVariable.query.filter_by(
                project_id=project_id, environment_id=environment_id
            ).all()
            for r in env_records:
                variables[r.name] = r.value
    except Exception:
        return base_url, path, headers, params, body

    if not variables:
        return base_url, path, headers, params, body

    return (
        _replace_in_string(base_url, variables),
        _replace_in_string(path, variables),
        _replace_in_value(headers, variables),
        _replace_in_value(params, variables),
        _replace_in_value(body, variables),
    )


def resolve_prefix_url(environment_id, module=None, service=None, base_url=None):
    """
    根据接口的 module 和 service 匹配当前环境的前置 URL。

    匹配优先级：
    1. 精确匹配（module + service）
    2. 默认匹配（"默认模块" + "默认服务"）
    3. 无匹配（返回空字符串）

    当 base_url 非空时，跳过匹配（接口自带域名优先），直接返回 base_url。
    """
    # 接口自带域名优先
    if base_url:
        return base_url

    if not environment_id:
        return ""

    try:
        # 1. 精确匹配（module + service）
        if module and service:
            exact_match = PrefixUrl.query.filter_by(
                environment_id=environment_id,
                module=module,
                service=service
            ).first()
            if exact_match and exact_match.url:
                return exact_match.url

        # 2. 默认匹配（"默认模块" + "默认服务"）
        default_match = PrefixUrl.query.filter_by(
            environment_id=environment_id,
            module="默认模块",
            service="默认服务"
        ).first()
        if default_match and default_match.url:
            return default_match.url

        # 3. 无匹配
        return ""
    except Exception:
        return ""


def merge_global_params(project_id, headers=None):
    """
    查询项目的 GlobalParam 并合并到请求 Headers 中。

    请求中已有的同名 Header 优先于全局参数（不覆盖）。

    返回合并后的 headers 字典。
    """
    if headers is None:
        headers = {}

    try:
        global_params = GlobalParam.query.filter_by(project_id=project_id).all()
        for param in global_params:
            # 请求中已有的同名 Header 优先
            if param.name not in headers:
                headers[param.name] = param.value
    except Exception:
        pass

    return headers
