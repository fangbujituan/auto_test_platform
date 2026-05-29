"""
AI 提供商适配器模块。

提供统一的适配器接口，封装不同 AI 提供商（OpenAI、DashScope、Ollama）的调用差异。

作者: yandc
创建时间: 2026-02-10
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Generator

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60


class ProviderAdapter(ABC):
    """AI 提供商适配器抽象基类。"""

    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    @abstractmethod
    def chat(self, messages: list, temperature: float = 0.7,
             max_tokens: int = 2048) -> dict:
        """同步对话，返回 {"content": str, "usage": dict}。"""

    @abstractmethod
    def chat_stream(self, messages: list, temperature: float = 0.7,
                    max_tokens: int = 2048) -> Generator[str, None, None]:
        """流式对话，yield 每个 token 片段。"""

    @abstractmethod
    def test_connection(self) -> dict:
        """测试连接，返回 {"success": bool, "message": str, "latency_ms": int}。"""

    @staticmethod
    def _make_error(error_code: str, error_message: str) -> dict:
        """构造标准错误响应。"""
        return {"error_code": error_code, "error_message": error_message}


class OpenAIAdapter(ProviderAdapter):
    """OpenAI 兼容接口适配器，调用 /v1/chat/completions。"""

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, messages: list, temperature: float = 0.7,
             max_tokens: int = 2048) -> dict:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._build_headers(),
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return self._parse_error_response(resp)
            data = resp.json()
            return self._normalize_response(data)
        except requests.exceptions.Timeout:
            return self._make_error("TIMEOUT", "AI 服务调用超时")
        except requests.exceptions.ConnectionError:
            return self._make_error("CONNECTION_ERROR", "无法连接到 AI 服务")
        except Exception as e:
            return self._make_error("UNKNOWN_ERROR", str(e))

    def chat_stream(self, messages: list, temperature: float = 0.7,
                    max_tokens: int = 2048) -> Generator[str, None, None]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._build_headers(),
                                 timeout=REQUEST_TIMEOUT, stream=True)
            if resp.status_code != 200:
                yield json.dumps(self._parse_error_response(resp))
                return
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except requests.exceptions.Timeout:
            yield json.dumps(self._make_error("TIMEOUT", "AI 服务调用超时"))
        except requests.exceptions.ConnectionError:
            yield json.dumps(self._make_error("CONNECTION_ERROR", "无法连接到 AI 服务"))
        except Exception as e:
            yield json.dumps(self._make_error("UNKNOWN_ERROR", str(e)))

    def test_connection(self) -> dict:
        import time
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        start = time.time()
        try:
            resp = requests.post(url, json=payload, headers=self._build_headers(),
                                 timeout=REQUEST_TIMEOUT)
            latency = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"success": True, "message": "连接成功", "latency_ms": latency}
            return {"success": False, "message": f"服务返回错误: {resp.status_code} {resp.text[:200]}",
                    "latency_ms": latency}
        except requests.exceptions.Timeout:
            return {"success": False, "message": "连接超时", "latency_ms": int((time.time() - start) * 1000)}
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "无法连接到服务", "latency_ms": int((time.time() - start) * 1000)}
        except Exception as e:
            return {"success": False, "message": str(e), "latency_ms": int((time.time() - start) * 1000)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_response(data: dict) -> dict:
        """将 OpenAI 原始响应转换为标准格式。"""
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return {"content": content, "usage": usage}

    def _parse_error_response(self, resp: requests.Response) -> dict:
        """解析 OpenAI 错误响应为标准错误格式。"""
        try:
            body = resp.json()
            err = body.get("error", {})
            code = err.get("code") or err.get("type") or str(resp.status_code)
            message = err.get("message") or resp.text[:200]
        except Exception:
            code = str(resp.status_code)
            message = resp.text[:200]
        return self._make_error(str(code), message)


class DashScopeAdapter(ProviderAdapter):
    """通义千问 DashScope 适配器（OpenAI 兼容格式）。"""

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, messages: list, temperature: float = 0.7,
             max_tokens: int = 2048) -> dict:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._build_headers(),
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return self._parse_error_response(resp)
            data = resp.json()
            return self._normalize_response(data)
        except requests.exceptions.Timeout:
            return self._make_error("TIMEOUT", "AI 服务调用超时")
        except requests.exceptions.ConnectionError:
            return self._make_error("CONNECTION_ERROR", "无法连接到 AI 服务")
        except Exception as e:
            return self._make_error("UNKNOWN_ERROR", str(e))

    def chat_stream(self, messages: list, temperature: float = 0.7,
                    max_tokens: int = 2048) -> Generator[str, None, None]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._build_headers(),
                                 timeout=REQUEST_TIMEOUT, stream=True)
            if resp.status_code != 200:
                yield json.dumps(self._parse_error_response(resp))
                return
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except requests.exceptions.Timeout:
            yield json.dumps(self._make_error("TIMEOUT", "AI 服务调用超时"))
        except requests.exceptions.ConnectionError:
            yield json.dumps(self._make_error("CONNECTION_ERROR", "无法连接到 AI 服务"))
        except Exception as e:
            yield json.dumps(self._make_error("UNKNOWN_ERROR", str(e)))

    def test_connection(self) -> dict:
        import time
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        start = time.time()
        try:
            resp = requests.post(url, json=payload, headers=self._build_headers(),
                                 timeout=REQUEST_TIMEOUT)
            latency = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"success": True, "message": "连接成功", "latency_ms": latency}
            return {"success": False, "message": f"服务返回错误: {resp.status_code} {resp.text[:200]}",
                    "latency_ms": latency}
        except requests.exceptions.Timeout:
            return {"success": False, "message": "连接超时", "latency_ms": int((time.time() - start) * 1000)}
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "无法连接到服务", "latency_ms": int((time.time() - start) * 1000)}
        except Exception as e:
            return {"success": False, "message": str(e), "latency_ms": int((time.time() - start) * 1000)}

    @staticmethod
    def _normalize_response(data: dict) -> dict:
        """将 DashScope 响应转换为标准格式。"""
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return {"content": content, "usage": usage}

    def _parse_error_response(self, resp: requests.Response) -> dict:
        try:
            body = resp.json()
            err = body.get("error", {})
            code = err.get("code") or err.get("type") or str(resp.status_code)
            message = err.get("message") or resp.text[:200]
        except Exception:
            code = str(resp.status_code)
            message = resp.text[:200]
        return self._make_error(str(code), message)


class OllamaAdapter(ProviderAdapter):
    """Ollama 本地模型适配器，调用 /api/chat。"""

    def chat(self, messages: list, temperature: float = 0.7,
             max_tokens: int = 2048) -> dict:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return self._parse_error_response(resp)
            data = resp.json()
            return self._normalize_response(data)
        except requests.exceptions.Timeout:
            return self._make_error("TIMEOUT", "AI 服务调用超时")
        except requests.exceptions.ConnectionError:
            return self._make_error("CONNECTION_ERROR", "无法连接到 AI 服务")
        except Exception as e:
            return self._make_error("UNKNOWN_ERROR", str(e))

    def chat_stream(self, messages: list, temperature: float = 0.7,
                    max_tokens: int = 2048) -> Generator[str, None, None]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT, stream=True)
            if resp.status_code != 200:
                yield json.dumps(self._parse_error_response(resp))
                return
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except requests.exceptions.Timeout:
            yield json.dumps(self._make_error("TIMEOUT", "AI 服务调用超时"))
        except requests.exceptions.ConnectionError:
            yield json.dumps(self._make_error("CONNECTION_ERROR", "无法连接到 AI 服务"))
        except Exception as e:
            yield json.dumps(self._make_error("UNKNOWN_ERROR", str(e)))

    def test_connection(self) -> dict:
        import time
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
            "options": {"num_predict": 5},
        }
        start = time.time()
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            latency = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"success": True, "message": "连接成功", "latency_ms": latency}
            return {"success": False, "message": f"服务返回错误: {resp.status_code} {resp.text[:200]}",
                    "latency_ms": latency}
        except requests.exceptions.Timeout:
            return {"success": False, "message": "连接超时", "latency_ms": int((time.time() - start) * 1000)}
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "无法连接到服务", "latency_ms": int((time.time() - start) * 1000)}
        except Exception as e:
            return {"success": False, "message": str(e), "latency_ms": int((time.time() - start) * 1000)}

    @staticmethod
    def _normalize_response(data: dict) -> dict:
        """将 Ollama 响应转换为标准格式。"""
        content = data.get("message", {}).get("content", "")
        # Ollama 返回的 token 统计在顶层
        usage = {}
        if "prompt_eval_count" in data:
            usage["prompt_tokens"] = data["prompt_eval_count"]
        if "eval_count" in data:
            usage["completion_tokens"] = data["eval_count"]
        if usage:
            usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        return {"content": content, "usage": usage}

    def _parse_error_response(self, resp: requests.Response) -> dict:
        try:
            body = resp.json()
            message = body.get("error", resp.text[:200])
        except Exception:
            message = resp.text[:200]
        return self._make_error(str(resp.status_code), str(message))


# ------------------------------------------------------------------
# 适配器工厂
# ------------------------------------------------------------------

_ADAPTER_MAP = {
    "openai": OpenAIAdapter,
    "dashscope": DashScopeAdapter,
    "ollama": OllamaAdapter,
}


def get_adapter(provider_type: str, api_key: str, base_url: str,
                model_name: str) -> ProviderAdapter:
    """
    根据提供商类型返回对应的适配器实例。

    Args:
        provider_type: 提供商类型 (openai / dashscope / ollama)
        api_key: API Key（明文，调用前在内存中解密）
        base_url: API 基础地址
        model_name: 模型名称

    Returns:
        ProviderAdapter 实例

    Raises:
        ValueError: 不支持的提供商类型
    """
    adapter_cls = _ADAPTER_MAP.get(provider_type)
    if adapter_cls is None:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
    return adapter_cls(api_key=api_key, base_url=base_url, model_name=model_name)
