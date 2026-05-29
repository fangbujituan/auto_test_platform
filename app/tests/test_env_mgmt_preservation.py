"""
保持性属性测试 — 变量替换与 URL 拼接行为保持不变

Property 2: Preservation - 在未修复代码上验证基线行为，确保修复后这些行为不变。

遵循观察优先方法论：
- 观察: replace_in_request 对单一变量替换正常工作
- 观察: 不存在的变量占位符保留原始文本
- 观察: _replace_in_string / _replace_in_value 对 dict、list、str 类型递归替换正常
- 观察: 变量替换异常时返回原始未替换数据

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from hypothesis import given, strategies as st, settings, assume

from app.services.variable_replacer import (
    _replace_in_string,
    _replace_in_value,
    VARIABLE_PATTERN,
)


# ── 策略定义 ──────────────────────────────────────────────────────

# 合法变量名：字母或下划线开头，后跟字母数字下划线
var_name_st = st.from_regex(r"[A-Za-z_]\w{0,15}", fullmatch=True)

# 变量值：不含 {{ }} 的非空字符串
var_value_st = st.text(
    alphabet=st.characters(blacklist_characters="{}"),
    min_size=1,
    max_size=50,
)

# 普通文本：不含 {{ }} 的字符串（用于构造不含占位符的输入）
plain_text_st = st.text(
    alphabet=st.characters(blacklist_characters="{}"),
    min_size=0,
    max_size=100,
)

# 生成变量字典：变量名 -> 变量值
variables_st = st.dictionaries(
    keys=var_name_st,
    values=var_value_st,
    min_size=0,
    max_size=5,
)


# ── 辅助策略 ──────────────────────────────────────────────────────

def text_with_known_placeholders_st():
    """生成包含已知变量占位符的文本和对应变量字典。"""
    return st.tuples(var_name_st, var_value_st, plain_text_st, plain_text_st).map(
        lambda t: (
            f"{t[2]}{{{{{t[0]}}}}}{t[3]}",  # "prefix{{var_name}}suffix"
            {t[0]: t[1]},                     # {var_name: var_value}
            t[0],                              # var_name
            t[1],                              # var_value
        )
    )


def text_with_unknown_placeholder_st():
    """生成包含不存在变量占位符的文本（变量字典中无此变量）。"""
    return st.tuples(var_name_st, var_name_st, var_value_st, plain_text_st).filter(
        lambda t: t[0] != t[1]  # 确保占位符变量名与字典中的变量名不同
    ).map(
        lambda t: (
            f"{t[3]}{{{{{t[0]}}}}}",          # "prefix{{unknown_var}}"
            {t[1]: t[2]},                      # {other_var: value}（不含 unknown_var）
            t[0],                              # unknown_var_name
        )
    )


# 递归值策略：生成 str / dict / list 嵌套结构
def recursive_value_st():
    """生成可递归替换的值：str、dict、list 嵌套结构。"""
    leaf = plain_text_st
    return st.recursive(
        leaf,
        lambda children: st.one_of(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=10),
                values=children,
                min_size=0,
                max_size=3,
            ),
            st.lists(children, min_size=0, max_size=3),
        ),
        max_leaves=5,
    )


# ── Property 2a: _replace_in_string 对已知变量正确替换 ─────────────
# **Validates: Requirements 3.2**

class TestReplaceInStringPreservation:
    """
    保持性: _replace_in_string 对 {{变量名}} 占位符的替换行为。

    观察: 在未修复代码上，当变量存在时，{{变量名}} 被正确替换为变量值。
    """

    @given(data=text_with_known_placeholders_st())
    @settings(max_examples=100, deadline=None)
    def test_known_variable_is_replaced(self, data):
        """
        属性: 当变量存在于字典中时，{{变量名}} 应被替换为对应的值。

        **Validates: Requirements 3.2**
        """
        text, variables, var_name, var_value = data
        result = _replace_in_string(text, variables)

        # 替换后的结果不应再包含该变量的占位符
        placeholder = f"{{{{{var_name}}}}}"
        assert placeholder not in result, (
            f"变量 {var_name} 存在于字典中，但占位符 {placeholder} 未被替换。"
            f"输入: {text!r}, 变量: {variables}, 结果: {result!r}"
        )

        # 替换后的结果应包含变量值（当值非空时）
        assert var_value in result, (
            f"变量 {var_name}={var_value!r} 应出现在替换结果中。"
            f"输入: {text!r}, 结果: {result!r}"
        )

    @given(data=text_with_unknown_placeholder_st())
    @settings(max_examples=100, deadline=None)
    def test_unknown_variable_placeholder_preserved(self, data):
        """
        属性: 当变量不存在于字典中时，{{变量名}} 占位符保留原始文本。

        **Validates: Requirements 3.3**
        """
        text, variables, unknown_var = data
        result = _replace_in_string(text, variables)

        # 不存在的变量占位符应保留原文
        placeholder = f"{{{{{unknown_var}}}}}"
        assert placeholder in result, (
            f"不存在的变量 {unknown_var} 的占位符应保留原文。"
            f"输入: {text!r}, 变量: {variables}, 结果: {result!r}"
        )

    @given(text=plain_text_st, variables=variables_st)
    @settings(max_examples=100, deadline=None)
    def test_text_without_placeholders_unchanged(self, text, variables):
        """
        属性: 不含 {{}} 占位符的文本经过替换后保持不变。

        **Validates: Requirements 3.2**
        """
        result = _replace_in_string(text, variables)
        assert result == text, (
            f"不含占位符的文本应保持不变。"
            f"输入: {text!r}, 结果: {result!r}"
        )

    @given(text=plain_text_st)
    @settings(max_examples=50, deadline=None)
    def test_empty_variables_dict_preserves_text(self, text):
        """
        属性: 空变量字典时，任何文本保持不变（占位符也保留）。

        **Validates: Requirements 3.3**
        """
        result = _replace_in_string(text, {})
        assert result == text, (
            f"空变量字典时文本应保持不变。"
            f"输入: {text!r}, 结果: {result!r}"
        )

    @given(value=st.one_of(st.integers(), st.floats(allow_nan=False), st.none()))
    @settings(max_examples=50, deadline=None)
    def test_non_string_input_returned_as_is(self, value):
        """
        属性: 非字符串输入直接返回原值，不做替换。

        **Validates: Requirements 3.2**
        """
        result = _replace_in_string(value, {"any": "val"})
        assert result == value or (result != result and value != value), (
            f"非字符串输入应直接返回。输入: {value!r}, 结果: {result!r}"
        )


# ── Property 2b: _replace_in_value 递归替换行为 ───────────────────
# **Validates: Requirements 3.2, 3.3**

class TestReplaceInValuePreservation:
    """
    保持性: _replace_in_value 对 dict、list、str 类型的递归替换行为。

    观察: 在未修复代码上，_replace_in_value 正确递归处理嵌套结构。
    """

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
        extra_text=plain_text_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_string_value_replacement(self, var_name, var_value, extra_text):
        """
        属性: 字符串值中的 {{变量名}} 被正确替换。

        **Validates: Requirements 3.2**
        """
        text = f"{extra_text}{{{{{var_name}}}}}"
        variables = {var_name: var_value}
        result = _replace_in_value(text, variables)

        assert isinstance(result, str), "字符串输入应返回字符串"
        assert f"{{{{{var_name}}}}}" not in result, (
            f"字符串值中的占位符应被替换。输入: {text!r}, 结果: {result!r}"
        )

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
        dict_key=st.text(min_size=1, max_size=10),
    )
    @settings(max_examples=100, deadline=None)
    def test_dict_value_recursive_replacement(self, var_name, var_value, dict_key):
        """
        属性: dict 类型值中嵌套的 {{变量名}} 被递归替换。

        **Validates: Requirements 3.2**
        """
        input_dict = {dict_key: f"{{{{{var_name}}}}}"}
        variables = {var_name: var_value}
        result = _replace_in_value(input_dict, variables)

        assert isinstance(result, dict), "dict 输入应返回 dict"
        assert result[dict_key] == var_value, (
            f"dict 中的占位符应被替换。"
            f"输入: {input_dict}, 结果: {result}"
        )

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_list_value_recursive_replacement(self, var_name, var_value):
        """
        属性: list 类型值中嵌套的 {{变量名}} 被递归替换。

        **Validates: Requirements 3.2**
        """
        input_list = [f"{{{{{var_name}}}}}"]
        variables = {var_name: var_value}
        result = _replace_in_value(input_list, variables)

        assert isinstance(result, list), "list 输入应返回 list"
        assert result[0] == var_value, (
            f"list 中的占位符应被替换。"
            f"输入: {input_list}, 结果: {result}"
        )

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
        inner_key=st.text(min_size=1, max_size=10),
    )
    @settings(max_examples=50, deadline=None)
    def test_nested_dict_in_list_replacement(self, var_name, var_value, inner_key):
        """
        属性: list 中嵌套 dict 的 {{变量名}} 被递归替换。

        **Validates: Requirements 3.2**
        """
        input_val = [{"nested": {inner_key: f"{{{{{var_name}}}}}"}}]
        variables = {var_name: var_value}
        result = _replace_in_value(input_val, variables)

        assert result[0]["nested"][inner_key] == var_value, (
            f"嵌套结构中的占位符应被递归替换。"
            f"输入: {input_val}, 结果: {result}"
        )

    @given(value=st.one_of(st.integers(), st.floats(allow_nan=False), st.booleans(), st.none()))
    @settings(max_examples=50, deadline=None)
    def test_non_container_value_returned_as_is(self, value):
        """
        属性: 非 str/dict/list 类型的值直接返回，不做替换。

        **Validates: Requirements 3.2**
        """
        result = _replace_in_value(value, {"any": "val"})
        assert result == value or (result != result and value != value), (
            f"非容器类型应直接返回。输入: {value!r}, 结果: {result!r}"
        )

    @given(
        var_name=var_name_st,
        other_var=var_name_st,
        var_value=var_value_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_unknown_placeholder_preserved_in_nested(self, var_name, other_var, var_value):
        """
        属性: 嵌套结构中不存在的变量占位符保留原文。

        **Validates: Requirements 3.3**
        """
        assume(var_name != other_var)
        input_val = {"key": [f"{{{{{var_name}}}}}"]}
        variables = {other_var: var_value}
        result = _replace_in_value(input_val, variables)

        assert result["key"][0] == f"{{{{{var_name}}}}}", (
            f"不存在的变量占位符应保留原文。"
            f"输入: {input_val}, 变量: {variables}, 结果: {result}"
        )


# ── Property 2c: replace_in_request 异常处理保持性 ────────────────
# **Validates: Requirements 3.6**

class TestReplaceInRequestExceptionPreservation:
    """
    保持性: 变量替换异常时返回原始未替换数据。

    观察: 在未修复代码上，当数据库查询失败时，replace_in_request 返回原始数据。
    此测试通过 mock 数据库查询异常来验证此行为。
    """

    @given(
        base_url=st.text(min_size=0, max_size=50),
        path=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=50, deadline=None)
    def test_exception_returns_original_data(self, base_url, path):
        """
        属性: 当变量查询异常时，返回原始未替换的数据。

        通过 mock EnvironmentVariable 类使其 query 属性抛出异常来验证。

        **Validates: Requirements 3.6**
        """
        from unittest.mock import patch, MagicMock

        headers = {"Content-Type": "application/json"}
        params = {"key": "value"}
        body = {"data": "test"}

        # 创建一个 mock EnvironmentVariable 类，其 query.filter_by 抛出异常
        mock_env_var_cls = MagicMock()
        mock_env_var_cls.query.filter_by.side_effect = Exception("数据库连接失败")

        with patch(
            "app.services.variable_replacer.EnvironmentVariable",
            mock_env_var_cls,
        ):
            from app.services.variable_replacer import replace_in_request
            result = replace_in_request(
                project_id=999,
                base_url=base_url,
                path=path,
                headers=headers,
                params=params,
                body=body,
                body_type="json",
            )

        # 异常时应返回原始数据
        assert result == (base_url, path, headers, params, body), (
            f"异常时应返回原始数据。"
            f"base_url={base_url!r}, path={path!r}, 结果: {result}"
        )


# ── Property 2d: replace_in_request 单一变量替换正常工作 ──────────
# **Validates: Requirements 3.1, 3.2**

class TestReplaceInRequestSingleVarPreservation:
    """
    保持性: replace_in_request 对单一变量替换正常工作。

    观察: 在未修复代码上，当只有一个变量时，replace_in_request 正确替换所有位置。
    """

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_single_variable_replacement_in_all_fields(self, var_name, var_value):
        """
        属性: 单一变量在 base_url、path、headers、params、body 中均被正确替换。

        通过 mock 数据库返回单一变量来验证替换行为。

        **Validates: Requirements 3.1, 3.2**
        """
        from unittest.mock import MagicMock, patch

        placeholder = f"{{{{{var_name}}}}}"

        # 构造包含占位符的请求数据
        base_url = f"https://{placeholder}.example.com"
        path = f"/api/{placeholder}"
        headers = {"Authorization": f"Bearer {placeholder}"}
        params = {"token": placeholder}
        body = {"user": placeholder}

        # 模拟数据库返回单一变量
        mock_record = MagicMock()
        mock_record.name = var_name
        mock_record.value = var_value

        mock_env_var_cls = MagicMock()
        mock_env_var_cls.query.filter_by.return_value.all.return_value = [mock_record]

        with patch(
            "app.services.variable_replacer.EnvironmentVariable",
            mock_env_var_cls,
        ):
            from app.services.variable_replacer import replace_in_request
            r_base, r_path, r_headers, r_params, r_body = replace_in_request(
                project_id=1,
                base_url=base_url,
                path=path,
                headers=headers,
                params=params,
                body=body,
                body_type="json",
            )

        # 验证所有位置的占位符都被替换
        assert placeholder not in r_base, (
            f"base_url 中的占位符应被替换。结果: {r_base!r}"
        )
        assert placeholder not in r_path, (
            f"path 中的占位符应被替换。结果: {r_path!r}"
        )
        assert placeholder not in r_headers.get("Authorization", ""), (
            f"headers 中的占位符应被替换。结果: {r_headers}"
        )
        assert placeholder not in r_params.get("token", ""), (
            f"params 中的占位符应被替换。结果: {r_params}"
        )
        assert placeholder not in r_body.get("user", ""), (
            f"body 中的占位符应被替换。结果: {r_body}"
        )

        # 验证替换后包含正确的值
        assert var_value in r_base, f"base_url 应包含变量值 {var_value!r}"
        assert var_value in r_path, f"path 应包含变量值 {var_value!r}"

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
        unknown_var=var_name_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_mixed_known_and_unknown_variables(self, var_name, var_value, unknown_var):
        """
        属性: 已知变量被替换，未知变量保留原始占位符。

        **Validates: Requirements 3.2, 3.3**
        """
        assume(var_name != unknown_var)
        from unittest.mock import MagicMock, patch

        known_ph = f"{{{{{var_name}}}}}"
        unknown_ph = f"{{{{{unknown_var}}}}}"

        base_url = f"https://{known_ph}.example.com"
        path = f"/api/{unknown_ph}/resource"
        headers = {}
        params = {}
        body = {}

        mock_record = MagicMock()
        mock_record.name = var_name
        mock_record.value = var_value

        mock_env_var_cls = MagicMock()
        mock_env_var_cls.query.filter_by.return_value.all.return_value = [mock_record]

        with patch(
            "app.services.variable_replacer.EnvironmentVariable",
            mock_env_var_cls,
        ):
            from app.services.variable_replacer import replace_in_request
            r_base, r_path, r_headers, r_params, r_body = replace_in_request(
                project_id=1,
                base_url=base_url,
                path=path,
                headers=headers,
                params=params,
                body=body,
                body_type="json",
            )

        # 已知变量被替换
        assert known_ph not in r_base, (
            f"已知变量 {var_name} 应被替换。结果: {r_base!r}"
        )
        # 未知变量保留原文
        assert unknown_ph in r_path, (
            f"未知变量 {unknown_var} 的占位符应保留。结果: {r_path!r}"
        )

    @given(
        base_url=plain_text_st,
        path=plain_text_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_no_variables_returns_original(self, base_url, path):
        """
        属性: 当数据库中无变量时，返回原始数据不变。

        **Validates: Requirements 3.2**
        """
        from unittest.mock import MagicMock, patch

        headers = {"key": "val"}
        params = {"p": "v"}
        body = {"b": "d"}

        mock_env_var_cls = MagicMock()
        mock_env_var_cls.query.filter_by.return_value.all.return_value = []

        with patch(
            "app.services.variable_replacer.EnvironmentVariable",
            mock_env_var_cls,
        ):
            from app.services.variable_replacer import replace_in_request
            result = replace_in_request(
                project_id=1,
                base_url=base_url,
                path=path,
                headers=headers,
                params=params,
                body=body,
                body_type="json",
            )

        assert result == (base_url, path, headers, params, body), (
            f"无变量时应返回原始数据。结果: {result}"
        )
