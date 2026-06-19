"""
HTTP请求执行引擎。

作者: yandc
创建时间: 2026-01-16
"""
import time
import json
import requests
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse


class RequestFactory:
    """HTTP请求执行工厂类。"""
    
    def __init__(self, timeout: int = 30):
        """
        初始化请求工厂。
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()
        # ATP 是接口测试工具，必须直连目标，不能被系统/环境代理劫持。
        # 否则用户的内网或本地接口会被代理转发并返回 502。
        # 如果未来需要支持"通过代理发请求"，应该在每次 execute() 调用时
        # 通过显式参数传入 proxies，而不是借用系统设置。
        self.session.trust_env = False
    
    def execute(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        body_type: str = "json"
    ) -> Dict[str, Any]:
        """
        执行HTTP请求。
        
        Args:
            method: HTTP方法（GET, POST, PUT, DELETE, PATCH）
            url: 请求URL
            headers: 请求头
            params: 查询参数
            body: 请求体
            body_type: 请求体类型（json, form, raw）
        
        Returns:
            包含请求和响应信息的字典
        """
        start_time = time.time()
        result = {
            "success": False,
            "request": {
                "method": method.upper(),
                "url": url,
                "headers": headers or {},
                "params": params or {},
                "body": body or {},
                "body_type": body_type
            },
            "response": None,
            "error": None,
            "duration": 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            # 验证URL
            if not url:
                raise ValueError("URL不能为空")
            
            # 如果URL不是完整的，添加协议
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            
            # 准备请求参数
            request_kwargs = {
                "timeout": self.timeout,
                "headers": headers or {},
                "params": params or {}
            }
            
            # 处理请求体
            if body and method.upper() in ['POST', 'PUT', 'PATCH']:
                if body_type == "json":
                    request_kwargs["json"] = body
                elif body_type == "form":
                    request_kwargs["data"] = body
                elif body_type == "raw":
                    request_kwargs["data"] = json.dumps(body) if isinstance(body, dict) else body
            
            # 发送请求
            response = self.session.request(
                method=method.upper(),
                url=url,
                **request_kwargs
            )
            
            # 计算耗时
            duration = time.time() - start_time
            
            # 解析响应
            response_data = self._parse_response(response)
            
            result.update({
                "success": True,
                "response": response_data,
                "duration": round(duration, 3)
            })
            
        except requests.exceptions.Timeout:
            result["error"] = {
                "type": "TimeoutError",
                "message": f"请求超时（{self.timeout}秒）"
            }
            result["duration"] = round(time.time() - start_time, 3)
            
        except requests.exceptions.ConnectionError as e:
            result["error"] = {
                "type": "ConnectionError",
                "message": f"连接失败: {str(e)}"
            }
            result["duration"] = round(time.time() - start_time, 3)
            
        except requests.exceptions.RequestException as e:
            result["error"] = {
                "type": "RequestException",
                "message": f"请求异常: {str(e)}"
            }
            result["duration"] = round(time.time() - start_time, 3)
            
        except Exception as e:
            result["error"] = {
                "type": "UnknownError",
                "message": f"未知错误: {str(e)}"
            }
            result["duration"] = round(time.time() - start_time, 3)
        
        return result
    
    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        解析响应对象。
        
        Args:
            response: requests响应对象
        
        Returns:
            响应信息字典
        """
        # 获取响应头
        headers = dict(response.headers)
        
        # 尝试解析JSON响应
        try:
            body = response.json()
        except ValueError:
            # 如果不是JSON，返回文本
            body = response.text
        
        # 保留原始响应文本（用于前端保持字段顺序显示）
        body_raw = None
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type or isinstance(body, (dict, list)):
            try:
                body_raw = response.text
            except Exception:
                pass
        
        return {
            "status_code": response.status_code,
            "status_text": response.reason,
            "headers": headers,
            "body": body,
            "body_raw": body_raw,
            "size": len(response.content),
            "encoding": response.encoding
        }
    
    def validate_response(
        self,
        response: Dict[str, Any],
        expected_status: Optional[int] = None,
        expected_body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        验证响应是否符合预期。
        
        Args:
            response: 响应数据
            expected_status: 期望的状态码
            expected_body: 期望的响应体
        
        Returns:
            验证结果
        """
        validation_result = {
            "passed": True,
            "failures": []
        }
        
        if not response or "response" not in response:
            validation_result["passed"] = False
            validation_result["failures"].append("响应数据为空")
            return validation_result
        
        resp = response["response"]
        
        # 验证状态码
        if expected_status is not None:
            if resp["status_code"] != expected_status:
                validation_result["passed"] = False
                validation_result["failures"].append(
                    f"状态码不匹配: 期望 {expected_status}, 实际 {resp['status_code']}"
                )
        
        # 验证响应体
        if expected_body is not None:
            actual_body = resp["body"]
            if isinstance(actual_body, dict) and isinstance(expected_body, dict):
                for key, expected_value in expected_body.items():
                    if key not in actual_body:
                        validation_result["passed"] = False
                        validation_result["failures"].append(f"响应体缺少字段: {key}")
                    elif actual_body[key] != expected_value:
                        validation_result["passed"] = False
                        validation_result["failures"].append(
                            f"字段 {key} 值不匹配: 期望 {expected_value}, 实际 {actual_body[key]}"
                        )
        
        return validation_result
    
    def close(self):
        """关闭会话。"""
        self.session.close()


# 全局请求工厂实例
_request_factory = None


def get_request_factory() -> RequestFactory:
    """获取全局请求工厂实例。"""
    global _request_factory
    if _request_factory is None:
        _request_factory = RequestFactory()
    return _request_factory
