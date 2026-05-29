# 测试脚本目录

本目录包含项目的各种测试和工具脚本。

## 目录结构

### API 测试脚本
- `test_api.py` - API 接口基础测试
- `test_bug_api.py` - Bug 管理 API 测试
- `test_bug_fix.py` - Bug 修复验证测试
- `test_bug_tree.py` - Bug 树形结构测试
- `test_bug_tree_api.py` - Bug 树形 API 测试
- `test_case_module_demo.py` - 测试用例模块演示
- `test_permission_fix.py` - 权限修复测试
- `test_request_factory.py` - 请求工厂测试
- `verify_api_fix.py` - API 修复验证

### 数据检查脚本
- `check_data.py` - 检查数据库中的目录和接口数据
- `check_setup.py` - 检查测试用例管理模块配置
- `check_bug_data.py` - 检查 Bug 数据
- `check_user_project.py` - 检查用户项目关联

### 初始化脚本
- `init_bug_data.py` - 初始化 Bug 测试数据
- `init_folders.py` - 初始化文件夹数据
- `init_test_case_permissions.py` - 初始化测试用例权限

### 数据库迁移脚本
- `migrate_add_folder.py` - 添加文件夹字段迁移
- `migrate_add_folder_to_bug_testcase.py` - 为 Bug 和测试用例添加文件夹
- `migrate_add_test_case_module.py` - 添加测试用例模块
- `migrate_test_case_optional_fields.py` - 测试用例可选字段迁移

### 其他工具
- `create_test_case_vue.py` - 创建测试用例 Vue 组件
- `update_permissions.py` - 更新权限配置

## 使用方法

所有脚本都可以从项目根目录直接运行：

```bash
# 运行 API 测试
python tests/test_api.py

# 检查数据
python tests/check_data.py

# 初始化数据
python tests/init_bug_data.py

# 运行数据库迁移
python tests/migrate_add_folder.py
```

**注意**：所有测试脚本都已配置好路径，可以直接从项目根目录运行，无需担心导入问题。

## 注意事项

1. 运行测试前确保后端服务已启动（默认 http://localhost:12048）
2. 数据库迁移脚本请谨慎使用，建议先备份数据库
3. 初始化脚本会创建测试数据，可能影响现有数据
4. 所有脚本都应该从项目根目录运行（不是从 tests 目录内）
