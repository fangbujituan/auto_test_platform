# 权限问题修复总结

## 问题描述

前端访问测试用例功能时，后端返回 403 错误：
```
GET /api/modules/tree?project_id=5 HTTP/1.1" 403
GET /api/test-cases?project_id=5&page=1&per_page=20 HTTP/1.1" 403
```

## 根本原因

1. **权限名称不匹配**：
   - 测试用例 API 使用 `test_case:*` 权限（如 `test_case:read`）
   - 模块 API 使用 `module:*` 权限（如 `module:read`）
   - 但权限系统中只定义了 `case:*` 和 `execute:*` 权限

2. **缺少权限定义**：
   - 数据库中没有 `module:*` 相关权限
   - 数据库中没有 `test_case:*` 相关权限

## 修复方案

### 1. 更新权限初始化脚本

修改 `app/init_permission.py`，添加缺失的权限：

```python
# 模块权限
{"name": "module:read", "resource": "module", "action": "read", "description": "查看模块"},
{"name": "module:create", "resource": "module", "action": "create", "description": "创建模块"},
{"name": "module:update", "resource": "module", "action": "update", "description": "编辑模块"},
{"name": "module:delete", "resource": "module", "action": "delete", "description": "删除模块"},

# 测试用例权限
{"name": "test_case:read", "resource": "test_case", "action": "read", "description": "查看测试用例"},
{"name": "test_case:create", "resource": "test_case", "action": "create", "description": "创建测试用例"},
{"name": "test_case:update", "resource": "test_case", "action": "update", "description": "编辑测试用例"},
{"name": "test_case:delete", "resource": "test_case", "action": "delete", "description": "删除测试用例"},
```

### 2. 运行权限更新脚本

创建并运行 `update_permissions.py` 脚本：

```bash
python update_permissions.py
```

该脚本会：
- 添加 8 个新权限（4个模块权限 + 4个测试用例权限）
- 更新所有角色的权限配置
- admin 和 owner 角色拥有所有权限
- member 角色拥有读写权限
- viewer 角色只有读权限

## 验证结果

运行 `python test_permission_fix.py` 验证修复：

### admin 用户（项目成员）
✅ 可以访问模块树 API
✅ 可以访问测试用例列表 API

### test 用户（非项目成员）
❌ 无法访问（符合预期，因为不是项目成员）

## 权限系统统计

修复后的权限系统：
- **总权限数**: 27 个
- **总角色数**: 4 个（admin, owner, member, viewer）

## 注意事项

1. **用户必须是项目成员**才能访问项目相关的 API
2. **权限检查逻辑**：
   - 先检查用户是否登录
   - 再检查用户是否有对应的权限
   - 权限通过用户的项目成员角色来判断

3. **如何添加用户到项目**：
   ```python
   # 使用项目成员管理 API
   POST /api/projects/{project_id}/members
   {
       "user_id": 4,
       "role_name": "member"
   }
   ```

## 相关文件

- `app/init_permission.py` - 权限初始化脚本（已更新）
- `update_permissions.py` - 权限更新脚本（新建）
- `test_permission_fix.py` - 权限修复验证脚本（新建）
- `app/routes/test_case.py` - 测试用例 API
- `app/routes/module.py` - 模块 API
- `app/utils/permission.py` - 权限装饰器

## 问题已解决 ✅

前端现在可以正常访问测试用例功能，只要用户是项目成员即可。
