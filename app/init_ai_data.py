"""
初始化 AI 内置提示词模板数据。

为平台预置三个内置提示词模板：测试用例生成、缺陷分析、需求评审。
仅在模板不存在时插入，避免重复创建。

作者: yandc
创建时间: 2026-02-10
"""
from app.models.base import db
from app.models.ai_prompt import AIPromptTemplate


# 内置模板定义
BUILTIN_TEMPLATES = [
    {
        "name": "测试用例生成",
        "scene": "test_case_generation",
        "description": "根据需求描述自动生成测试用例",
        "system_prompt": (
            "你是一位资深的软件测试专家，擅长根据需求描述设计全面的测试用例。"
            "你需要考虑正常流程、边界条件、异常场景和安全性测试。"
            "请以结构化的格式输出测试用例，包含用例编号、用例标题、前置条件、测试步骤、预期结果和优先级。"
        ),
        "user_prompt_template": "请根据以下需求描述生成测试用例：\n\n{requirement}",
    },
    {
        "name": "缺陷分析",
        "scene": "bug_analysis",
        "description": "分析缺陷信息并提供修复建议",
        "system_prompt": (
            "你是一位经验丰富的 QA 专家，擅长分析软件缺陷的根本原因并提供修复建议。"
            "你需要从缺陷描述中识别可能的原因、影响范围，并给出具体的修复方案和预防措施。"
            "请以清晰的结构输出分析结果，包含缺陷分类、严重程度评估、根因分析、修复建议和回归测试建议。"
        ),
        "user_prompt_template": "请分析以下缺陷信息并提供修复建议：\n\n{bug_description}",
    },
    {
        "name": "需求评审",
        "scene": "requirement_review",
        "description": "评审需求文档并提出改进建议",
        "system_prompt": (
            "你是一位专业的需求分析师，擅长评审需求文档的完整性、一致性和可测试性。"
            "你需要检查需求是否存在歧义、遗漏、冲突或不可测试的描述，并提出改进建议。"
            "请以结构化的格式输出评审结果，包含需求完整性评估、潜在问题列表、改进建议和测试可行性分析。"
        ),
        "user_prompt_template": "请评审以下需求内容并提出改进建议：\n\n{requirement_content}",
    },
]


def init_ai_templates():
    """
    初始化内置 AI 提示词模板。

    检查每个内置模板是否已存在（通过 scene 标识判断），
    仅在模板不存在时插入，避免重复创建。
    """
    created_count = 0

    for template_data in BUILTIN_TEMPLATES:
        existing = AIPromptTemplate.query.filter_by(
            scene=template_data["scene"]
        ).first()

        if existing:
            print(f"  模板已存在，跳过: {template_data['name']} ({template_data['scene']})")
            continue

        template = AIPromptTemplate(
            name=template_data["name"],
            scene=template_data["scene"],
            description=template_data["description"],
            system_prompt=template_data["system_prompt"],
            user_prompt_template=template_data["user_prompt_template"],
            is_builtin=True,
        )
        db.session.add(template)
        created_count += 1
        print(f"  创建内置模板: {template_data['name']} ({template_data['scene']})")

    if created_count > 0:
        db.session.commit()
        print(f"成功创建 {created_count} 个内置模板")
    else:
        print("所有内置模板已存在，无需初始化")


if __name__ == "__main__":
    from app.flask_app import create_app

    app = create_app()
    with app.app_context():
        print("开始初始化 AI 内置提示词模板...")
        init_ai_templates()
        print("初始化完成！")
