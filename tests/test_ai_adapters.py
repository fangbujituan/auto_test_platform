"""
AI 提供商适配器单元测试。

使用 unittest.mock 模拟 HTTP 请求，验证适配器的响应转换和错误处理逻辑。
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_adapters import (
    OpenAIAdapter,
    DashScopeAdapter,
    OllamaAdapter,
    get_adapter,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def openai_adapter():
    return OpenAIAdapter(api_key="sk-test", base_url="https://api.openai.com", model_name="gpt-4o")


@pytest.fixture
def dashscope_adapter():
    return DashScopeAdapter(api_key="sk-dash", base_url="https://dashscope.aliyuncs.com/compatible-mode",
                            model_name="qwen-plus")


@pytest.fixture
def ollama_adapter():
    return OllamaAdapter(api_key="", base_url="http://localhost:11434", model_name="llama3")


# ------------------------------------------------------------------
# Factory tests
# ------------------------------------------------------------------

class TestGetAdapter:
    def test_returns_openai_adapter(self):
        adapter = get_adapter("openai", "key", "http://url", "model")
        assert isinstance(adapter, OpenAIAdapter)

    def test_returns_dashscope_adapter(self):
        adapter = get_adapter("dashscope", "key", "http://url", "model")
        assert isinstance(adapter, DashScopeAdapter)

    def test_returns_ollama_adapter(self):
        adapter = get_adapter("ollama", "", "http://url", "model")
        assert isinstance(adapter, OllamaAdapter)

    def test_raises_for_unknown_type(self):
        with pytest.raises(ValueError, match="不支持的提供商类型"):
            get_adapter("unknown", "", "http://url", "model")

    def test_base_url_trailing_slash_stripped(self):
        adapter = get_adapter("openai", "key", "http://url/", "model")
        assert adapter.base_url == "http://url"


# ------------------------------------------------------------------
# OpenAI adapter tests
# ------------------------------------------------------------------

class TestOpenAIAdapter:
    @patch("app.services.ai_adapters.requests.post")
    def test_chat_success(self, mock_post, openai_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_post.return_value = mock_resp

        result = openai_adapter.chat([{"role": "user", "content": "Hi"}])

        assert "content" in result
        assert "usage" in result
        assert result["content"] == "Hello!"
        assert isinstance(result["usage"], dict)

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_api_error(self, mock_post, openai_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"code": "invalid_api_key", "message": "Invalid key"}}
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        result = openai_adapter.chat([{"role": "user", "content": "Hi"}])

        assert "error_code" in result
        assert "error_message" in result
        assert result["error_code"] == "invalid_api_key"

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_timeout(self, mock_post, openai_adapter):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()

        result = openai_adapter.chat([{"role": "user", "content": "Hi"}])

        assert result["error_code"] == "TIMEOUT"

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_connection_error(self, mock_post, openai_adapter):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError()

        result = openai_adapter.chat([{"role": "user", "content": "Hi"}])

        assert result["error_code"] == "CONNECTION_ERROR"

    @patch("app.services.ai_adapters.requests.post")
    def test_test_connection_success(self, mock_post, openai_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Hi"}}]}
        mock_post.return_value = mock_resp

        result = openai_adapter.test_connection()

        assert result["success"] is True
        assert "latency_ms" in result

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_stream_yields_content(self, mock_post, openai_adapter):
        lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b'data: [DONE]',
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter([l.decode() for l in lines])
        mock_post.return_value = mock_resp

        chunks = list(openai_adapter.chat_stream([{"role": "user", "content": "Hi"}]))

        assert "Hello" in chunks
        assert " world" in chunks


# ------------------------------------------------------------------
# DashScope adapter tests
# ------------------------------------------------------------------

class TestDashScopeAdapter:
    @patch("app.services.ai_adapters.requests.post")
    def test_chat_success(self, mock_post, dashscope_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "你好！"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_post.return_value = mock_resp

        result = dashscope_adapter.chat([{"role": "user", "content": "你好"}])

        assert result["content"] == "你好！"
        assert isinstance(result["usage"], dict)

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_error(self, mock_post, dashscope_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": {"code": "invalid_request", "message": "Bad request"}}
        mock_resp.text = "Bad request"
        mock_post.return_value = mock_resp

        result = dashscope_adapter.chat([{"role": "user", "content": "Hi"}])

        assert "error_code" in result
        assert "error_message" in result


# ------------------------------------------------------------------
# Ollama adapter tests
# ------------------------------------------------------------------

class TestOllamaAdapter:
    @patch("app.services.ai_adapters.requests.post")
    def test_chat_success(self, mock_post, ollama_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Hello from Ollama!"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        mock_post.return_value = mock_resp

        result = ollama_adapter.chat([{"role": "user", "content": "Hi"}])

        assert result["content"] == "Hello from Ollama!"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5
        assert result["usage"]["total_tokens"] == 15

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_error(self, mock_post, ollama_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"error": "model not found"}
        mock_resp.text = "model not found"
        mock_post.return_value = mock_resp

        result = ollama_adapter.chat([{"role": "user", "content": "Hi"}])

        assert "error_code" in result
        assert "error_message" in result

    @patch("app.services.ai_adapters.requests.post")
    def test_chat_stream_yields_content(self, mock_post, ollama_adapter):
        lines = [
            '{"message":{"content":"Hello"}}',
            '{"message":{"content":" there"}}',
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_post.return_value = mock_resp

        chunks = list(ollama_adapter.chat_stream([{"role": "user", "content": "Hi"}]))

        assert "Hello" in chunks
        assert " there" in chunks

    @patch("app.services.ai_adapters.requests.post")
    def test_test_connection_success(self, mock_post, ollama_adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "Hi"}}
        mock_post.return_value = mock_resp

        result = ollama_adapter.test_connection()

        assert result["success"] is True
        assert "latency_ms" in result


# ------------------------------------------------------------------
# Standard response format validation
# ------------------------------------------------------------------

class TestResponseFormat:
    """Verify all adapters produce the standard response format."""

    @patch("app.services.ai_adapters.requests.post")
    def test_all_adapters_return_content_and_usage(self, mock_post):
        """Each adapter's successful response must contain 'content' (str) and 'usage' (dict)."""
        openai_raw = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        dashscope_raw = {
            "choices": [{"message": {"content": "好的"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        ollama_raw = {
            "message": {"content": "ok"},
            "prompt_eval_count": 1,
            "eval_count": 1,
        }

        configs = [
            ("openai", openai_raw),
            ("dashscope", dashscope_raw),
            ("ollama", ollama_raw),
        ]

        for ptype, raw in configs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = raw
            mock_post.return_value = mock_resp

            adapter = get_adapter(ptype, "key", "http://localhost", "model")
            result = adapter.chat([{"role": "user", "content": "test"}])

            assert isinstance(result.get("content"), str), f"{ptype}: content should be str"
            assert isinstance(result.get("usage"), dict), f"{ptype}: usage should be dict"

    @patch("app.services.ai_adapters.requests.post")
    def test_all_adapters_error_format(self, mock_post):
        """Each adapter's error response must contain 'error_code' and 'error_message'."""
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()

        for ptype in ("openai", "dashscope", "ollama"):
            adapter = get_adapter(ptype, "key", "http://localhost", "model")
            result = adapter.chat([{"role": "user", "content": "test"}])

            assert isinstance(result.get("error_code"), str), f"{ptype}: error_code should be str"
            assert isinstance(result.get("error_message"), str), f"{ptype}: error_message should be str"
            assert len(result["error_code"]) > 0
            assert len(result["error_message"]) > 0
