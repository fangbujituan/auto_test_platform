"""
@Author: <yandc>
@Time: 2025/06/07
断言处理
"""
from app.utils.logger_config import logger


class AssertionResult:
    """
    表示单个断言的结果。
    """

    def __init__(self, passed: bool, message: str, details: dict = None):
        self.passed = passed
        self.message = message
        self.details = details if details is not None else {}

    def to_dict(self):
        return {
            'passed': self.passed,
            'message': self.message,
            'details': self.details
        }


class AssertionHandler:
    """
    处理测试用例中的断言。
    支持多种断言类型，并根据配置处理断言失败的策略（继续或终止）。
    """

    def __init__(self, terminate_on_failure: bool = True):
        """
        :param terminate_on_failure: 如果为True，则断言失败时抛出异常终止执行；否则继续。
        """
        self.terminate_on_failure = terminate_on_failure
        logger.info(f"========断言准备就绪========")
        # logger.info(f"AssertionHandler: 初始化，断言失败时 {'终止' if terminate_on_failure else '继续'} 执行。")

    def assert_status_code(self, actual_status_code: int, expected_status_code: int) -> AssertionResult:
        """
        断言 HTTP 响应状态码。
        """
        passed = (actual_status_code == expected_status_code)
        message = f"断言状态码：期望 {expected_status_code}, 实际 {actual_status_code}."
        if passed:
            logger.info(f"AssertionHandler: 状态码断言成功: {message}")
        else:
            logger.error(f"AssertionHandler: 状态码断言失败: {message}")
            if self.terminate_on_failure:
                raise AssertionError(message)
        return AssertionResult(passed, message, {'actual': actual_status_code, 'expected': expected_status_code})

    def assert_json_contains(self, actual_json: dict, expected_key: str, expected_value: any) -> AssertionResult:
        """
        断言 JSON 响应中是否包含指定的键值对。
        """
        passed = False
        message = f"断言 JSON 响应中键 '{expected_key}' 的值：期望 '{expected_value}'."
        actual_value = actual_json.get(expected_key)

        if actual_value is not None:
            if actual_value == expected_value:
                passed = True
                message += f" 实际 '{actual_value}'。断言成功。"
                logger.info(f"AssertionHandler: JSON 内容断言成功: {message}")
            else:
                message += f" 实际 '{actual_value}'。断言失败。"
                logger.error(f"AssertionHandler: JSON 内容断言失败: {message}")
        else:
            message += f" 键 '{expected_key}' 不存在。断言失败。"
            logger.error(f"AssertionHandler: JSON 内容断言失败: {message}")

        if not passed and self.terminate_on_failure:
            raise AssertionError(message)
        return AssertionResult(passed, message, {'actual_json': actual_json, 'expected_key': expected_key,
                                                 'expected_value': expected_value})

    def assert_response_text_contains(self, actual_text: str, expected_substring: str) -> AssertionResult:
        """
        断言响应文本是否包含指定子字符串。
        """
        passed = (expected_substring in actual_text)
        message = f"断言响应文本包含 '{expected_substring}'."
        if passed:
            message += " 断言成功。"
            logger.info(f"AssertionHandler: 文本内容断言成功: {message}")
        else:
            message += " 未包含。断言失败。"
            logger.error(f"AssertionHandler: 文本内容断言失败: {message}")

        if not passed and self.terminate_on_failure:
            raise AssertionError(message)
        return AssertionResult(passed, message, {'actual_text': actual_text, 'expected_substring': expected_substring})

    # 可以根据需要添加更多断言方法，例如：
    # assert_header(self, actual_headers: dict, expected_header_key: str, expected_header_value: str)
    # assert_less_than(self, actual_value, expected_max_value)
    # ...


if __name__ == '__main__':
    # 示例用法：断言失败时终止
    handler_terminate = AssertionHandler(terminate_on_failure=True)

    logger.info("\n--- 示例1: 断言失败时终止 ---")
    try:
        handler_terminate.assert_status_code(200, 201)  # 预期失败
    except AssertionError as e:
        logger.info(f"捕获到异常 (预期): {e}")

    try:
        handler_terminate.assert_json_contains({'message': 'success', 'code': 0}, 'code', 1)  # 预期失败
    except AssertionError as e:
        logger.info(f"捕获到异常 (预期): {e}")

    handler_terminate.assert_status_code(200, 200)  # 预期成功

    # 示例用法：断言失败时继续
    handler_continue = AssertionHandler(terminate_on_failure=False)
    logger.info("\n--- 示例2: 断言失败时继续 ---")
    result1 = handler_continue.assert_status_code(200, 201)  # 预期失败
    logger.info(f"结果1: {result1.to_dict()}")

    result2 = handler_continue.assert_json_contains({'message': 'success', 'code': 0}, 'code', 1)  # 预期失败
    logger.info(f"结果2: {result2.to_dict()}")

    result3 = handler_continue.assert_response_text_contains("hello world", "goodbye")  # 预期失败
    logger.info(f"结果3: {result3.to_dict()}")

    result4 = handler_continue.assert_status_code(200, 200)  # 预期成功
    logger.info(f"结果4: {result4.to_dict()}")
