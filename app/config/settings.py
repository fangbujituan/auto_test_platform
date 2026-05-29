"""
应用程序配置设置。

所有配置值从环境变量读取，默认值见 .env.example。
作者: yandc
创建时间: 2026-01-13
"""
import os


class Config:
    """基础配置。"""

    SECRET_KEY = os.getenv("SECRET_KEY")

    # JSON配置 - 确保中文正常显示
    JSON_AS_ASCII = False
    JSONIFY_MIMETYPE = "application/json; charset=utf-8"

    # MySQL配置
    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """开发环境配置。"""

    DEBUG = True


class TestingConfig(Config):
    """测试环境配置。"""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    """生产环境配置。"""

    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
