"""
prefix_url 与 global params 适配器。

直接复用 ``app/services/variable_replacer.py`` 里已经稳定运行的解析逻辑，
不重新实现，只把它包成引擎友好的函数：

- 当 Flask app context 不可用时（单测）SHALL 静默返回空值，由调用方决定行为。
- 不抛异常到引擎核心层，避免污染 step 失败语义。

作者: yandc
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_prefix_url(
    *,
    environment_id: int | None,
    module: str | None,
    service: str | None,
    base_url: str,
) -> str:
    """根据接口的 module/service 匹配当前环境的前置 URL。

    优先级：接口自带 base_url > 精确匹配 > 默认匹配 > 空串。
    """
    try:
        from app.services.variable_replacer import resolve_prefix_url as _resolve
    except Exception:  # pragma: no cover - 极端环境（无 Flask）
        return base_url or ""

    try:
        return _resolve(
            environment_id=environment_id,
            module=module,
            service=service,
            base_url=base_url,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("[api_engine] resolve_prefix_url 失败，回退原 base_url: %s", exc)
        return base_url or ""


def merge_global_params(
    *,
    project_id: int,
    headers: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并项目级 GlobalParam 到请求 Header。

    请求中已有的同名 Header 优先；DB 不可用时原样返回。
    """
    headers = dict(headers or {})
    try:
        from app.services.variable_replacer import merge_global_params as _merge
    except Exception:  # pragma: no cover
        return headers

    try:
        return _merge(project_id=project_id, headers=headers)
    except Exception as exc:  # pragma: no cover
        logger.warning("[api_engine] merge_global_params 失败，原 headers 返回: %s", exc)
        return headers


def load_project_variables(
    *,
    project_id: int,
    environment_id: int | None,
) -> dict[str, Any]:
    """加载项目级"全局变量 + 环境变量"，环境变量覆盖同名全局变量。

    返回扁平 ``{name: value}`` 字典；DB 不可用时返回空字典。
    """
    variables: dict[str, Any] = {}
    try:
        from app.models.env_variable import EnvironmentVariable, GlobalVariable
    except Exception:  # pragma: no cover
        return variables

    try:
        # 1. 全局变量（优先级低）
        for record in GlobalVariable.query.filter_by(project_id=project_id).all():
            variables[record.name] = record.value
        # 2. 环境变量（优先级高，覆盖同名）
        if environment_id is not None:
            env_records = EnvironmentVariable.query.filter_by(
                project_id=project_id, environment_id=environment_id
            ).all()
        else:
            # 兼容老调用：environment_id=None 时加载该项目全部 EnvironmentVariable
            env_records = EnvironmentVariable.query.filter_by(project_id=project_id).all()
        for record in env_records:
            variables[record.name] = record.value
    except Exception as exc:  # pragma: no cover
        logger.warning("[api_engine] load_project_variables 失败: %s", exc)

    return variables
