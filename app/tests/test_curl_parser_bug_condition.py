"""
Bug 条件探索性测试 — 后端 parse_curl

模拟用户从浏览器 DevTools 粘贴 CMD/bash 格式 cURL 的真实场景。
在未修复的代码上运行时，CMD 格式测试应当失败，从而证明 bug 存在。

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.routes.api_import import parse_curl


class TestParseCurlBugConditionCMD:
    """CMD 格式 cURL 双引号转义 JSON Body 解析 bug 条件测试"""

    def test_cmd_data_raw_escaped_json(self):
        """CMD 格式 --data-raw 应正确解析 JSON body"""
        curl = (
            'curl ^"https://example.com/api^" '
            '^-H ^"content-type: application/json;charset=UTF-8^" '
            '^--data-raw ^"^{^\\^"ClientID^\\^":1005,'
            '^\\^"PageIndex^\\^":1^}^"'
        )
        result = parse_curl(curl)
        assert result['body'] == {"ClientID": 1005, "PageIndex": 1}
        assert result['body_type'] == 'json'

    def test_cmd_data_raw_empty_string_values(self):
        """CMD 格式 --data-raw 包含空字符串值应正确解析"""
        curl = (
            'curl ^"https://example.com/api^" '
            '^-H ^"content-type: application/json;charset=UTF-8^" '
            '^--data-raw ^"^{^\\^"sortfield^\\^":^\\^"^\\^",'
            '^\\^"sorttype^\\^":^\\^"^\\^"^}^"'
        )
        result = parse_curl(curl)
        assert result['body'] == {"sortfield": "", "sorttype": ""}
        assert result['body_type'] == 'json'

    def test_cmd_full_curl_user_reported(self):
        """CMD 格式完整 cURL（用户实际报告的命令）应正确解析"""
        curl = (
            'curl ^"https://bnp-test.example.com/api/Test^" '
            '^-H ^"content-type: application/json;charset=UTF-8^" '
            '^--data-raw ^"^{^\\^"ClientID^\\^":1005,'
            '^\\^"PageSize^\\^":20,'
            '^\\^"sortfield^\\^":^\\^"^\\^",'
            '^\\^"PaymentStatus^\\^":^\\^"2^\\^"^}^"'
        )
        result = parse_curl(curl)
        assert result['body'] == {
            "ClientID": 1005,
            "PageSize": 20,
            "sortfield": "",
            "PaymentStatus": "2"
        }
        assert result['body_type'] == 'json'
        assert result['method'] == 'POST'


class TestParseCurlBugConditionBash:
    """bash 双引号格式 cURL 转义 JSON Body 解析 bug 条件测试"""

    def test_bash_data_raw_escaped_json(self):
        """bash 双引号 --data-raw 转义 JSON 应正确解析"""
        curl = (
            'curl -X POST "https://example.com/api" '
            '--data-raw "{\\"ClientID\\":1005,\\"PageIndex\\":1}"'
        )
        result = parse_curl(curl)
        assert result['body'] == {"ClientID": 1005, "PageIndex": 1}
        assert result['body_type'] == 'json'

    def test_bash_data_raw_empty_string_values(self):
        """bash 双引号 --data-raw 包含空字符串值应正确解析"""
        curl = (
            'curl -X POST "https://example.com/api" '
            '--data-raw "{\\"sortfield\\":\\"\\",\\"sorttype\\":\\"\\"}"'
        )
        result = parse_curl(curl)
        assert result['body'] == {"sortfield": "", "sorttype": ""}
        assert result['body_type'] == 'json'

    def test_d_flag_escaped_json(self):
        """-d 标志的双引号转义 JSON 应与 --data-raw 行为一致"""
        curl = (
            'curl -X POST "https://example.com/api" '
            '-d "{\\"name\\":\\"test\\"}"'
        )
        result = parse_curl(curl)
        assert result['body'] == {"name": "test"}
        assert result['body_type'] == 'json'
