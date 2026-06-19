"""
Loader 基类 / Protocol。

所有数据适配器（数据库模型 / 前端 dict → spec）的统一接口。

设计要点：
- Loader 是引擎里**唯一**允许 import ORM 模型的层；引擎核心保持 ORM 无依赖。
- 提供 ``load_request`` / ``load_collection`` 两个方法，子类按需重写其中之一或两者都实现。
- 默认 ``load_collection`` 退化为多次 ``load_request`` 拼装；子类可覆盖以更高效。

作者: yandc
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.engine.api_engine.specs import CollectionSpec, RequestSpec


class BaseLoader(ABC):
    """Loader 抽象基类。

    子类必须实现 ``load_request``（单条转换）；``load_collection`` 提供默认实现。
    """

    @abstractmethod
    def load_request(self, *args: Any, **kwargs: Any) -> RequestSpec:
        """把单条数据源转换成 ``RequestSpec``。"""

    def load_collection(self, *args: Any, **kwargs: Any) -> CollectionSpec:
        """把多条数据源转换成 ``CollectionSpec``。

        默认实现：要求子类自行覆盖。本方法直接抛 ``NotImplementedError`` 而不是
        提供 stub，避免上层误以为有可用的批量入口。
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 未实现 load_collection；"
            f"如需批量加载请覆盖此方法"
        )
