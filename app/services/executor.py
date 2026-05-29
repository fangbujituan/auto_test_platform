"""
测试用例执行器服务。

作者: yandc
创建时间: 2026-01-13
"""
import time
import requests
from app.models.base import db
from app.models.result import TestResult


class TestExecutor:
    """执行测试用例并记录结果。"""

    def __init__(self, timeout=30):
        """使用超时设置初始化执行器。"""
        self.timeout = timeout

    def run_case(self, case):
        """执行单个测试用例并返回结果。"""
        start_time = time.time()
        result = TestResult(case_id=case.id)
        
        try:
            response = self._send_request(case)
            duration = time.time() - start_time
            
            result.actual_status = response.status_code
            result.actual_response = self._parse_response(response)
            result.duration = duration
            
            # 验证结果
            if self._validate(case, response):
                result.status = "passed"
            else:
                result.status = "failed"
                result.error_message = self._get_validation_error(case, response)
                
        except requests.RequestException as e:
            result.status = "error"
            result.error_message = str(e)
            result.duration = time.time() - start_time
        
        db.session.add(result)
        db.session.commit()
        return result

    def run_cases(self, cases):
        """执行多个测试用例。"""
        return [self.run_case(case) for case in cases]

    def _send_request(self, case):
        """根据用例配置发送HTTP请求。"""
        return requests.request(
            method=case.method,
            url=case.url,
            headers=case.headers or {},
            params=case.params or {},
            json=case.body,
            timeout=self.timeout,
        )

    def _parse_response(self, response):
        """解析响应体。"""
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

    def _validate(self, case, response):
        """根据预期值验证响应。"""
        if case.expected_status and response.status_code != case.expected_status:
            return False
        
        if case.expected_response:
            actual = self._parse_response(response)
            return self._match_response(case.expected_response, actual)
        
        return True

    def _match_response(self, expected, actual):
        """检查实际响应是否匹配预期（部分匹配）。"""
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            for key, value in expected.items():
                if key not in actual:
                    return False
                if not self._match_response(value, actual[key]):
                    return False
            return True
        return expected == actual

    def _get_validation_error(self, case, response):
        """生成验证错误消息。"""
        errors = []
        if case.expected_status and response.status_code != case.expected_status:
            errors.append(
                f"状态码不匹配: 预期 {case.expected_status}, "
                f"实际 {response.status_code}"
            )
        if case.expected_response:
            actual = self._parse_response(response)
            if not self._match_response(case.expected_response, actual):
                errors.append("响应体不匹配")
        return "; ".join(errors)
