# Bug目录功能测试指南

## 功能说明
为Bug新增功能添加了目录选择器，现在创建Bug时必须选择所属目录。

## 前端修改

### 1. BugManagementNew.vue（新版Bug管理页面）
- ✅ 添加了目录选择器（el-tree-select）
- ✅ 添加了folderOptions数据存储目录列表
- ✅ 添加了loadFolders函数加载目录列表
- ✅ 修改了bugRules，添加folder_id为必填项
- ✅ 在onMounted中调用loadFolders
- ✅ 在目录创建/更新/初始化后刷新目录列表
- ✅ showCreateBugDialog支持传入folderId参数

### 2. BugManagement.vue（旧版Bug管理页面）
- ✅ 添加了目录选择器（el-tree-select）
- ✅ 添加了folderOptions数据存储目录列表
- ✅ 添加了loadFolders函数加载目录列表
- ✅ 修改了rules，添加folder_id为必填项
- ✅ 在onMounted中调用loadFolders
- ✅ showCreateDialog和editCurrentBug包含folder_id字段

### 3. API调用
- ✅ 使用getFolders接口获取目录列表
- ✅ 目录数据格式：{ id, name, children }

## 后端支持

### 1. 数据库
- ✅ bugs表已有folder_id字段（通过migrate_add_folder_to_bug_testcase.py迁移）
- ✅ folder_id关联到api_folders表

### 2. API接口
- ✅ GET /api/projects/{project_id}/folders - 获取目录树
- ✅ POST /api/projects/{project_id}/bugs - 创建Bug（支持folder_id）
- ✅ PUT /api/projects/{project_id}/bugs/{bug_id} - 更新Bug（支持folder_id）

## 测试步骤

### 1. 准备测试数据
```bash
# 确保项目有目录
python test_bug_tree.py
```

### 2. 测试创建Bug
1. 打开Bug管理页面
2. 点击"新建Bug"按钮
3. 验证"所属目录"字段显示为必填（红色星号）
4. 验证目录下拉框显示目录树结构
5. 不选择目录，点击确定，应该提示"请选择所属目录"
6. 选择一个目录，填写其他必填字段，点击确定
7. 验证Bug创建成功，并显示在选择的目录下

### 3. 测试编辑Bug
1. 选择一个已有的Bug
2. 点击"编辑"按钮
3. 验证目录选择器显示当前Bug的目录
4. 修改目录为其他目录
5. 点击确定
6. 验证Bug移动到新目录下

### 4. 测试从目录创建Bug
1. 在目录树中，右键点击一个目录
2. 选择"新建Bug"
3. 验证目录选择器自动选中该目录
4. 填写其他字段，点击确定
5. 验证Bug创建在该目录下

## 预期结果
- ✅ 创建Bug时必须选择目录
- ✅ 目录选择器显示树形结构
- ✅ 可以选择任意层级的目录
- ✅ 编辑Bug时可以修改目录
- ✅ 从目录右键创建Bug时自动选中该目录
- ✅ Bug显示在对应的目录下

## 注意事项
1. 目录选择器使用el-tree-select组件
2. check-strictly属性允许选择任意层级的目录
3. folder_id为必填项，不能为空
4. 目录数据从api_folders表查询
5. Bug和API共用同一套目录结构
