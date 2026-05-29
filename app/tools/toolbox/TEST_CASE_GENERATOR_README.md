# 测试用例自动生成器使用指南

## 📖 简介

这是一个智能的接口测试用例生成器，能够根据参数定义自动生成高质量的测试用例。支持：

- ✅ **等价类划分**：自动识别有效/无效等价类
- ✅ **边界值分析**：自动生成边界值测试用例
- ✅ **正交实验**：支持参数组合测试（Pairwise）
- ✅ **类型校验**：自动生成类型错误用例
- ✅ **唯一性约束**：支持唯一字段测试
- ✅ **必传/非必传**：区分必传和可选参数

## 🚀 快速开始

### 基本使用

```python
from app.tools.toolbox.test_case_generator import (
    TestCaseGenerator,
    FieldConstraint,
    FieldType
)

# 1. 定义基准参数（一组正确的参数）
base_params = {
    "username": "testuser",
    "password": "Pass@123",
    "email": "test@example.com"
}

# 2. 定义字段约束
constraints = [
    FieldConstraint(
        field_name="username",
        field_type=FieldType.STRING,
        required=True,           # 必传
        min_length=3,           # 最小长度
        max_length=20,          # 最大长度
        unique=True,            # 唯一约束
        description="用户名"
    ),
    FieldConstraint(
        field_name="password",
        field_type=FieldType.STRING,
        required=True,
        min_length=6,
        max_length=50
    ),
    FieldConstraint(
        field_name="email",
        field_type=FieldType.EMAIL,
        required=True,
        unique=True
    )
]

# 3. 生成测试用例
generator = TestCaseGenerator(base_params, constraints)
test_cases = generator.generate_all_cases()

# 4. 查看结果
print(f"生成了 {len(test_cases)} 个测试用例")
for case in test_cases:
    print(f"{case.case_id}: {case.description}")
```

## 📋 字段类型支持

```python
class FieldType(Enum):
    STRING = "string"      # 字符串
    INTEGER = "integer"    # 整数
    FLOAT = "float"        # 浮点数
    BOOLEAN = "boolean"    # 布尔值
    ARRAY = "array"        # 数组
    OBJECT = "object"      # 对象
    EMAIL = "email"        # 邮箱
    PHONE = "phone"        # 手机号
    DATE = "date"          # 日期
```

## 🔧 字段约束参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `field_name` | str | 字段名称 | "username" |
| `field_type` | FieldType | 字段类型 | FieldType.STRING |
| `required` | bool | 是否必传 | True |
| `min_length` | int | 最小长度（字符串） | 3 |
| `max_length` | int | 最大长度（字符串） | 20 |
| `min_value` | float | 最小值（数值） | 0 |
| `max_value` | float | 最大值（数值） | 100 |
| `pattern` | str | 正则表达式 | "^[a-zA-Z0-9]+$" |
| `enum_values` | list | 枚举值 | ["male", "female"] |
| `unique` | bool | 是否唯一 | True |
| `description` | str | 字段描述 | "用户名" |

## 📊 生成的用例类型

### 1. 正向用例（POSITIVE）
- 最小必传参数集
- 全参数正常值

### 2. 负向用例（NEGATIVE）
- 缺失必传参数
- 必传参数为None
- 必传参数为空字符串
- 类型错误
- 唯一性冲突

### 3. 边界值用例（BOUNDARY）
- 字符串长度边界（min-1, min, max, max+1）
- 数值边界（min-1, min, max, max+1）

### 4. 组合用例（COMBINATION）
- 参数两两组合测试（Pairwise）

## 💡 实际应用示例

### 示例1：用户注册接口

```python
base_params = {
    "username": "testuser123",
    "password": "Pass@123456",
    "email": "test@example.com",
    "phone": "13800138000",
    "age": 25,
    "agree_terms": True
}

constraints = [
    FieldConstraint("username", FieldType.STRING, required=True, 
                   min_length=3, max_length=20, unique=True),
    FieldConstraint("password", FieldType.STRING, required=True, 
                   min_length=6, max_length=50),
    FieldConstraint("email", FieldType.EMAIL, required=True, unique=True),
    FieldConstraint("phone", FieldType.PHONE, required=False, 
                   min_length=11, max_length=11),
    FieldConstraint("age", FieldType.INTEGER, required=False, 
                   min_value=1, max_value=150),
    FieldConstraint("agree_terms", FieldType.BOOLEAN, required=True)
]

generator = TestCaseGenerator(base_params, constraints)
test_cases = generator.generate_all_cases()

# 导出为JSON
import json
with open("test_cases.json", "w", encoding="utf-8") as f:
    json.dump(generator.export_to_dict(), f, ensure_ascii=False, indent=2)

# 导出为Markdown
with open("test_cases.md", "w", encoding="utf-8") as f:
    f.write(generator.export_to_markdown())
```

### 示例2：创建项目接口

```python
base_params = {
    "name": "测试项目",
    "project_type": "web",
    "priority": 1,
    "budget": 100000.50,
    "is_public": False
}

constraints = [
    FieldConstraint("name", FieldType.STRING, required=True, 
                   min_length=1, max_length=100, unique=True),
    FieldConstraint("project_type", FieldType.STRING, required=True,
                   enum_values=["web", "mobile", "desktop", "api"]),
    FieldConstraint("priority", FieldType.INTEGER, required=False,
                   min_value=1, max_value=5),
    FieldConstraint("budget", FieldType.FLOAT, required=False,
                   min_value=0, max_value=9999999.99),
    FieldConstraint("is_public", FieldType.BOOLEAN, required=False)
]

generator = TestCaseGenerator(base_params, constraints)
test_cases = generator.generate_all_cases()
```

## 🎯 高级用法

### 控制生成的用例类型

```python
test_cases = generator.generate_all_cases(
    include_positive=True,      # 包含正向用例
    include_negative=True,      # 包含负向用例
    include_boundary=True,      # 包含边界值用例
    include_combination=True,   # 包含组合用例
    combination_depth=2         # 组合深度（2=两两组合）
)
```

### 获取统计信息

```python
stats = generator.get_statistics()
print(f"总计: {stats['total']}")
print(f"正向: {stats['positive']}")
print(f"负向: {stats['negative']}")
print(f"边界: {stats['boundary']}")
print(f"组合: {stats['combination']}")
```

### 导出格式

```python
# 导出为字典列表
dict_list = generator.export_to_dict()

# 导出为Markdown
markdown = generator.export_to_markdown()

# 访问原始用例对象
for case in generator.generated_cases:
    print(case.case_id)
    print(case.case_type)
    print(case.description)
    print(case.params)
    print(case.expected_result)
    print(case.test_point)
```

## 📈 用例数量估算

假设接口有 N 个参数（M 个必传，N-M 个非必传）：

| 用例类型 | 数量估算 | 说明 |
|---------|---------|------|
| 正向用例 | 2 | 最小必传 + 全参数 |
| 必传参数负向 | M × 3 | 每个必传参数：缺失、None、空值 |
| 边界值 | 字段数 × 4 | 每个有边界的字段：4个边界用例 |
| 类型错误 | 字段数 × 2 | 每个字段：2个类型错误 |
| 唯一性 | 唯一字段数 | 每个唯一字段：1个重复用例 |
| 组合测试 | C(高优先级字段, 2) × 4 | 两两组合 |

**示例**：10个参数（6必传 + 4非必传），3个有边界，2个唯一
- 正向：2个
- 负向：6×3 = 18个
- 边界：3×4 = 12个
- 类型：10×2 = 20个
- 唯一：2个
- 组合：约20个
- **总计：约74个用例**

## 🔍 测试策略建议

### 1. 冒烟测试（快速验证）
```python
test_cases = generator.generate_all_cases(
    include_positive=True,
    include_negative=False,
    include_boundary=False,
    include_combination=False
)
```

### 2. 完整回归测试
```python
test_cases = generator.generate_all_cases(
    include_positive=True,
    include_negative=True,
    include_boundary=True,
    include_combination=True
)
```

### 3. 仅边界值测试
```python
test_cases = generator.generate_all_cases(
    include_positive=False,
    include_negative=False,
    include_boundary=True,
    include_combination=False
)
```

## 🛠️ 集成到自动化测试

### 与 pytest 集成

```python
import pytest
from app.tools.toolbox.test_case_generator import TestCaseGenerator

@pytest.fixture
def test_cases():
    generator = TestCaseGenerator(base_params, constraints)
    return generator.generate_all_cases()

@pytest.mark.parametrize("case", test_cases)
def test_api(case):
    response = requests.post("/api/register", json=case.params)
    
    if case.case_type.value == "positive":
        assert response.status_code == 200
    else:
        assert response.status_code in [400, 422]
```

### 与 unittest 集成

```python
import unittest

class TestUserRegister(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generator = TestCaseGenerator(base_params, constraints)
        cls.test_cases = generator.generate_all_cases()
    
    def test_all_cases(self):
        for case in self.test_cases:
            with self.subTest(case=case.case_id):
                response = call_api(case.params)
                self.validate_response(response, case)
```

## 📝 注意事项

1. **唯一性约束测试**：需要先创建重复数据才能测试唯一性冲突
2. **组合爆炸**：参数过多时限制 `combination_depth` 和字段数量
3. **业务规则**：生成器不理解复杂业务规则，需手动补充
4. **数据依赖**：某些用例可能需要预置数据
5. **执行顺序**：某些负向用例可能影响后续测试

## 🎓 最佳实践

1. **参数分组**：将相关参数分组，分别生成用例
2. **优先级标记**：为约束添加优先级，控制生成数量
3. **定期更新**：接口变更时及时更新约束定义
4. **结合手工**：自动生成 + 手工补充业务场景
5. **持续优化**：根据缺陷反馈调整生成策略

## 📞 运行示例

```bash
# 进入项目目录
cd app/tools/toolbox

# 运行示例
python test_case_generator_example.py
```

会生成：
- `test_cases_user_register.json` - 用户注册接口用例（JSON格式）
- `test_cases_user_register.md` - 用户注册接口用例（Markdown格式）
- `test_cases_create_project.json` - 创建项目接口用例（JSON格式）

## 🤝 扩展开发

如需添加新的测试策略，可以继承 `TestCaseGenerator` 类：

```python
class CustomTestCaseGenerator(TestCaseGenerator):
    def _generate_custom_cases(self):
        """自定义测试用例生成逻辑"""
        # 实现你的逻辑
        pass
```

---

**作者**: Kiro AI Assistant  
**版本**: 1.0.0  
**更新日期**: 2024-01-01
