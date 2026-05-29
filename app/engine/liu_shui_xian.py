"""
@Author: <yandc>
@Time: 2025/06/07
执行用例调度驱动·转子发动机
"""
import requests
import json
from app.utils.logger_config import logger
from app.engine.read_env import ReadEnv
from app.engine.assertion_handler import AssertionHandler, AssertionResult


class TestCaseStepResult:
    """
    表示测试用例中单个步骤的执行结果。
    """

    def __init__(self, step_name: str, passed: bool, message: str, details: dict = None, assertions: list = None):
        self.step_name = step_name
        self.passed = passed
        self.message = message
        self.details = details if details is not None else {}
        self.assertions = assertions if assertions is not None else []

    def to_dict(self):
        return {
            'step_name': self.step_name,
            'passed': self.passed,
            'message': self.message,
            'details': self.details,
            'assertions': [a.to_dict() for a in self.assertions]
        }


class LiuShuiXian:
    """
    自动化测试用例的执行引擎。
    负责发送HTTP请求、处理响应、执行断言、并记录执行过程。
    """

    def __init__(self, env: ReadEnv, assertion_handler: AssertionHandler):
        """
        :param env: 环境变量初始化器实例。
        :param assertion_handler: 断言处理器实例。
        """
        self.read_env = env
        self.assertion_handler = assertion_handler
        logger.info("======== 自动化引擎已准备就绪 =========")

    @staticmethod
    def _send_http_request(method: str, url: str, headers: dict, data: dict = None,
                           params: dict = None) -> requests.Response:
        """
        发送 HTTP 请求的私有方法。
        """
        logger.info(f"LiuShuiXian: 发送 {method} 请求到: {url}")
        logger.info(f"LiuShuiXian: 请求头: {headers}")
        if data:
            logger.info(f"LiuShuiXian: 请求体: {data}")
        if params:
            logger.debug(f"LiuShuiXian: 请求参数: {params}")

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, params=params, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, params=params, timeout=10)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            logger.info(f"LiuShuiXian: 收到响应，状态码: {response.status_code}")
            logger.debug(f"LiuShuiXian: 收到响应，响应内容: {response.text}")
            return response
        except requests.exceptions.Timeout:
            logger.error(f"LiuShuiXian: 请求超时: {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"LiuShuiXian: 请求发生错误: {e}")
            raise

    def execute_test_step(self, step_config: dict) -> TestCaseStepResult:
        """
        执行单个用例步骤。
        :param step_config: 单个用例步骤的配置字典，从数据库获取。
                            （将来删掉）例如：{
                                "step_name": "获取用户信息",
                                "method": "GET",
                                "path": "/users/{user_id}",
                                "params": {"user_id": "{user_id}"}, # 支持变量替换d'd
                                "headers": {"Authorization": "Bearer {auth_token}"}, # 支持变量替换
                                "body": {},
                                "expected_status_code": 200,
                                "assertions": [
                                    {"type": "json_contains", "key": "username", "value": "testuser"},
                                    {"type": "text_contains", "value": "success"}
                                ]
                            }
        :return: TestCaseStepResult 实例，包含步骤执行结果。
        """
        step_name = step_config.get('step_name', '未知步骤')
        logger.info(f"\n--- LiuShuiXian: 开始执行步骤: {step_name} ---")

        method = step_config.get('method', 'GET').upper()
        path = step_config.get('path', '/')
        expected_status_code = step_config.get('expected_status_code')
        assertions_config = step_config.get('assertions', [])

        # 变量替换
        current_env = self.read_env.get_env_variables()
        url = current_env.get('base_url', '') + path.format(**current_env)

        # 深度复制headers和params，避免修改原始配置
        headers = current_env.get('common_headers', {}).copy()
        step_headers = step_config.get('headers', {})
        for k, v in step_headers.items():
            headers[k] = str(v).format(**current_env) if isinstance(v, str) else v

        params = {k: str(v).format(**current_env) if isinstance(v, str) else v for k, v in
                  step_config.get('params', {}).items()}

        body = step_config.get('body', {})
        # 如果body是字符串，尝试解析为json，如果不是则直接用
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass  # 如果不是JSON字符串，就保持原样
        # 变量替换请求体中的值
        body_processed = {}
        for k, v in body.items():
            if isinstance(v, str):
                body_processed[k] = v.format(**current_env)
            else:
                body_processed[k] = v

        step_passed = True
        step_message = "步骤执行成功。"
        step_details = {}
        assertion_results = []

        try:
            response = self._send_http_request(method, url, headers, body_processed, params)
            step_details['status_code'] = response.status_code
            step_details['response_text'] = response.text

            # 执行状态码断言
            if expected_status_code:
                status_assertion = self.assertion_handler.assert_status_code(response.status_code, expected_status_code)
                assertion_results.append(status_assertion)
                if not status_assertion.passed:
                    step_passed = False
                    step_message = "状态码断言失败。"
                    # 如果断言处理器配置为终止，这里会抛出异常，因此不需要额外处理中断

            # 执行其他断言,可以在这比对每个字段{接口.字段<->数据库.字段}
            for assertion_cfg in assertions_config:
                assertion_type = assertion_cfg.get('type')
                assertion_key = assertion_cfg.get('key')
                assertion_value = assertion_cfg.get('value')

                assertion_result = None
                if assertion_type == 'json_contains':
                    try:
                        response_json = response.json()
                        assertion_result = self.assertion_handler.assert_json_contains(response_json, assertion_key,
                                                                                       assertion_value)
                    except json.JSONDecodeError:
                        msg = f"响应体不是有效的JSON，无法执行JSON断言。步骤: {step_name}"
                        logger.error(msg)
                        assertion_result = AssertionResult(False, msg, {'response_text': response.text})
                elif assertion_type == 'text_contains':
                    assertion_result = self.assertion_handler.assert_response_text_contains(response.text,
                                                                                            assertion_value)
                # 可扩展其他断言类型

                if assertion_result:
                    assertion_results.append(assertion_result)
                    if not assertion_result.passed:
                        step_passed = False
                        step_message = "有断言失败。"
                        # 如果断言处理器配置为终止，这里会抛出异常，因此不需要额外处理中断
                else:
                    logger.warning(f"LiuShuiXian: 未知断言类型: {assertion_type}")

        except AssertionError as e:
            # 如果断言处理器配置为终止，则会捕获到这里的AssertionError
            step_passed = False
            step_message = f"步骤执行因断言失败而终止: {e}"
            logger.error(f"LiuShuiXian: 步骤 '{step_name}' 终止: {e}")
        except requests.exceptions.RequestException as e:
            step_passed = False
            step_message = f"HTTP请求失败: {e}"
            logger.error(f"LiuShuiXian: 步骤 '{step_name}' HTTP请求失败: {e}")
        except Exception as e:
            step_passed = False
            step_message = f"步骤执行发生未知错误: {e}"
            logger.error(f"LiuShuiXian: 步骤 '{step_name}' 发生未知错误: {e}", exc_info=True)
        finally:
            logger.info(f"--- LiuShuiXian: 步骤 '{step_name}' 执行 {'成功' if step_passed else '失败'} ---\n")
            return TestCaseStepResult(step_name, step_passed, step_message, step_details, assertion_results)

    def execute_test_case(self, test_case_data: dict):  # -> list
        """
        执行一个测试场景，包含用例步骤。
        :param test_case_data: 单个测试用例->dict
        :return: 包含所有步骤执行结果的列表。
        """
        logger.info(f"test_case_data:{test_case_data}")
        # case_name = test_case_data.get('case_name', '未知用例')
        case_name = test_case_data.get('apiName', '未知用例')
        logger.info(f"========LiuShuiXian: 开始执行用例: {case_name} ========")

        all_step_results = []
        case_passed = True

        # 在执行每个用例前，可以考虑清空或重新初始化环境变量，以保证用例间独立性
        # self.read_env.clear_env_variables()
        # 如果用例之间有依赖，则不清除
        for step_idx, step_config in enumerate(test_case_data.get('steps', [])):
            step_config['step_name'] = f"步骤 {step_idx + 1}: {step_config.get('step_name', '无名称')}"
            logger.info(f"step_config的type:{type(step_config)},step_config的值：{step_config}")
            step_result = self.execute_test_step(step_config)
            all_step_results.append(step_result)

            if not step_result.passed and self.assertion_handler.terminate_on_failure:
                logger.error(f"LiuShuiXian: 用例 '{case_name}' 因步骤 '{step_result.step_name}' 失败而提前终止。")
                case_passed = False
                break  # 如果断言失败且配置为终止，则停止后续步骤执行
            elif not step_result.passed and not self.assertion_handler.terminate_on_failure:
                case_passed = False  # 即使继续执行，用例整体也算失败

        logger.info(f"======== LiuShuiXian: 用例 '{case_name}' 执行 {'成功' if case_passed else '失败'} ========\n")
        return all_step_results, case_passed


# 调试代码
# if __name__ == '__main__':
#     method = 'POST'
#     url = 'http://127.0.0.1:5001/api/directory/getDirectory'
#     headers = {
#         "Content-Type": "application/json"
#     }
#     body_processed = {
#         "projectId": 2,
#         "dtype": "interface"
#     }
#     params = {}
#     response = LiuShuiXian._send_http_request(method, url, headers, body_processed, params)
#     logger.info(f"请求返回结果为：{response.text}")


