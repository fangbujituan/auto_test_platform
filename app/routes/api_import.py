"""
API接口导入路由 - 支持cURL和Swagger格式导入。

作者: yandc
创建时间: 2026-02-25
"""
import re
import json
from urllib.parse import urlparse, parse_qs, unquote
import requests as http_requests
import yaml
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.api import Api
from app.models.api_folder import ApiFolder
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema
from app.schemas.api_import import (
    CurlPreviewRequestSchema, CurlImportRequestSchema,
    CurlPreviewResponseSchema, CurlImportResponseSchema,
    SwaggerPreviewRequestSchema, SwaggerImportRequestSchema,
    SwaggerPreviewResponseSchema, SwaggerImportResponseSchema,
    SwaggerFetchUrlRequestSchema, SwaggerFetchUrlResponseSchema,
)

import_blp = Blueprint(
    "api_import", __name__,
    url_prefix="/api/projects/<int:project_id>/apis/import",
    description="API接口导入（cURL / Swagger）"
)


def _normalize_cmd_curl(curl_str):
    """将 Windows CMD 格式的 cURL 转换为标准格式。

    CMD 用 ^ 转义特殊字符：^" → "，^\\" → "（嵌套引号），^{ → {，^} → } 等。
    """
    # ^\^" → \"（CMD 中 JSON 值里的引号，保留转义形式）
    curl_str = curl_str.replace('^\\^"', '\\"')

    # ^\\" → \"（CMD 中嵌套转义的双引号，在 data 内部表示字面引号）
    curl_str = curl_str.replace('^\\"', '\\"')

    # ^" → "（CMD 转义的普通双引号）
    curl_str = curl_str.replace('^"', '"')

    # 剩余的 ^ 转义（^{ ^} ^& ^| ^< ^> ^^ ^\ ^- 等）
    curl_str = re.sub(r'\^([{}&|<>^\\\-])', r'\1', curl_str)

    return curl_str



def parse_curl(curl_str):
    """解析cURL命令，提取HTTP请求信息。

    Returns:
        dict: {method, url, base_url, path, headers, params, body, body_type, name}
    """
    curl_str = curl_str.strip()
    if not curl_str.lower().startswith('curl'):
        raise ValueError("不是有效的cURL命令")

    # 合并多行（处理反斜杠换行）
    curl_str = re.sub(r'\\\s*\n', ' ', curl_str)
    curl_str = re.sub(r'\\\s*\r\n', ' ', curl_str)

    # 处理 Windows CMD 格式的 cURL（^转义符）
    if '^"' in curl_str or '^\\"' in curl_str:
        curl_str = _normalize_cmd_curl(curl_str)

    method = 'GET'
    url = ''
    headers = {}
    body = {}
    body_type = 'json'
    body_raw = ''

    # 提取 -X / --request 方法
    m = re.search(r'(?:-X|--request)\s+["\']?(\w+)["\']?', curl_str)
    if m:
        method = m.group(1).upper()

    # 提取 URL（支持带引号和不带引号）
    # 先尝试匹配 curl 后面紧跟的 URL
    url_match = re.search(
        r'curl\s+(?:.*?\s+)?["\']?(https?://[^\s"\']+)["\']?', curl_str
    )
    if not url_match:
        # 尝试匹配 --url 参数
        url_match = re.search(r'--url\s+["\']?(https?://[^\s"\']+)["\']?', curl_str)
    if url_match:
        url = url_match.group(1)

    # 提取所有 -H / --header
    header_matches = re.findall(
        r'(?:-H|--header)\s+["\']([^"\']+)["\']', curl_str
    )
    for h in header_matches:
        if ':' in h:
            key, val = h.split(':', 1)
            headers[key.strip()] = val.strip()

    # 提取 -d / --data / --data-raw / --data-binary
    data_match = re.search(
        r'(?:-d|--data|--data-raw|--data-binary)\s+"((?:[^"\\]|\\.)*)"|'
        r"(?:-d|--data|--data-raw|--data-binary)\s+'((?:[^'\\]|\\.)*)'",
        curl_str, re.DOTALL
    )
    if not data_match:
        # 回退：不带引号的简单匹配
        data_match = re.search(
            r'(?:-d|--data|--data-raw|--data-binary)\s+(\S+)',
            curl_str
        )
    if data_match:
        body_raw = data_match.group(1) or data_match.group(2) or ''
        # 处理转义引号
        body_raw = body_raw.replace('\\"', '"')
        if not method or method == 'GET':
            method = 'POST'

    # 提取 -F / --form（multipart form）
    form_matches = re.findall(
        r'(?:-F|--form)\s+["\']([^"\']+)["\']', curl_str
    )

    # 解析URL
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else ''
    path = parsed.path or '/'
    query_params = {}
    if parsed.query:
        for k, v in parse_qs(parsed.query).items():
            query_params[k] = v[0] if len(v) == 1 else v

    # 解析body
    if form_matches:
        body_type = 'form'
        for item in form_matches:
            if '=' in item:
                k, v = item.split('=', 1)
                body[k.strip()] = v.strip()
    elif body_raw:
        # 尝试解析为JSON
        try:
            body = json.loads(body_raw)
            body_type = 'json'
        except (json.JSONDecodeError, ValueError):
            # 尝试解析为form-urlencoded
            if '=' in body_raw and '&' in body_raw or '=' in body_raw:
                body_type = 'form'
                for pair in body_raw.split('&'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        body[unquote(k)] = unquote(v)
            else:
                body_type = 'raw'
                body = {"raw": body_raw}

    # 生成接口名称
    name = path.strip('/').split('/')[-1] if path.strip('/') else 'imported_api'

    return {
        "method": method,
        "url": url,
        "base_url": base_url,
        "path": path,
        "headers": headers,
        "params": query_params,
        "body": body,
        "body_type": body_type,
        "name": name,
        "description": f"从cURL导入: {method} {path}"
    }


def validate_swagger_data(data):
    """验证数据是否为有效的 Swagger/OpenAPI 格式。

    检查数据是否包含 swagger/openapi 版本字段和 paths 字段。

    Args:
        data: dict, 待验证的数据对象

    Returns:
        tuple[bool, str]: (is_valid, error_message)
            - 验证通过返回 (True, '')
            - 验证失败返回 (False, error_message)
    """
    if not isinstance(data, dict):
        return (False, "数据格式不正确，期望 JSON 对象")

    has_version = 'swagger' in data or 'openapi' in data
    if not has_version:
        return (False, "缺少 swagger 或 openapi 版本字段，不是有效的 Swagger/OpenAPI 文档")

    if 'paths' not in data:
        return (False, "缺少 paths 字段，不是有效的 Swagger/OpenAPI 文档")

    return (True, '')


def parse_swagger(swagger_data):
    """解析Swagger/OpenAPI JSON，提取所有API接口信息。

    Args:
        swagger_data: dict, Swagger/OpenAPI JSON对象

    Returns:
        list[dict]: 接口列表，每个元素包含 {method, path, name, description,
                     headers, params, body, body_type, tag}
    """
    apis = []
    version = swagger_data.get('openapi', swagger_data.get('swagger', ''))
    is_v3 = version.startswith('3')

    # 提取 base_url
    base_url = ''
    if is_v3:
        servers = swagger_data.get('servers', [])
        if servers:
            base_url = servers[0].get('url', '')
    else:
        # Swagger 2.0
        host = swagger_data.get('host', '')
        base_path = swagger_data.get('basePath', '')
        schemes = swagger_data.get('schemes', ['https'])
        if host:
            base_url = f"{schemes[0]}://{host}{base_path}"

    paths = swagger_data.get('paths', {})

    for path, methods in paths.items():
        for method, detail in methods.items():
            if method.lower() in ('get', 'post', 'put', 'delete', 'patch',
                                  'head', 'options'):
                api_info = _parse_swagger_operation(
                    method, path, detail, swagger_data, is_v3, base_url
                )
                apis.append(api_info)

    return apis


def _parse_swagger_operation(method, path, detail, swagger_data, is_v3,
                             base_url):
    """解析单个Swagger操作。"""
    name = detail.get('summary', '') or detail.get('operationId', '') or path
    description = detail.get('description', '')
    tags = detail.get('tags', [])
    tag = tags[0] if tags else ''

    headers = {}
    params = {}
    body = {}
    body_type = 'json'

    if is_v3:
        # OpenAPI 3.x 参数解析
        for param in detail.get('parameters', []):
            param = _resolve_ref(param, swagger_data)
            location = param.get('in', '')
            param_name = param.get('name', '')
            example = _get_param_example(param)

            if location == 'query':
                params[param_name] = example
            elif location == 'header':
                headers[param_name] = example
            elif location == 'path':
                params[f"path:{param_name}"] = example

        # 解析 requestBody
        request_body = detail.get('requestBody', {})
        request_body = _resolve_ref(request_body, swagger_data)
        if request_body:
            content = request_body.get('content', {})
            if 'application/json' in content:
                body_type = 'json'
                schema = content['application/json'].get('schema', {})
                schema = _resolve_ref(schema, swagger_data)
                body = _schema_to_example(schema, swagger_data)
            elif 'application/x-www-form-urlencoded' in content:
                body_type = 'form'
                schema = content['application/x-www-form-urlencoded'].get(
                    'schema', {}
                )
                schema = _resolve_ref(schema, swagger_data)
                body = _schema_to_example(schema, swagger_data)
            elif 'multipart/form-data' in content:
                body_type = 'form'
                schema = content['multipart/form-data'].get('schema', {})
                schema = _resolve_ref(schema, swagger_data)
                body = _schema_to_example(schema, swagger_data)
    else:
        # Swagger 2.0 参数解析
        for param in detail.get('parameters', []):
            param = _resolve_ref(param, swagger_data)
            location = param.get('in', '')
            param_name = param.get('name', '')
            example = _get_param_example(param)

            if location == 'query':
                params[param_name] = example
            elif location == 'header':
                headers[param_name] = example
            elif location == 'body':
                schema = param.get('schema', {})
                schema = _resolve_ref(schema, swagger_data)
                body = _schema_to_example(schema, swagger_data)
                body_type = 'json'
            elif location == 'formData':
                body_type = 'form'
                body[param_name] = example

    return {
        "method": method.upper(),
        "path": path,
        "base_url": base_url,
        "name": name,
        "description": description,
        "headers": headers,
        "params": params,
        "body": body,
        "body_type": body_type,
        "tag": tag,
        "tags": tags
    }


def _resolve_ref(obj, swagger_data):
    """解析 $ref 引用。"""
    if not isinstance(obj, dict):
        return obj
    ref = obj.get('$ref')
    if not ref:
        return obj

    parts = ref.lstrip('#/').split('/')
    result = swagger_data
    for part in parts:
        result = result.get(part, {})
    return result


def _get_param_example(param):
    """获取参数的示例值。"""
    if 'example' in param:
        return param['example']
    if 'default' in param:
        return param['default']

    schema = param.get('schema', {})
    type_name = schema.get('type', param.get('type', 'string'))
    type_defaults = {
        'string': '', 'integer': 0, 'number': 0,
        'boolean': False, 'array': [], 'object': {}
    }
    return type_defaults.get(type_name, '')


def _schema_to_example(schema, swagger_data, depth=0):
    """将Schema转换为示例数据。"""
    if depth > 5:
        return {}

    schema = _resolve_ref(schema, swagger_data)

    if 'example' in schema:
        return schema['example']

    schema_type = schema.get('type', 'object')

    if schema_type == 'object':
        result = {}
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            prop_schema = _resolve_ref(prop_schema, swagger_data)
            result[prop_name] = _schema_to_example(
                prop_schema, swagger_data, depth + 1
            )
        return result
    elif schema_type == 'array':
        items = schema.get('items', {})
        items = _resolve_ref(items, swagger_data)
        return [_schema_to_example(items, swagger_data, depth + 1)]
    else:
        type_defaults = {
            'string': '', 'integer': 0, 'number': 0,
            'boolean': False
        }
        return schema.get('example', schema.get('default',
                          type_defaults.get(schema_type, '')))


@import_blp.route("/curl")
class CurlImportView(MethodView):
    """cURL导入接口"""

    @import_blp.arguments(CurlImportRequestSchema)
    @import_blp.response(200, CurlImportResponseSchema)
    @import_blp.alt_response(400, schema=MessageResponseSchema, description="解析失败")
    @import_blp.alt_response(500, schema=MessageResponseSchema, description="导入失败")
    @login_required
    @check_project_permission('create')
    def post(self, data, project_id):
        """通过cURL命令导入单个API接口。"""
        curl_command = data.get('curl_command', '').strip()
        folder_id = data.get('folder_id')
        custom_name = data.get('name')

        if not curl_command:
            return jsonify({"code": 1, "message": "cURL命令不能为空"}), 400

        if not folder_id:
            return jsonify({"code": 1, "message": "请选择目标目录"}), 400

        # 验证目录存在
        folder = ApiFolder.query.filter_by(
            id=folder_id, project_id=project_id
        ).first()
        if not folder:
            return jsonify({"code": 1, "message": "目标目录不存在"}), 400

        try:
            parsed = parse_curl(curl_command)
        except ValueError as e:
            return jsonify({"code": 1, "message": f"cURL解析失败: {str(e)}"}), 400

        try:
            api = Api(
                name=custom_name or parsed['name'],
                description=parsed['description'],
                project_id=project_id,
                folder_id=folder_id,
                method=parsed['method'],
                path=parsed['path'],
                base_url=parsed['base_url'],
                headers=parsed['headers'],
                params=parsed['params'],
                body=parsed['body'],
                body_type=parsed['body_type'],
                status=1
            )
            db.session.add(api)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "导入成功",
                "data": api.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"导入失败: {str(e)}"
            }), 500


@import_blp.route("/curl/preview")
class CurlPreviewView(MethodView):
    """cURL预览（解析但不保存）"""

    @import_blp.arguments(CurlPreviewRequestSchema)
    @import_blp.response(200, CurlPreviewResponseSchema)
    @import_blp.alt_response(400, schema=MessageResponseSchema, description="解析失败")
    @login_required
    @check_project_permission('read')
    def post(self, data, project_id):
        """预览cURL解析结果，不保存到数据库。"""
        curl_command = data.get('curl_command', '').strip()

        if not curl_command:
            return jsonify({"code": 1, "message": "cURL命令不能为空"}), 400

        try:
            parsed = parse_curl(curl_command)
            return jsonify({"code": 0, "data": parsed})
        except ValueError as e:
            return jsonify({"code": 1, "message": f"解析失败: {str(e)}"}), 400


@import_blp.route("/swagger")
class SwaggerImportView(MethodView):
    """Swagger/OpenAPI导入接口"""

    @import_blp.arguments(SwaggerImportRequestSchema)
    @import_blp.response(200, SwaggerImportResponseSchema)
    @import_blp.alt_response(400, schema=MessageResponseSchema, description="解析失败")
    @import_blp.alt_response(500, schema=MessageResponseSchema, description="导入失败")
    @login_required
    @check_project_permission('create')
    def post(self, data, project_id):
        """通过Swagger/OpenAPI JSON批量导入API接口。"""
        swagger_data = data.get('swagger_data')
        folder_id = data.get('folder_id')
        create_folders = data.get('create_folders', True)
        selected_apis = data.get('selected_apis')
        override_base_url = data.get('override_base_url')

        if not swagger_data:
            return jsonify({"code": 1, "message": "Swagger数据不能为空"}), 400

        if not folder_id:
            # 未指定目录时，自动使用项目的第一个根目录
            default_folder = ApiFolder.query.filter_by(
                project_id=project_id, parent_id=None
            ).order_by(ApiFolder.id.asc()).first()
            if not default_folder:
                return jsonify({"code": 1, "message": "项目中没有目录，请先创建目录"}), 400
            folder_id = default_folder.id
        else:
            # 验证指定的目录存在
            default_folder = ApiFolder.query.filter_by(
                id=folder_id, project_id=project_id
            ).first()
            if not default_folder:
                return jsonify({"code": 1, "message": "默认目标目录不存在"}), 400

        try:
            api_list = parse_swagger(swagger_data)
        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"Swagger解析失败: {str(e)}"
            }), 400

        if not api_list:
            return jsonify({"code": 1, "message": "未解析到任何接口"}), 400

        # 如果指定了选中的接口，只导入选中的
        if selected_apis is not None:
            selected_set = set(selected_apis)
            api_list = [a for i, a in enumerate(api_list) if i in selected_set]

        try:
            # 按tag创建目录映射
            tag_folder_map = {}
            if create_folders:
                tags_set = set()
                for api_info in api_list:
                    tag = api_info.get('tag', '')
                    if tag:
                        tags_set.add(tag)

                for tag_name in tags_set:
                    # 查找已有同名目录
                    existing = ApiFolder.query.filter_by(
                        project_id=project_id, name=tag_name
                    ).first()
                    if existing:
                        tag_folder_map[tag_name] = existing.id
                    else:
                        new_folder = ApiFolder(
                            name=tag_name,
                            description=f"从Swagger导入: {tag_name}",
                            project_id=project_id,
                            parent_id=default_folder.parent_id
                        )
                        db.session.add(new_folder)
                        db.session.flush()
                        tag_folder_map[tag_name] = new_folder.id

            # 批量创建接口
            created_count = 0
            skipped_count = 0
            created_apis = []

            for idx, api_info in enumerate(api_list):
                tag = api_info.get('tag', '')
                target_folder_id = tag_folder_map.get(tag, folder_id)
                api_base_url = override_base_url or api_info.get('base_url', '')

                # 检查是否已存在相同 method+path 的接口
                existing_api = Api.query.filter_by(
                    project_id=project_id,
                    method=api_info['method'],
                    path=api_info['path']
                ).first()
                if existing_api:
                    skipped_count += 1
                    continue

                try:
                    api = Api(
                        name=api_info['name'],
                        description=api_info.get('description', ''),
                        project_id=project_id,
                        folder_id=target_folder_id,
                        method=api_info['method'],
                        path=api_info['path'],
                        base_url=api_base_url,
                        headers=api_info.get('headers', {}),
                        params=api_info.get('params', {}),
                        body=api_info.get('body', {}),
                        body_type=api_info.get('body_type', 'json'),
                        status=1,
                        category=tag,
                        tags=api_info.get('tags', [])
                    )
                    db.session.add(api)
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    error_detail = str(e)
                    return jsonify({
                        "code": 1,
                        "message": (
                            f"导入失败: 第 {idx + 1} 个接口 "
                            f"[{api_info['method']} {api_info['path']}] "
                            f"创建出错: {error_detail}"
                        ),
                        "data": {
                            "failed_index": idx,
                            "failed_api": {
                                "method": api_info['method'],
                                "path": api_info['path']
                            },
                            "error_detail": error_detail,
                            "created_before_failure": created_count
                        }
                    }), 500

                created_count += 1
                created_apis.append(api)

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": f"导入完成: 成功{created_count}个, 跳过{skipped_count}个(已存在)",
                "data": {
                    "created_count": created_count,
                    "skipped_count": skipped_count,
                    "total": len(api_list),
                    "created_folders": list(tag_folder_map.keys())
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"导入失败: {str(e)}"
            }), 500


@import_blp.route("/swagger/preview")
class SwaggerPreviewView(MethodView):
    """Swagger预览（解析但不保存）"""

    @import_blp.arguments(SwaggerPreviewRequestSchema)
    @import_blp.response(200, SwaggerPreviewResponseSchema)
    @import_blp.alt_response(400, schema=MessageResponseSchema, description="解析失败")
    @login_required
    @check_project_permission('read')
    def post(self, data, project_id):
        """预览Swagger解析结果，不保存到数据库。"""
        swagger_data = data.get('swagger_data')

        if not swagger_data:
            return jsonify({"code": 1, "message": "Swagger数据不能为空"}), 400

        try:
            api_list = parse_swagger(swagger_data)

            # 提取所有tag
            tags = set()
            for api_info in api_list:
                if api_info.get('tag'):
                    tags.add(api_info['tag'])

            return jsonify({
                "code": 0,
                "data": {
                    "apis": api_list,
                    "total": len(api_list),
                    "tags": sorted(list(tags))
                }
            })
        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"解析失败: {str(e)}"
            }), 400


@import_blp.route("/swagger/fetch-url")
class SwaggerFetchUrlView(MethodView):
    """通过 URL 获取远程 Swagger/OpenAPI 文档"""

    @import_blp.arguments(SwaggerFetchUrlRequestSchema)
    @import_blp.response(200, SwaggerFetchUrlResponseSchema)
    @import_blp.alt_response(400, schema=MessageResponseSchema, description="请求失败")
    @login_required
    @check_project_permission('create')
    def post(self, data, project_id):
        """通过 URL 获取并解析 Swagger/OpenAPI 文档。"""
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"code": 1, "message": "URL 不能为空"}), 400

        # 验证 URL 格式
        if not url.startswith('http://') and not url.startswith('https://'):
            return jsonify({
                "code": 1,
                "message": "请输入有效的 URL 地址（必须以 http:// 或 https:// 开头）"
            }), 400

        # 获取远程内容
        try:
            resp = http_requests.get(url, timeout=30)
            resp.raise_for_status()
            content = resp.text
        except http_requests.exceptions.Timeout:
            return jsonify({
                "code": 1,
                "message": "获取 Swagger 文档失败，请求超时，请检查 URL 是否可访问"
            }), 400
        except http_requests.exceptions.RequestException:
            return jsonify({
                "code": 1,
                "message": "获取 Swagger 文档失败，请检查 URL 是否可访问"
            }), 400

        # 尝试 JSON 解析，失败则尝试 YAML 解析
        parsed_data = None
        try:
            parsed_data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            try:
                parsed_data = yaml.safe_load(content)
            except yaml.YAMLError:
                return jsonify({
                    "code": 1,
                    "message": "URL 返回的内容无法解析为 JSON 或 YAML 格式"
                }), 400

        if not isinstance(parsed_data, dict):
            return jsonify({
                "code": 1,
                "message": "URL 返回的内容不是有效的 Swagger/OpenAPI 文档"
            }), 400

        # 验证 Swagger 格式
        is_valid, error_msg = validate_swagger_data(parsed_data)
        if not is_valid:
            return jsonify({
                "code": 1,
                "message": f"URL 返回的内容不是有效的 Swagger/OpenAPI 文档: {error_msg}"
            }), 400

        return jsonify({
            "code": 0,
            "data": parsed_data,
            "message": "获取成功"
        })
