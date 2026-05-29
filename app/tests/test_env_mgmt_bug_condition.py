"""
Bug 条件探索性测试 — 环境变量优先级与前置 URL 匹配缺陷

在未修复的代码上运行时，这些测试应当失败，从而证明 bug 存在。
使用 Hypothesis 进行基于属性的测试，生成随机输入以发现反例。

**Validates: Requirements 1.3, 1.7, 1.8, 1.9, 1.10, 2.3, 2.7, 2.9, 2.10**
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from hypothesis import given, strategies as st, settings

from app.services.variable_replacer import replace_in_request, _replace_in_string


# ── 策略定义 ──────────────────────────────────────────────────────

# 生成合法的变量名（字母数字下划线，非空）
var_name_st = st.from_regex(r"[A-Za-z_]\w{0,19}", fullmatch=True)

# 生成变量值（非空字符串，不含 {{ }}）
var_value_st = st.text(
    alphabet=st.characters(blacklist_characters="{}"),
    min_size=1,
    max_size=50,
)

# 生成模块/服务名称
module_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# 生成 URL
url_st = st.from_regex(r"https?://[a-z]{3,10}\.[a-z]{2,5}", fullmatch=True)

# 生成接口路径
path_st = st.from_regex(r"/[a-z]{1,10}(/[a-z]{1,10}){0,3}", fullmatch=True)


# ── Property 1: 环境变量优先于全局变量 ──────────────────────────────
# **Validates: Requirements 2.7**

class TestVariablePriorityBugCondition:
    """
    Bug 条件: 当全局变量和环境变量同名时，replace_in_request 无法区分优先级。

    当前 replace_in_request 函数签名不接受 environment_id 参数，
    因此无法实现"环境变量优先于全局变量"的优先级机制。
    """

    @given(
        var_name=var_name_st,
        global_value=var_value_st,
        env_value=var_value_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_replace_in_request_accepts_environment_id(
        self, var_name, global_value, env_value
    ):
        """
        Property 1: replace_in_request 函数应接受 environment_id 参数。

        当前函数签名为:
          replace_in_request(project_id, base_url, path, headers, params, body, body_type)
        期望函数签名应包含 environment_id 参数以支持变量优先级。

        **Validates: Requirements 2.7**
        """
        # 检查 replace_in_request 函数是否接受 environment_id 参数
        sig = inspect.signature(replace_in_request)
        param_names = list(sig.parameters.keys())

        assert "environment_id" in param_names, (
            f"replace_in_request 函数签名缺少 environment_id 参数。"
            f"当前参数: {param_names}。"
            f"无法区分全局变量 {var_name}={global_value} "
            f"和环境变量 {var_name}={env_value} 的优先级。"
        )


# ── Property 2: 前置 URL 自动匹配 ──────────────────────────────────
# **Validates: Requirements 2.9, 2.10**

class TestPrefixUrlMatchingBugCondition:
    """
    Bug 条件: 当接口 base_url 为空时，系统无法根据模块/服务自动匹配前置 URL。

    当前系统不存在 resolve_prefix_url 函数，也不存在 PrefixUrl 数据模型，
    因此无法实现前置 URL 的自动匹配。
    """

    @given(
        module=module_st,
        service=module_st,
        prefix_url=url_st,
        api_path=path_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_resolve_prefix_url_function_exists(
        self, module, service, prefix_url, api_path
    ):
        """
        Property 2: variable_replacer 模块应提供 resolve_prefix_url 函数。

        当 base_url 为空且当前环境配置了对应模块/服务的前置 URL 时，
        系统应自动使用匹配的前置 URL 作为域名拼接完整请求 URL。

        **Validates: Requirements 2.9**
        """
        import app.services.variable_replacer as vr_module

        assert hasattr(vr_module, "resolve_prefix_url"), (
            f"variable_replacer 模块缺少 resolve_prefix_url 函数。"
            f"当 base_url 为空、接口路径为 {api_path}、"
            f"模块={module}、服务={service} 时，"
            f"无法自动匹配前置 URL {prefix_url}。"
        )


# ── Property 3: 接口自带域名优先 ──────────────────────────────────
# **Validates: Requirements 2.10**

class TestInterfaceDomainPriorityBugCondition:
    """
    Bug 条件: 当接口 base_url 非空时，系统需要明确的优先级规则。

    当前系统没有 resolve_prefix_url 函数，因此也没有
    "接口自带域名优先于环境前置 URL"的优先级逻辑。
    """

    @given(
        own_base_url=url_st,
        prefix_url=url_st,
        api_path=path_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_interface_domain_priority_logic_exists(
        self, own_base_url, prefix_url, api_path
    ):
        """
        Property 3: 当 resolve_prefix_url 存在时，base_url 非空应跳过匹配。

        由于 resolve_prefix_url 函数不存在，此属性无法被验证，
        测试通过检查函数存在性来证明缺陷。

        **Validates: Requirements 2.10**
        """
        import app.services.variable_replacer as vr_module

        # 首先，resolve_prefix_url 必须存在
        assert hasattr(vr_module, "resolve_prefix_url"), (
            f"variable_replacer 模块缺少 resolve_prefix_url 函数。"
            f"无法验证接口自带域名 {own_base_url} 是否优先于"
            f"环境前置 URL {prefix_url}（路径: {api_path}）。"
        )


# ── Property 4: 数据模型完整性 ──────────────────────────────────
# **Validates: Requirements 2.3, 2.13**

class TestDataModelBugCondition:
    """
    Bug 条件: 当前不存在 Environment、PrefixUrl、GlobalVariable、GlobalParam 数据模型。

    缺少这些模型意味着系统无法支持环境分组、前置 URL 配置、
    全局变量管理和全局参数管理功能。
    """

    @given(env_name=st.text(min_size=1, max_size=20))
    @settings(max_examples=30, deadline=None)
    def test_environment_model_exists(self, env_name):
        """
        Property 4a: Environment 数据模型应存在。

        环境分组功能需要 Environment 模型来组织变量和前置 URL。

        **Validates: Requirements 2.3**
        """
        import app.models.env_variable as models_module

        assert hasattr(models_module, "Environment"), (
            f"env_variable 模块缺少 Environment 模型。"
            f"无法创建环境分组 '{env_name}'。"
        )

    @given(
        module=module_st,
        service=module_st,
        url=url_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_prefix_url_model_exists(self, module, service, url):
        """
        Property 4b: PrefixUrl 数据模型应存在。

        前置 URL 配置功能需要 PrefixUrl 模型来存储模块/服务/URL 映射。

        **Validates: Requirements 2.9**
        """
        import app.models.env_variable as models_module

        assert hasattr(models_module, "PrefixUrl"), (
            f"env_variable 模块缺少 PrefixUrl 模型。"
            f"无法为模块={module}、服务={service} 配置前置 URL {url}。"
        )

    @given(
        var_name=var_name_st,
        var_value=var_value_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_global_variable_model_exists(self, var_name, var_value):
        """
        Property 4c: GlobalVariable 数据模型应存在。

        全局变量管理功能需要 GlobalVariable 模型来存储跨环境共享的变量。

        **Validates: Requirements 2.7**
        """
        import app.models.env_variable as models_module

        assert hasattr(models_module, "GlobalVariable"), (
            f"env_variable 模块缺少 GlobalVariable 模型。"
            f"无法管理全局变量 {var_name}={var_value}。"
        )

    @given(
        param_name=var_name_st,
        param_value=var_value_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_global_param_model_exists(self, param_name, param_value):
        """
        Property 4d: GlobalParam 数据模型应存在。

        全局参数管理功能需要 GlobalParam 模型来存储跨环境共享的 Header 参数。

        **Validates: Requirements 2.3**
        """
        import app.models.env_variable as models_module

        assert hasattr(models_module, "GlobalParam"), (
            f"env_variable 模块缺少 GlobalParam 模型。"
            f"无法管理全局参数 {param_name}={param_value}。"
        )
