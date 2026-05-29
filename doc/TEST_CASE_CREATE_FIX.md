# 测试用例创建接口修复说明

## 问题描述
创建测试用例时报错："模块ID不能为空"

### 错误请求示例
```bash
curl "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "id": null,
    "title": "测试用例01",
    "description": "描述",
    "priority": "P2",
    "case_type": "功能",
    "case_status": "草稿",
    "folder_id": 16,
    "precondition": "前置条件",
    "steps": "测试步骤",
    "expected_result": "预期结果",
    "project_id": 5
  }'
```

### 错误响应
```json
{
  "error": "模块ID不能为空"
}
```

## 根本原因
后端代码中 `module_id` 字段被设置为必填，但前端已经改用 `folder_id` 来管理测试用例的目录结构。

### 原代码问题
```python
@test_case_bp.route("", methods=["POST"])
@require_permission("test_case:create")
def create_test_case():
    """创建测试用例。"""
    data = request.get_json()

    if not data.get("title"):
        return jsonify({"error": "用例标题不能为空"}), 400
    if not data.get("project_id"):
        return jsonify({"error": "项目ID不能为空"}), 400
    if not data.get("module_id"):  # ❌ 强制要求 module_id
        return jsonify({"error": "模块ID不能为空"}), 400
```

## 解决方案

### 1. 修改创建接口 (POST /api/test-cases)

**修改前：**
- `module_id` 必填
- 不验证 `folder_id`

**修改后：**
- `module_id` 改为可选
- 添加 `folder_id` 验证（如果提供）

```python
@test_case_bp.route("", methods=["POST"])
@require_permission("test_case:create")
def create_test_case():
    """创建测试用例。"""
    data = request.get_json()

    if not data.get("title"):
        return jsonify({"error": "用例标题不能为空"}), 400
    if not data.get("project_id"):
        return jsonify({"error": "项目ID不能为空"}), 400

    project = Project.query.get(data["project_id"])
    if not project:
        return jsonify({"error": "项目不存在"}), 404

    # module_id 改为可选
    module_id = data.get("module_id")
    if module_id:
        module = Module.query.get(module_id)
        if not module:
            return jsonify({"error": "模块不存在"}), 404
        if module.project_id != data["project_id"]:
            return jsonify({"error": "模块不属于该项目"}), 400

    # 验证 folder_id（如果提供）
    folder_id = data.get("folder_id")
    if folder_id:
        folder = ApiFolder.query.get(folder_id)
        if not folder:
            return jsonify({"error": "目录不存在"}), 404
        if folder.project_id != data["project_id"]:
            return jsonify({"error": "目录不属于该项目"}), 400

    case_no = generate_case_no(data["project_id"])

    test_case = TestCaseManagement(
        case_no=case_no,
        title=data["title"],
        description=data.get("description"),
        precondition=data.get("precondition"),
        steps=data.get("steps"),
        expected_result=data.get("expected_result"),
        project_id=data["project_id"],
        module_id=module_id,  # 可选
        folder_id=folder_id,  # 可选
        priority=data.get("priority", "P2"),
        case_type=data.get("case_type", "功能"),
        case_status=data.get("case_status", "草稿"),
        status=data.get("status", 1)
    )
    # ... 后续代码
```

### 2. 修改更新接口 (PUT /api/test-cases/<case_id>)

**修改前：**
- 只验证 `module_id` 存在性
- `folder_id` 直接赋值，不验证

**修改后：**
- 验证 `module_id`（如果提供且不为空）
- 验证 `folder_id`（如果提供且不为空）

```python
@test_case_bp.route("/<int:case_id>", methods=["PUT"])
@require_permission("test_case:update")
def update_test_case(case_id):
    """更新测试用例。"""
    test_case = TestCaseManagement.query.get(case_id)
    if not test_case:
        return jsonify({"error": "测试用例不存在"}), 404

    data = request.get_json()

    # 验证 module_id（如果提供）
    if "module_id" in data and data["module_id"]:
        module = Module.query.get(data["module_id"])
        if not module:
            return jsonify({"error": "模块不存在"}), 404
        if module.project_id != test_case.project_id:
            return jsonify({"error": "模块不属于该项目"}), 400
        test_case.module_id = data["module_id"]

    # 验证 folder_id（如果提供）
    if "folder_id" in data:
        if data["folder_id"]:
            folder = ApiFolder.query.get(data["folder_id"])
            if not folder:
                return jsonify({"error": "目录不存在"}), 404
            if folder.project_id != test_case.project_id:
                return jsonify({"error": "目录不属于该项目"}), 400
        test_case.folder_id = data["folder_id"]

    # 更新其他字段
    if "title" in data:
        test_case.title = data["title"]
    # ... 其他字段
```

## 修改文件
- `app/routes/test_case.py`
  - 修改 `create_test_case()` 函数
  - 修改 `update_test_case()` 函数

## 数据模型支持

### TestCaseManagement 模型
```python
class TestCaseManagement(db.Model):
    __tablename__ = 'test_case_management'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, nullable=False)
    module_id = db.Column(db.Integer, nullable=True)  # 可选
    folder_id = db.Column(db.Integer, nullable=True)  # 可选
    # ... 其他字段
```

两个字段都是可选的，支持以下场景：
1. 只使用 `module_id`（旧方式）
2. 只使用 `folder_id`（新方式）
3. 同时使用两者（兼容模式）
4. 都不使用（未分类）

## 验证逻辑

### 创建时
1. ✅ 验证 `title` 必填
2. ✅ 验证 `project_id` 必填且存在
3. ✅ 验证 `module_id`（如果提供）存在且属于该项目
4. ✅ 验证 `folder_id`（如果提供）存在且属于该项目

### 更新时
1. ✅ 验证用例存在
2. ✅ 验证 `module_id`（如果提供且不为空）存在且属于该项目
3. ✅ 验证 `folder_id`（如果提供且不为空）存在且属于该项目
4. ✅ 允许设置为 `null`（移到未分类）

## 测试用例

### 1. 创建用例（只使用 folder_id）
```bash
curl -X POST "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "title": "测试用例01",
    "description": "描述",
    "priority": "P2",
    "case_type": "功能",
    "case_status": "草稿",
    "folder_id": 16,
    "project_id": 5
  }'
```

**预期结果：** 成功创建，返回 200

### 2. 创建用例（不指定 folder_id 和 module_id）
```bash
curl -X POST "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "title": "未分类用例",
    "project_id": 5
  }'
```

**预期结果：** 成功创建，用例显示在"未分类"节点下

### 3. 创建用例（同时指定 folder_id 和 module_id）
```bash
curl -X POST "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "title": "兼容模式用例",
    "folder_id": 16,
    "module_id": 3,
    "project_id": 5
  }'
```

**预期结果：** 成功创建，同时关联目录和模块

### 4. 创建用例（folder_id 不存在）
```bash
curl -X POST "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "title": "测试用例",
    "folder_id": 9999,
    "project_id": 5
  }'
```

**预期结果：** 返回 404，错误信息："目录不存在"

### 5. 更新用例（移动到其他目录）
```bash
curl -X PUT "http://localhost:12048/api/test-cases/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "folder_id": 17
  }'
```

**预期结果：** 成功更新，用例移动到新目录

### 6. 更新用例（移到未分类）
```bash
curl -X PUT "http://localhost:12048/api/test-cases/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "folder_id": null
  }'
```

**预期结果：** 成功更新，用例移动到"未分类"

## 兼容性说明

### 向后兼容
- ✅ 旧的使用 `module_id` 的代码仍然可以工作
- ✅ 可以同时使用 `module_id` 和 `folder_id`
- ✅ 现有数据不需要迁移

### 推荐使用方式
- 新功能使用 `folder_id`
- 逐步迁移旧数据到 `folder_id`
- 最终可以废弃 `module_id`

## 注意事项

1. **数据一致性**：如果同时使用 `module_id` 和 `folder_id`，需要确保它们的关系合理
2. **权限控制**：确保用户有权限访问指定的目录
3. **级联删除**：删除目录时需要处理其下的用例
4. **未分类处理**：`folder_id` 和 `module_id` 都为 `null` 的用例会显示在"未分类"节点

## 后续优化建议

1. 添加数据迁移脚本，将 `module_id` 数据迁移到 `folder_id`
2. 在前端完全移除 `module_id` 的使用
3. 考虑在数据库层面废弃 `module_id` 字段
4. 添加更完善的验证规则和错误提示
