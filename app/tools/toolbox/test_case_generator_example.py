"""
测试用例生成器使用示例
"""
import json
from app.tools.toolbox.test_case_generator import (
    TestCaseGenerator,
    FieldConstraint,
    FieldType
)


def example_user_register_api():
    """示例：用户注册接口测试用例生成"""
    
    # 1. 定义基准正确参数（所有字段的有效值）
    base_params = {
        "username": "testuser123",
        "password": "Pass@123456",
        "email": "test@example.com",
        "phone": "13800138000",
        "age": 25,
        "gender": "male",
        "nickname": "测试用户",
        "bio": "这是个人简介",
        "agree_terms": True
    }
    
    # 2. 定义字段约束
    constraints = [
        FieldConstraint(
            field_name="username",
            field_type=FieldType.STRING,
            required=True,
            min_length=3,
            max_length=20,
            unique=True,
            description="用户名，必须唯一"
        ),
        FieldConstraint(
            field_name="password",
            field_type=FieldType.STRING,
            required=True,
            min_length=6,
            max_length=50,
            description="密码"
        ),
        FieldConstraint(
            field_name="email",
            field_type=FieldType.EMAIL,
            required=True,
            unique=True,
            description="邮箱，必须唯一"
        ),
        FieldConstraint(
            field_name="phone",
            field_type=FieldType.PHONE,
            required=False,
            min_length=11,
            max_length=11,
            description="手机号"
        ),
        FieldConstraint(
            field_name="age",
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=150,
            description="年龄"
        ),
        FieldConstraint(
            field_name="gender",
            field_type=FieldType.STRING,
            required=False,
            enum_values=["male", "female", "other"],
            description="性别"
        ),
        FieldConstraint(
            field_name="nickname",
            field_type=FieldType.STRING,
            required=False,
            max_length=50,
            description="昵称"
        ),
        FieldConstraint(
            field_name="bio",
            field_type=FieldType.STRING,
            required=False,
            max_length=200,
            description="个人简介"
        ),
        FieldConstraint(
            field_name="agree_terms",
            field_type=FieldType.BOOLEAN,
            required=True,
            description="是否同意条款"
        )
    ]
    
    # 3. 创建生成器并生成用例
    generator = TestCaseGenerator(base_params, constraints)
    
    test_cases = generator.generate_all_cases(
        include_positive=True,
        include_negative=True,
        include_boundary=True,
        include_combination=True,
        combination_depth=2
    )
    
    # 4. 输出结果
    print("=" * 80)
    print("用户注册接口测试用例生成结果")
    print("=" * 80)
    
    # 统计信息
    stats = generator.get_statistics()
    print(f"\n📊 用例统计:")
    print(f"  总计: {stats['total']} 个")
    print(f"  正向用例: {stats['positive']} 个")
    print(f"  负向用例: {stats['negative']} 个")
    print(f"  边界值用例: {stats['boundary']} 个")
    print(f"  组合用例: {stats['combination']} 个")
    
    # 展示部分用例
    print("\n📝 用例详情（前10个）:")
    print("-" * 80)
    for i, case in enumerate(test_cases[:10], 1):
        print(f"\n[{i}] {case.case_id} - {case.description}")
        print(f"    类型: {case.case_type.value}")
        print(f"    测试点: {case.test_point}")
        print(f"    参数: {json.dumps(case.params, ensure_ascii=False, indent=6)}")
        print(f"    预期: {case.expected_result}")
    
    # 保存到文件夹（使用时间戳命名）
    saved_files = generator.save_to_folder(
        folder_path="test_cases",
        file_prefix="user_register",
        formats=["json", "markdown"]
    )
    
    print(f"\n✅ 文件已保存:")
    for format_type, filepath in saved_files.items():
        print(f"  {format_type}: {filepath}")
    
    return test_cases


def example_create_project_api():
    """示例：创建项目接口测试用例生成"""
    
    base_params = {
        "UserID": 7025,
        "AccountItem": "test-AccountItem",
        "UnitPrice": 641.09,
        "Description": "desc",
        "AccountItemTypeID": "",
        "TagID": 3,
        "Category": "AIR",
        "UOM": "877884578",
        "CountByID": 10325,
        "BillToID": 0,
        "ValueType": 1,
        "PartsCategoryID": 2,
        "TriggerPointID": 30,
        "AccountingItemID": 51,
        "AutoBillingForWMS": True,
        "Hidden": True,
        "IsOnlyOneTime": False,
        "ChargeCode": "9523",
        "ChargeName": "test-ChargeName",
        "ChargeType": "sed nulla minim",
        "IsActive": True,
        "VendorIDs": []
    }
    
    constraints = [
        FieldConstraint(
            field_name="name",
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=100,
            unique=True,
            description="项目名称"
        ),
        FieldConstraint(
            field_name="description",
            field_type=FieldType.STRING,
            required=False,
            max_length=500,
            description="项目描述"
        ),
        FieldConstraint(
            field_name="project_type",
            field_type=FieldType.STRING,
            required=True,
            enum_values=["web", "mobile", "desktop", "api"],
            description="项目类型"
        ),
        FieldConstraint(
            field_name="priority",
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=5,
            description="优先级"
        ),
        FieldConstraint(
            field_name="start_date",
            field_type=FieldType.DATE,
            required=False,
            description="开始日期"
        ),
        FieldConstraint(
            field_name="end_date",
            field_type=FieldType.DATE,
            required=False,
            description="结束日期"
        ),
        FieldConstraint(
            field_name="budget",
            field_type=FieldType.FLOAT,
            required=False,
            min_value=0,
            max_value=9999999.99,
            description="预算"
        ),
        FieldConstraint(
            field_name="members",
            field_type=FieldType.ARRAY,
            required=False,
            description="成员ID列表"
        ),
        FieldConstraint(
            field_name="tags",
            field_type=FieldType.ARRAY,
            required=False,
            description="标签列表"
        ),
        FieldConstraint(
            field_name="is_public",
            field_type=FieldType.BOOLEAN,
            required=False,
            description="是否公开"
        )
    ]
    
    generator = TestCaseGenerator(base_params, constraints)
    test_cases = generator.generate_all_cases()
    
    print("\n" + "=" * 80)
    print("创建项目接口测试用例生成结果")
    print("=" * 80)
    
    stats = generator.get_statistics()
    print(f"\n📊 用例统计: 总计 {stats['total']} 个")
    
    # 保存到文件夹
    saved_files = generator.save_to_folder(
        folder_path="test_cases",
        file_prefix="create_project",
        formats=["json", "markdown"]
    )
    
    print(f"\n✅ 文件已保存:")
    for format_type, filepath in saved_files.items():
        print(f"  {format_type}: {filepath}")
    
    return test_cases


def example_minimal_usage():
    """最简使用示例"""
    
    # 最简配置
    base_params = {"id": 1, "name": "test"}
    
    constraints = [
        FieldConstraint("id", FieldType.INTEGER, required=True, min_value=1),
        FieldConstraint("name", FieldType.STRING, required=True, min_length=1, max_length=50)
    ]
    
    generator = TestCaseGenerator(base_params, constraints)
    test_cases = generator.generate_all_cases()
    
    print("\n" + "=" * 80)
    print("最简示例")
    print("=" * 80)
    print(f"生成了 {len(test_cases)} 个测试用例")
    
    for case in test_cases[:5]:
        print(f"  - {case.description}")


if __name__ == "__main__":
    # 运行示例
    print("🚀 测试用例生成器示例\n")
    
    # 示例1: 用户注册接口
    example_user_register_api()
    
    # 示例2: 创建项目接口
    example_create_project_api()
    
    # 示例3: 最简使用
    example_minimal_usage()
    
    print("\n" + "=" * 80)
    print("✨ 所有示例运行完成！")
    print("=" * 80)
