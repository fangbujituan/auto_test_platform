"""
Preservation 属性测试 — 后端 parse_curl

验证非 bug 条件输入（不涉及"双引号包裹 + 内部含 \\" 转义引号"）的行为保持不变。
这些测试在未修复的代码上应当全部通过，确认基线行为。

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.routes.api_import import parse_curl


class TestPreservationSingleQuoteJSON:
    """Preservation: 单引号包裹 JSON body 正确解析 (Req 3.1)"""

    def test_single_quote_json_body(self):
        """--data-raw '{}' 单引号 JSON 应解析为 json 类型"""
        curl = "curl -X POST 'https://example.com/api' --data-raw '{\"key\":\"value\"}'"
        result = parse_curl(curl)

        assert result['body'] == {"key": "value"}
        assert result['body_type'] == 'json'


class TestPreservationFormUrlencoded:
    """Preservation: form-urlencoded 正确解析 (Req 3.2)"""

    def test_form_urlencoded(self):
        """-d "key1=value1&key2=value2" 应解析为 form 类型"""
        curl = 'curl -X POST https://example.com/api -d "key1=value1&key2=value2"'
        result = parse_curl(curl)

        assert result['body_type'] == 'form'
        assert result['body'] == {"key1": "value1", "key2": "value2"}


class TestPreservationMultipartForm:
    """Preservation: -F/--form multipart 正确解析 (Req 3.3)"""

    def test_form_multipart(self):
        """-F "file=@test.txt" 应解析为 form 类型"""
        curl = 'curl -X POST https://example.com/api -F "file=@test.txt"'
        result = parse_curl(curl)

        assert result['body_type'] == 'form'
        assert result['body'] == {"file": "@test.txt"}


class TestPreservationPureGET:
    """Preservation: 纯 GET 请求 body 为空 (Req 3.4)"""

    def test_pure_get_request(self):
        """无 body 的 GET 请求应返回空对象和 GET 方法"""
        curl = 'curl https://example.com/api'
        result = parse_curl(curl)

        assert result['body'] == {}
        assert result['method'] == 'GET'


class TestPreservationSimpleUnquotedData:
    """Preservation: 不带引号的简单数据回退匹配 (Req 3.5)"""

    def test_unquoted_simple_data(self):
        """--data-raw 不带引号的简单字符串应通过回退匹配提取"""
        curl = 'curl -X POST https://example.com/api --data-raw simpledata'
        result = parse_curl(curl)

        assert result['method'] == 'POST'
        assert result['body'] == {"raw": "simpledata"}
        assert result['body_type'] == 'raw'
