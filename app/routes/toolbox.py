"""
工具箱接口
提供各种测试工具的后端支持
"""
import os
import json
import tempfile
from flask import request, jsonify, current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from app.tools.toolbox.test_case_generator import (
    TestCaseGenerator,
    FieldConstraint,
    FieldType
)
from app.tools.tool_excel_db.excel_db_comparator import ExcelDBComparator
from app.schemas.common import MessageResponseSchema

toolbox_blp = Blueprint(
    'toolbox', __name__,
    url_prefix='/api/toolbox',
    description="工具箱"
)

# 向后兼容
toolbox_bp = toolbox_blp

# Excel文件上传配置
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def convert_field_type(type_str):
    """将字符串转换为 FieldType 枚举"""
    type_mapping = {
        'string': FieldType.STRING,
        'integer': FieldType.INTEGER,
        'float': FieldType.FLOAT,
        'boolean': FieldType.BOOLEAN,
        'array': FieldType.ARRAY,
        'object': FieldType.OBJECT,
        'email': FieldType.EMAIL,
        'phone': FieldType.PHONE,
        'date': FieldType.DATE,
    }
    return type_mapping.get(type_str, FieldType.STRING)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@toolbox_blp.route('/generate-test-cases')
class GenerateTestCasesView(MethodView):
    """生成测试用例"""

    @toolbox_blp.response(200, MessageResponseSchema)
    @toolbox_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @toolbox_blp.alt_response(500, schema=MessageResponseSchema, description="生成失败")
    def post(self):
        """生成测试用例。"""
        try:
            data = request.get_json()

            if not data.get('tool_name'):
                return jsonify({'error': '工具名称不能为空'}), 400

            if not data.get('base_params'):
                return jsonify({'error': '基准参数不能为空'}), 400

            if not data.get('constraints'):
                return jsonify({'error': '字段约束不能为空'}), 400

            base_params = data.get('base_params')
            if isinstance(base_params, str):
                base_params = json.loads(base_params)

            constraints_data = data.get('constraints')
            if isinstance(constraints_data, str):
                constraints_data = json.loads(constraints_data)

            constraints = []
            for cd in constraints_data:
                field_type = convert_field_type(
                    cd.get('field_type', 'string')
                )

                constraint = FieldConstraint(
                    field_name=cd.get('field_name'),
                    field_type=field_type,
                    required=cd.get('required', True),
                    min_length=cd.get('min_length'),
                    max_length=cd.get('max_length'),
                    min_value=cd.get('min_value'),
                    max_value=cd.get('max_value'),
                    pattern=cd.get('pattern'),
                    enum_values=cd.get('enum_values'),
                    unique=cd.get('unique', False),
                    description=cd.get('description', '')
                )
                constraints.append(constraint)

            generator = TestCaseGenerator(base_params, constraints)

            test_cases = generator.generate_all_cases(
                include_positive=data.get('include_positive', True),
                include_negative=data.get('include_negative', True),
                include_boundary=data.get('include_boundary', True),
                include_combination=data.get(
                    'include_combination', True
                ),
                combination_depth=2
            )

            test_data_folder = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'test_data'
            )

            saved_files = generator.save_to_folder(
                folder_path=test_data_folder,
                file_prefix=data.get('tool_name', 'test_case'),
                formats=['json', 'markdown']
            )

            stats = generator.get_statistics()

            return jsonify({
                'success': True,
                'message': '用例生成成功',
                'stats': stats,
                'files': [
                    os.path.basename(
                        saved_files.get('json', '')
                    ),
                    os.path.basename(
                        saved_files.get('markdown', '')
                    )
                ]
            }), 200

        except json.JSONDecodeError as e:
            return jsonify({
                'error': f'JSON 格式错误: {str(e)}'
            }), 400
        except ValueError as e:
            return jsonify({
                'error': f'参数错误: {str(e)}'
            }), 400
        except Exception as e:
            return jsonify({
                'error': f'生成失败: {str(e)}'
            }), 500


@toolbox_blp.route('/compare-excel-db')
class CompareExcelDbView(MethodView):
    """Excel与数据库数据比对"""

    @toolbox_blp.response(200, MessageResponseSchema)
    @toolbox_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @toolbox_blp.alt_response(500, schema=MessageResponseSchema, description="比对失败")
    def post(self):
        """Excel与数据库数据比对。"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': '请上传Excel文件'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': '未选择文件'}), 400

            if not allowed_file(file.filename):
                return jsonify({
                    'error': '仅支持 .xlsx 或 .xls 格式的Excel文件'
                }), 400

            sql = request.form.get('sql')
            if not sql:
                return jsonify({'error': 'SQL语句不能为空'}), 400

            mappings_str = request.form.get('mappings')
            if not mappings_str:
                return jsonify({'error': '映射关系不能为空'}), 400

            try:
                mappings = json.loads(mappings_str)
            except json.JSONDecodeError:
                return jsonify({
                    'error': '映射关系必须是有效的JSON格式'
                }), 400

            sheet_name = request.form.get('sheet_name')

            filename = secure_filename(file.filename)
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, filename)
            file.save(file_path)

            try:
                db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']

                comparator = ExcelDBComparator(db_uri)
                report = comparator.run_compare(
                    excel_path=file_path,
                    sql=sql,
                    mapping_config=mappings,
                    sheet_name=sheet_name if sheet_name else None
                )

                return jsonify({
                    'success': True,
                    'report': report.to_dict()
                }), 200

            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)

        except ValueError as e:
            return jsonify({
                'error': f'参数错误: {str(e)}'
            }), 400
        except Exception as e:
            return jsonify({
                'error': f'比对失败: {str(e)}'
            }), 500


@toolbox_blp.route('/crack-hash')
class CrackHashView(MethodView):
    """哈希转明文 - 通过常见密码字典匹配"""

    # 内置常见密码字典
    COMMON_PASSWORDS = [
        # 纯数字
        '0', '1', '123', '1234', '12345', '123456', '1234567',
        '12345678', '123456789', '1234567890', '111111', '666666',
        '888888', '000000', '654321', '987654321',
        # 简单密码
        'password', 'password1', 'password123', 'admin', 'admin123',
        'admin888', 'root', 'root123', 'test', 'test123', 'test1234',
        'qwerty', 'qwerty123', 'abc123', 'abc1234', 'abcd1234',
        'iloveyou', 'welcome', 'monkey', 'dragon', 'master',
        'letmein', 'login', 'princess', 'sunshine', 'trustno1',
        # 常见中文拼音
        'woaini', 'woaini123', 'woaini1314', 'aini1314',
        # 带特殊字符
        'P@ssw0rd', 'P@ssword1', 'Admin@123', 'Test@123',
        'Qwer@1234', 'Pass@123', 'Pass@1234', 'Abc@1234',
        'Admin@1234', 'Root@123',
        # 键盘序列
        'qwer1234', 'asdf1234', 'zxcv1234', 'qazwsx',
        'q1w2e3r4', '1q2w3e4r', '1qaz2wsx',
    ]

    @toolbox_blp.response(200, MessageResponseSchema)
    def post(self):
        """尝试通过字典匹配破解哈希值对应的明文密码。"""
        try:
            data = request.get_json()
            hash_value = data.get('hash', '').strip()
            extra_passwords = data.get('extra_passwords', [])

            if not hash_value:
                return jsonify({'error': '哈希值不能为空'}), 400

            # 合并内置字典和用户自定义密码
            passwords_to_try = list(self.COMMON_PASSWORDS)
            if extra_passwords:
                passwords_to_try.extend(extra_passwords)

            # 逐个尝试匹配
            for pwd in passwords_to_try:
                if check_password_hash(hash_value, pwd):
                    return jsonify({
                        'success': True,
                        'found': True,
                        'password': pwd,
                        'message': f'匹配成功，明文密码为: {pwd}'
                    }), 200

            return jsonify({
                'success': True,
                'found': False,
                'password': None,
                'message': '未在字典中找到匹配的明文密码，可尝试添加自定义密码列表'
            }), 200

        except Exception as e:
            return jsonify({'error': f'破解失败: {str(e)}'}), 500
