"""
Bug 条件探索性测试 — 后端 parse_curl

这些测试断言期望的正确行为。
在未修复的代码上运行时，它们应当失败，从而证明 bug 存在。

Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.routes.api_import import parse_curl


class TestParseCurlBugCondition:
    """双引号包裹的转义 JSON Body 解析 bug 条件测试"""

    def test_data_raw_escaped_json_parses_correctly(self):
        """--data-raw 双引号包裹 + 转义引号的 JSON 应正确解析为 JSON 对象"""
        curl = 'curl -X POST "https://example.com/api" --data-raw "{\\"ClientID\\":1005,\\"PageIndex\\":1}"'
        result = parse_curl(curl)

        assert result['body'] == {"ClientID": 1005, "PageIndex": 1}
        assert result['body_type'] == 'json'

    def test_data_raw_empty_string_values_parse_correctly(self):
        """--data-raw 包含空字符串值的转义 JSON 应正确解析"""
        curl = 'curl -X POST "https://example.com/api" --data-raw "{\\"sortfield\\":\\"\\",\\"sorttype\\":\\"\\"}"'
        result = parse_curl(curl)

        assert result['body'] == {"sortfield": "", "sorttype": ""}
        assert result['body_type'] == 'json'

    def test_d_flag_escaped_json_same_as_data_raw(self):
        """-d 标志的双引号转义 JSON 应与 --data-raw 行为一致"""
        curl = 'curl -X POST "https://example.com/api" -d "{\\"name\\":\\"test\\"}"'
        result = parse_curl(curl)

        assert result['body'] == {"name": "test"}
        assert result['body_type'] == 'json'
