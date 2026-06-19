"""
TestCaseLoader：``test_cases`` 表 → RequestSpec。

用例字段映射：
- ``id``               → ``RequestSpec.case_id``（外部引用，给 reporter 用）
- ``name``             → ``RequestSpec.name``
- ``method``           → ``RequestSpec.method``
- ``url``              → ``RequestSpec.url``（可能是完整 URL 或带变量的 path，由 ExecutionContext 处理）
- ``headers``          → ``RequestSpec.headers``
- ``params``           → ``RequestSpec.params``
- ``body``             → ``RequestSpec.body``（默认 body_type=json）
- ``expected_status``  → ``AssertionRule(type="status_code", config={"expected": ...})``
- ``expected_response``→ ``AssertionRule(type="json_subset", config={"expected": ...})``

用例没有显式的 ``assertions`` / ``extracts`` 字段，期望值（``expected_*``）会**自动**转换为
对应断言。这与老 ``TestExecutor._validate`` / ``_match_response`` 的语义保持一致。

设计要点：
- 引擎核心**不**依赖 ORM；这里是引擎与 ``app/models/case.py`` 的唯一桥梁
- 找不到记录抛 ``LoaderError``（路由层翻译为 404）

作者: yandc
"""
from __future__ import annotations

import logging
from typing import Any

from app.engine.api_engine.exceptions import LoaderError
from app.engine.api_engine.loaders.base import BaseLoader
from app.engine.api_engine.specs import (
    AssertionRule,
    CollectionSpec,
    RequestSpec,
)

logger = logging.getLogger(__name__)


class TestCaseLoader(BaseLoader):
    """``test_cases`` 表 → RequestSpec。"""

    # ------------------------------------------------------------------
    # 单条转换
    # ------------------------------------------------------------------

    def load_request(
        self,
        *,
        case_id: int | None = None,
        case=None,
    ) -> RequestSpec:
        """根据 ``case_id`` 或已查询的 ``TestCase`` 实例构造 RequestSpec。

        必须传 ``case_id`` 或 ``case`` 二选一；同时传时 ``case`` 优先。

        Raises:
            LoaderError: 找不到对应 case_id 时
        """
        case = case if case is not None else self._fetch(case_id)
        return self._to_spec(case)

    # ------------------------------------------------------------------
    # 批量转换
    # ------------------------------------------------------------------

    def load_collection(
        self,
        *,
        case_ids: list[int],
        project_id: int,
        environment_id: int | None = None,
        fail_strategy: str = "continue",
        name: str = "test-case-sequence",
        initial_variables: dict[str, Any] | None = None,
    ) -> CollectionSpec:
        if not case_ids:
            from app.engine.api_engine.exceptions import InvalidRequestSpecError
            raise InvalidRequestSpecError(
                "case_ids 不能为空",
                details={"received_count": 0},
            )

        specs = [self.load_request(case_id=cid) for cid in case_ids]
        return CollectionSpec(
            name=name,
            project_id=project_id,
            environment_id=environment_id,
            requests=specs,
            fail_strategy=fail_strategy,
            initial_variables=dict(initial_variables or {}),
        )

    # ------------------------------------------------------------------
    # 数据访问 + 转换核心
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch(case_id: int | None):
        """从 DB 取 TestCase 实体；找不到抛 LoaderError。"""
        if case_id is None:
            raise LoaderError(
                "TestCaseLoader.load_request 必须提供 case_id 或 case",
                details={},
            )
        try:
            from app.models.case import TestCase
        except Exception as exc:  # pragma: no cover
            raise LoaderError(
                "无法导入 TestCase 模型；TestCaseLoader 需要 Flask 上下文",
                details={"reason": str(exc)},
            ) from exc

        case = TestCase.query.get(case_id)
        if case is None:
            raise LoaderError(
                f"测试用例不存在: case_id={case_id}",
                details={"case_id": case_id},
            )
        return case

    def _to_spec(self, case) -> RequestSpec:
        """把 ``TestCase`` 实例转 RequestSpec。"""
        spec = RequestSpec(
            name=case.name or f"case-{case.id}",
            method=(case.method or "GET").upper(),
            url=case.url or "",
            headers=dict(case.headers or {}),
            params=dict(case.params or {}),
            body=case.body,
            body_type="json",   # TestCase 模型未保存 body_type，按老逻辑统一 json
            timeout=30,
            assertions=self._build_auto_assertions(case),
            extracts=[],
            case_id=case.id,
            api_id=None,
        )
        logger.debug(
            "[api_engine] TestCaseLoader 转换完成 case_id=%s assertions=%d",
            case.id, len(spec.assertions),
        )
        return spec

    @staticmethod
    def _build_auto_assertions(case) -> list[AssertionRule]:
        """从 ``expected_status`` / ``expected_response`` 自动派生断言。

        与老 ``TestExecutor._validate`` 行为对齐：
        - 配 expected_status → status_code 断言
        - 配 expected_response（非空）→ json_subset 断言（结构部分匹配）
        """
        rules: list[AssertionRule] = []

        if case.expected_status:
            rules.append(AssertionRule(
                type="status_code",
                config={"expected": int(case.expected_status)},
                name=f"状态码 == {case.expected_status}",
            ))

        if case.expected_response:
            # expected_response 可能是 dict / list / 标量；任何非 None 非空 dict/list 都做断言
            er = case.expected_response
            if er is not None and er != {} and er != []:
                rules.append(AssertionRule(
                    type="json_subset",
                    config={"expected": er},
                    name="响应包含期望子结构",
                ))

        return rules
