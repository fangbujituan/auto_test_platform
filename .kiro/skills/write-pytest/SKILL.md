---
name: write-pytest
description: 给 ATP 后端的 service / engine / agent / route 模块补 pytest 测试，按"正常 / 边界 / 异常"三类组织 TestXxx 类，必要时用 unittest.mock + Flask app context + sqlite in-memory，落位到 app/tests/。
---

# 写 pytest 测试

## 何时激活

用户说要"写 / 加 / 补 / 设计 测试 / 单测 / pytest"，针对一个具体模块（service / agent / route / engine）。
典型触发词：「给 xxx_service 写单测」「补一下 xxx 的 pytest」「测一下 xxx 函数」。

⚠️ 项目惯例：**默认不主动加测试**（系统提示明确：「DO NOT automatically add tests unless explicitly requested by the user」）。本 skill 只在用户明确要求时激活。

## 必要输入

确认（缺哪个问哪个）：

- 被测目标（文件路径 + 类 / 函数名，如 `app/services/scheduler_service.py` 的 `SchedulerService`）
- 测试范围（仅核心方法 / 全量公共 API）
- 是否需要 DB（如果是，用 sqlite in-memory；不要连真 MySQL）
- 是否需要 mock 外部依赖（HTTP / LLM / 文件系统）

## 项目硬约束

1. **测试文件位置**：放在 `app/tests/`，文件名 `test_<被测模块>.py`（不要放仓库根 `tests/`，那个目录是历史脚本仓库）。
2. **不接 LLM 真实调用**：Agent 测试用 `state.input_data["mock"] = True` 走 mock 分支，零 token。
3. **不连真 MySQL**：DB 相关测试一律用 sqlite in-memory（`sqlite:///:memory:`），参考 `app/tests/test_scheduler_service.py`。
4. **测试组织**：用 `class TestXxx:` 分组，每个公共方法对应一个 `Test<MethodName>` 类，类内方法名用 `test_<场景>` 描述（**snake_case + 一句话场景**）。
5. **三段式覆盖**：每个被测函数至少 3 类用例：
   - **正常路径（happy path）**：合法输入 → 预期输出
   - **边界（boundary）**：空输入 / 极值 / 临界条件
   - **异常（error）**：非法输入 / 依赖故障 / 应抛特定异常
6. **不要写依赖外部网络的测试**（除非显式 mark，且默认跳过）。
7. **断言要明确**：用 `assert x == y, "<失败原因>"`，不要只写 `assert x`。
8. 用 `pytest.raises` 检查异常，不要 `try/except + pytest.fail`。
9. fixture / 共享资源放 `conftest.py`，本测试文件独享的 mock 直接在测试里写。

## 实现步骤

### 1. 阅读相邻样例

读：
- `app/tests/test_scheduler_service.py` —— 三段式 + sqlite in-memory + Flask context 范本
- `app/tests/test_curl_parser_preservation.py` —— 纯函数测试范本
- `app/tests/test_swagger_import_error_reporting.py` —— 错误场景范本

### 2. 列出被测函数 / 方法清单

用 `grep_search` 或 `read_code` 把目标模块的公共 API 抽出来，逐项标注：

| 方法 | 输入 | 输出 | 副作用 | 异常路径 |
|------|------|------|--------|----------|
| `add_cron_job(task_id, cron)` | int + str | None | scheduler 增 job | cron 非法 → ValueError |
| ... |

### 3. 写测试文件

新建 `app/tests/test_<module>.py`：

```python
"""
<被测模块>单元测试。

覆盖：
- <方法 1>：正常 / 边界 / 异常
- <方法 2>：正常 / 边界 / 异常
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.<module> import <Class>


class Test<Method1>:
    """<method1> 测试。"""

    # ---- 正常路径 ----
    def test_<场景描述>(self):
        """<一句话期望>。"""
        result = <Class>().<method1>(<合法参数>)
        assert result == <预期>, "应返回 <预期>"

    def test_<另一种正常输入>(self):
        ...

    # ---- 边界 ----
    def test_empty_input_returns_default(self):
        """空输入应返回默认值。"""
        assert <Class>().<method1>("") == <默认>

    def test_max_length_input_ok(self):
        """超长输入仍能处理。"""
        ...

    # ---- 异常 ----
    def test_invalid_input_raises_value_error(self):
        """非法输入应抛 ValueError。"""
        with pytest.raises(ValueError, match="<错误信息片段>"):
            <Class>().<method1>(<非法>)

    def test_dependency_failure(self):
        """外部依赖故障时优雅降级 / 抛特定异常。"""
        with patch("app.services.<module>.<dep>") as m:
            m.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                <Class>().<method1>(<合法>)


class Test<Method2>:
    """<method2> 测试。"""
    ...
```

### 4. 需要 Flask app context / DB 的写法

参考 `test_scheduler_service.py::TestRestoreJobs`：

```python
def test_xxx_with_db(self):
    from flask import Flask
    from app.models.base import db as real_db

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    real_db.init_app(app)

    with app.app_context():
        real_db.create_all()
        # ... 插测试数据 ...
        # ... 调用被测对象 ...
        assert ...
```

注意：用 `sqlite:///:memory:` 避免污染真库，每个测试函数独立创建 app + 内存库。

### 5. 需要 mock 外部 HTTP / LLM 的写法

```python
@patch("app.services.<module>.requests.get")
def test_external_call(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"ok": 1})
    ...
```

Agent 类测试**优先走 mock 模式**，不需要 patch LLM：

```python
import asyncio
from app.agents.business import IntentAgent
from app.agents.orchestration import AgentState


def test_intent_agent_mock_returns_structured_output():
    state = AgentState(
        task_id="t1", correlation_id="c1", workflow_id="w1",
        input_data={"requirement": "测一下登录页面", "mock": True},
    )
    out = asyncio.run(IntentAgent().execute(state))
    assert out.output_data["test_type"] in {"ui", "api", "performance"}
    assert out.metadata["model_used"] == "mock"
```

### 6. 跑测试

```bash
# 单文件
pytest app/tests/test_<module>.py -v

# 单类
pytest app/tests/test_<module>.py::Test<Method1> -v

# 单测试
pytest app/tests/test_<module>.py::Test<Method1>::test_<scenario> -v
```

不要用 watch 模式（项目守则禁止），必须一次性 `--run` 或裸 `pytest`。

## 验证

1. 全部测试 `PASSED`，没 `xfail` / `skip`（除非显式说明原因）。
2. 每个公共方法都覆盖了正常 / 边界 / 异常 3 类（最少 3 个 case）。
3. 测试无外部依赖（不连真 MySQL / 真 LLM / 真网络）。
4. 单测运行时间 < 5s（DB / mock 让它跑得快）。
5. 不要为了凑覆盖率写"调一下函数 + 不断言"的空测试 —— 必须有意义的断言。

## 反模式

- 测试里调真实 LLM —— 浪费 token，CI 会跑挂。
- 测试连真 MySQL —— 污染数据 + 环境耦合。
- 一个测试函数测 5 件事 —— 拆成 5 个 `test_xxx`。
- 用 `unittest.TestCase` —— 项目惯用 `pytest` 风格的 class（无继承）。
- 写完不跑 —— 必须本机跑通再交付。
- 不写 docstring —— 每个 `test_` 第一行写一句话期望，便于报告里看。
