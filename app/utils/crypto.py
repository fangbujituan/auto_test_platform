"""
加解密工具模块。

使用 Fernet 对称加密保护 API Key 等敏感信息。
加密密钥从环境变量 AI_ENCRYPTION_KEY 读取。
"""
import os

from cryptography.fernet import Fernet


class CryptoUtil:
    """API Key 加解密工具，使用 Fernet 对称加密。"""

    @staticmethod
    def _get_fernet() -> Fernet:
        """获取 Fernet 实例，密钥从环境变量读取。"""
        key = os.environ.get("AI_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("环境变量 AI_ENCRYPTION_KEY 未配置")
        return Fernet(key.encode() if isinstance(key, str) else key)

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """加密明文，返回 base64 编码的密文字符串。"""
        f = CryptoUtil._get_fernet()
        token = f.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    @staticmethod
    def decrypt(ciphertext: str) -> str:
        """解密密文，返回明文字符串。"""
        f = CryptoUtil._get_fernet()
        plaintext = f.decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")

    @staticmethod
    def mask_key(api_key: str) -> str:
        """
        脱敏显示 API Key。

        长度 >= 8：前4位 + **** + 后4位
        长度 < 8：全部替换为星号
        """
        if len(api_key) >= 8:
            return api_key[:4] + "****" + api_key[-4:]
        return "*" * len(api_key)
