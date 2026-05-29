"""
接口测试用例自动生成器
支持等价类划分、边界值分析、正交实验等测试策略
"""
import copy
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum


class FieldType(Enum):
    """字段类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"


class TestCaseType(Enum):
    """测试用例类型"""
    POSITIVE = "positive"  # 正向用例
    NEGATIVE = "negative"  # 负向用例
    BOUNDARY = "boundary"  # 边界值用例
    COMBINATION = "combination"  # 组合用例


class FieldConstraint:
    """字段约束定义"""
    
    def __init__(
        self,
        field_name: str,
        field_type: FieldType,
        required: bool = True,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        pattern: Optional[str] = None,
        enum_values: Optional[List[Any]] = None,
        unique: bool = False,
        description: str = ""
    ):
        self.field_name = field_name
        self.field_type = field_type
        self.required = required
        self.min_length = min_length
        self.max_length = max_length
        self.min_value = min_value
        self.max_value = max_value
        self.pattern = pattern
        self.enum_values = enum_values
        self.unique = unique
        self.description = description


class TestCase:
    """测试用例数据结构"""
    
    def __init__(
        self,
        case_id: str,
        case_type: TestCaseType,
        description: str,
        params: Dict[str, Any],
        expected_result: str,
        test_point: str
    ):
        self.case_id = case_id
        self.case_type = case_type
        self.description = description
        self.params = params
        self.expected_result = expected_result
        self.test_point = test_point
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "case_id": self.case_id,
            "case_type": self.case_type.value,
            "description": self.description,
            "params": self.params,
            "expected_result": self.expected_result,
            "test_point": self.test_point
        }


class TestCaseGenerator:
    """测试用例生成器"""
    
    def __init__(self, base_params: Dict[str, Any], constraints: List[FieldConstraint]):
        """
        初始化生成器
        
        Args:
            base_params: 基准正确参数（所有字段的有效值）
            constraints: 字段约束列表
        """
        self.base_params = base_params
        self.constraints = {c.field_name: c for c in constraints}
        self.case_counter = 0
        self.generated_cases: List[TestCase] = []
    
    def generate_all_cases(
        self,
        include_positive: bool = True,
        include_negative: bool = True,
        include_boundary: bool = True,
        include_combination: bool = True,
        combination_depth: int = 2
    ) -> List[TestCase]:
        """
        生成所有测试用例
        
        Args:
            include_positive: 是否包含正向用例
            include_negative: 是否包含负向用例
            include_boundary: 是否包含边界值用例
            include_combination: 是否包含组合用例
            combination_depth: 组合测试深度（2=两两组合）
        
        Returns:
            测试用例列表
        """
        self.generated_cases = []
        self.case_counter = 0
        
        # 1. 正向用例
        if include_positive:
            self._generate_positive_cases()
        
        # 2. 必传参数负向用例
        if include_negative:
            self._generate_required_field_negative_cases()
        
        # 3. 边界值用例
        if include_boundary:
            self._generate_boundary_cases()
        
        # 4. 类型错误用例
        if include_negative:
            self._generate_type_error_cases()
        
        # 5. 唯一性约束用例
        if include_negative:
            self._generate_unique_constraint_cases()
        
        # 6. 组合测试用例（正交）
        if include_combination:
            self._generate_combination_cases(combination_depth)
        
        return self.generated_cases
    
    def _generate_positive_cases(self):
        """生成正向用例"""
        # 用例1: 最小必传参数集
        required_params = {
            k: v for k, v in self.base_params.items()
            if self.constraints.get(k) and self.constraints[k].required
        }
        self._add_case(
            TestCaseType.POSITIVE,
            "最小必传参数集",
            required_params,
            "成功",
            "验证仅传必传参数时接口正常"
        )
        
        # 用例2: 全参数正常值
        self._add_case(
            TestCaseType.POSITIVE,
            "全参数正常值",
            copy.deepcopy(self.base_params),
            "成功",
            "验证传入所有参数时接口正常"
        )
    
    def _generate_required_field_negative_cases(self):
        """生成必传参数负向用例"""
        for field_name, constraint in self.constraints.items():
            if not constraint.required:
                continue
            
            # 缺失必传参数
            params = copy.deepcopy(self.base_params)
            params.pop(field_name, None)
            self._add_case(
                TestCaseType.NEGATIVE,
                f"缺失必传参数: {field_name}",
                params,
                "失败: 参数缺失",
                f"验证缺少必传参数 {field_name} 时返回错误"
            )
            
            # 必传参数为None
            params = copy.deepcopy(self.base_params)
            params[field_name] = None
            self._add_case(
                TestCaseType.NEGATIVE,
                f"必传参数为None: {field_name}",
                params,
                "失败: 参数为空",
                f"验证必传参数 {field_name} 为None时返回错误"
            )
            
            # 字符串类型的空值测试
            if constraint.field_type == FieldType.STRING:
                params = copy.deepcopy(self.base_params)
                params[field_name] = ""
                self._add_case(
                    TestCaseType.NEGATIVE,
                    f"必传参数为空字符串: {field_name}",
                    params,
                    "失败: 参数为空",
                    f"验证必传参数 {field_name} 为空字符串时返回错误"
                )
    
    def _generate_boundary_cases(self):
        """生成边界值用例"""
        for field_name, constraint in self.constraints.items():
            if field_name not in self.base_params:
                continue
            
            # 字符串长度边界
            if constraint.field_type == FieldType.STRING:
                if constraint.min_length is not None:
                    # 最小长度-1（负向）
                    if constraint.min_length > 0:
                        params = copy.deepcopy(self.base_params)
                        params[field_name] = "a" * (constraint.min_length - 1)
                        self._add_case(
                            TestCaseType.BOUNDARY,
                            f"{field_name} 长度小于最小值",
                            params,
                            "失败: 长度不足",
                            f"验证 {field_name} 长度小于 {constraint.min_length} 时返回错误"
                        )
                    
                    # 最小长度（正向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = "a" * constraint.min_length
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 长度等于最小值",
                        params,
                        "成功",
                        f"验证 {field_name} 长度等于 {constraint.min_length} 时正常"
                    )
                
                if constraint.max_length is not None:
                    # 最大长度（正向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = "a" * constraint.max_length
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 长度等于最大值",
                        params,
                        "成功",
                        f"验证 {field_name} 长度等于 {constraint.max_length} 时正常"
                    )
                    
                    # 最大长度+1（负向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = "a" * (constraint.max_length + 1)
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 长度大于最大值",
                        params,
                        "失败: 长度超限",
                        f"验证 {field_name} 长度大于 {constraint.max_length} 时返回错误"
                    )
            
            # 数值边界
            if constraint.field_type in [FieldType.INTEGER, FieldType.FLOAT]:
                if constraint.min_value is not None:
                    # 最小值-1（负向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = constraint.min_value - 1
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 小于最小值",
                        params,
                        "失败: 数值过小",
                        f"验证 {field_name} 小于 {constraint.min_value} 时返回错误"
                    )
                    
                    # 最小值（正向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = constraint.min_value
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 等于最小值",
                        params,
                        "成功",
                        f"验证 {field_name} 等于 {constraint.min_value} 时正常"
                    )
                
                if constraint.max_value is not None:
                    # 最大值（正向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = constraint.max_value
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 等于最大值",
                        params,
                        "成功",
                        f"验证 {field_name} 等于 {constraint.max_value} 时正常"
                    )
                    
                    # 最大值+1（负向）
                    params = copy.deepcopy(self.base_params)
                    params[field_name] = constraint.max_value + 1
                    self._add_case(
                        TestCaseType.BOUNDARY,
                        f"{field_name} 大于最大值",
                        params,
                        "失败: 数值过大",
                        f"验证 {field_name} 大于 {constraint.max_value} 时返回错误"
                    )
    
    def _generate_type_error_cases(self):
        """生成类型错误用例"""
        type_error_values = {
            FieldType.STRING: [123, True, [], {}],
            FieldType.INTEGER: ["abc", True, [], {}],
            FieldType.FLOAT: ["abc", [], {}],
            FieldType.BOOLEAN: ["true", 1, []],
            FieldType.ARRAY: ["abc", 123, {}],
            FieldType.OBJECT: ["abc", 123, []],
        }
        
        for field_name, constraint in self.constraints.items():
            if field_name not in self.base_params:
                continue
            
            error_values = type_error_values.get(constraint.field_type, [])
            for error_value in error_values[:2]:  # 每种类型取2个错误值
                params = copy.deepcopy(self.base_params)
                params[field_name] = error_value
                self._add_case(
                    TestCaseType.NEGATIVE,
                    f"{field_name} 类型错误: {type(error_value).__name__}",
                    params,
                    "失败: 类型错误",
                    f"验证 {field_name} 传入 {type(error_value).__name__} 类型时返回错误"
                )
    
    def _generate_unique_constraint_cases(self):
        """生成唯一性约束用例"""
        for field_name, constraint in self.constraints.items():
            if constraint.unique and field_name in self.base_params:
                params = copy.deepcopy(self.base_params)
                self._add_case(
                    TestCaseType.NEGATIVE,
                    f"{field_name} 重复值测试",
                    params,
                    "失败: 字段值已存在",
                    f"验证 {field_name} 使用已存在的值时返回错误（需先创建重复数据）"
                )
    
    def _generate_combination_cases(self, depth: int = 2):
        """
        生成组合测试用例（简化版正交）
        
        Args:
            depth: 组合深度，2表示两两组合
        """
        # 选择高优先级字段进行组合测试
        priority_fields = [
            field_name for field_name, constraint in self.constraints.items()
            if constraint.required or constraint.unique
        ]
        
        if len(priority_fields) < depth:
            return
        
        # 为每个字段准备等价类值
        field_values = {}
        for field_name in priority_fields[:5]:  # 限制字段数量避免组合爆炸
            constraint = self.constraints[field_name]
            values = self._get_equivalence_class_values(field_name, constraint)
            field_values[field_name] = values
        
        # 生成两两组合（Pairwise）
        if depth == 2 and len(field_values) >= 2:
            field_names = list(field_values.keys())
            for i in range(len(field_names)):
                for j in range(i + 1, min(i + 3, len(field_names))):  # 限制组合数量
                    field1, field2 = field_names[i], field_names[j]
                    for val1 in field_values[field1][:2]:  # 每个字段取2个值
                        for val2 in field_values[field2][:2]:
                            params = copy.deepcopy(self.base_params)
                            params[field1] = val1
                            params[field2] = val2
                            self._add_case(
                                TestCaseType.COMBINATION,
                                f"组合测试: {field1}+{field2}",
                                params,
                                "成功或失败（取决于值）",
                                f"验证 {field1} 和 {field2} 的组合场景"
                            )
    
    def _get_equivalence_class_values(self, field_name: str, constraint: FieldConstraint) -> List[Any]:
        """获取字段的等价类值"""
        values = []
        
        if constraint.enum_values:
            return constraint.enum_values[:3]  # 枚举值取前3个
        
        if constraint.field_type == FieldType.STRING:
            values.append(self.base_params.get(field_name, "test"))
            if constraint.min_length:
                values.append("a" * constraint.min_length)
            if constraint.max_length:
                values.append("a" * constraint.max_length)
        
        elif constraint.field_type in [FieldType.INTEGER, FieldType.FLOAT]:
            values.append(self.base_params.get(field_name, 1))
            if constraint.min_value is not None:
                values.append(constraint.min_value)
            if constraint.max_value is not None:
                values.append(constraint.max_value)
        
        elif constraint.field_type == FieldType.BOOLEAN:
            values = [True, False]
        
        return values[:3]  # 最多返回3个等价类值
    
    def _add_case(
        self,
        case_type: TestCaseType,
        description: str,
        params: Dict[str, Any],
        expected_result: str,
        test_point: str
    ):
        """添加测试用例"""
        self.case_counter += 1
        case = TestCase(
            case_id=f"TC_{self.case_counter:03d}",
            case_type=case_type,
            description=description,
            params=params,
            expected_result=expected_result,
            test_point=test_point
        )
        self.generated_cases.append(case)
    
    def export_to_dict(self) -> List[Dict]:
        """导出为字典列表"""
        return [case.to_dict() for case in self.generated_cases]
    
    def export_to_markdown(self) -> str:
        """导出为Markdown格式"""
        lines = ["# 自动生成的测试用例\n"]
        lines.append(f"总计: {len(self.generated_cases)} 个用例\n")
        
        # 按类型分组
        by_type = {}
        for case in self.generated_cases:
            case_type = case.case_type.value
            if case_type not in by_type:
                by_type[case_type] = []
            by_type[case_type].append(case)
        
        for case_type, cases in by_type.items():
            lines.append(f"\n## {case_type.upper()} ({len(cases)}个)\n")
            lines.append("| 用例ID | 描述 | 测试点 | 预期结果 |")
            lines.append("|--------|------|--------|----------|")
            for case in cases:
                lines.append(
                    f"| {case.case_id} | {case.description} | "
                    f"{case.test_point} | {case.expected_result} |"
                )
        
        return "\n".join(lines)
    
    def get_statistics(self) -> Dict[str, int]:
        """获取用例统计信息"""
        stats = {
            "total": len(self.generated_cases),
            "positive": 0,
            "negative": 0,
            "boundary": 0,
            "combination": 0
        }
        
        for case in self.generated_cases:
            stats[case.case_type.value] += 1
        
        return stats
    
    def save_to_folder(
        self,
        folder_path: str = "test_cases",
        file_prefix: str = "test_case",
        formats: List[str] = None
    ) -> Dict[str, str]:
        """
        保存测试用例到指定文件夹，使用时间戳命名
        
        Args:
            folder_path: 保存文件夹路径（相对或绝对）
            file_prefix: 文件名前缀，默认为 "test_case"
            formats: 保存格式列表，支持 ["json", "markdown"]，默认两种都保存
        
        Returns:
            保存的文件路径字典，如 {"json": "path/to/file.json", "markdown": "path/to/file.md"}
        
        Example:
            >>> generator = TestCaseGenerator(base_params, constraints)
            >>> test_cases = generator.generate_all_cases()
            >>> files = generator.save_to_folder(
            ...     folder_path="test_cases",
            ...     file_prefix="user_register",
            ...     formats=["json", "markdown"]
            ... )
            >>> print(files)
            {'json': 'test_cases/user_register_20240115_143022.json', 
             'markdown': 'test_cases/user_register_20240115_143022.md'}
        """
        import json
        
        if formats is None:
            formats = ["json", "markdown"]
        
        # 创建文件夹（如果不存在）
        os.makedirs(folder_path, exist_ok=True)
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 生成文件名
        base_filename = f"{file_prefix}_{timestamp}"
        
        saved_files = {}
        
        # 保存 JSON 格式
        if "json" in formats:
            json_filename = f"{base_filename}.json"
            json_filepath = os.path.join(folder_path, json_filename)
            
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(self.export_to_dict(), f, ensure_ascii=False, indent=2)
            
            saved_files["json"] = json_filepath
        
        # 保存 Markdown 格式
        if "markdown" in formats:
            md_filename = f"{base_filename}.md"
            md_filepath = os.path.join(folder_path, md_filename)
            
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(self.export_to_markdown())
            
            saved_files["markdown"] = md_filepath
        
        return saved_files
