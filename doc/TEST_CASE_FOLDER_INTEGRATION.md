# 测试用例目录集成说明

## 概述
已成功将测试用例管理模块改为使用 `api_folders` 表来管理目录结构，与 Bug 管理模块保持一致。

## 主要修改

### 1. 前端 API 层 (client/src/api/folder.js)
新增方法：
```javascript
// 获取测试用例目录树（包含测试用例）
export function getTestCaseFolderTree(projectId) {
  return request({
    url: `/test-cases/tree/${projectId}`,
    method: 'get'
  })
}
```

### 2. 前端视图层 (client/src/views/TestCaseManagement2.vue)

#### 导入变更
- 移除：`getModuleTree, createModule, updateModule, deleteModule`
- 新增：`getFolders, createFolder, updateFolder, deleteFolder, initProjectFolders, getTestCaseFolderTree`

#### 数据结构变更
- `currentModule` → `currentFolder`
- `moduleOptions` → `folderOptions`
- `moduleTreeProps` → `folderTreeProps`
- `moduleForm` → `folderForm`
- `moduleDialogVisible` → `folderDialogVisible`
- `moduleDialogTitle` → `folderDialogTitle`

#### 表单字段变更
**目录表单 (folderForm):**
- 移除：`module_no` 字段
- 保留：`id, name, description, parent_id`
- 新增：`type: 'test_case'`

**用例表单 (caseForm):**
- `module_id` → `folder_id`

#### 功能变更
- `loadModules()` → `loadFolders()`
- `showCreateModuleDialog()` → `showCreateFolderDialog()`
- `editModule()` → `editFolder()`
- `submitModule()` → `submitFolder()`
- `deleteModuleConfirm()` → `deleteFolderConfirm()`
- `handleModuleAction()` → `handleFolderAction()`
- `getModuleName()` → `getFolderName()`

#### 新增功能
- 初始化目录功能（与 Bug 管理一致）
- 支持虚拟目录（如"未分类"）

### 3. 树形结构变更

#### 节点类型
- `type: 'module'` → `type: 'folder'`
- `type: 'case'` 保持不变

#### 节点属性
目录节点包含：
- `id`: 格式为 `folder_{id}`
- `raw_id`: 实际的数据库 ID
- `name`: 目录名称
- `description`: 目录描述
- `type`: 'folder'
- `children`: 子节点数组

用例节点包含：
- `id`: 格式为 `case_{id}`
- `raw_id`: 实际的数据库 ID
- `name`: 用例标题
- `case_no`: 用例编号
- `priority`: 优先级
- `case_type`: 用例类型
- `case_status`: 用例状态
- `folder_id`: 所属目录 ID
- `type`: 'case'

## 数据源统一

### api_folders 表结构
```sql
- id: 主键
- project_id: 项目ID
- name: 目录名称
- description: 目录描述
- parent_id: 父目录ID
- type: 目录类型 ('api', 'bug', 'test_case')
- sort_order: 排序
- created_at: 创建时间
- updated_at: 更新时间
```

### 三个模块的目录类型
- 接口管理：`type = 'api'`
- Bug管理：`type = 'bug'`
- 测试用例：`type = 'test_case'`

## 后端 API

### 已有的测试用例目录树 API
```
GET /test-cases/tree/<project_id>
```

返回结构：
```json
[
  {
    "id": "folder_1",
    "raw_id": 1,
    "name": "功能测试",
    "description": "功能测试用例",
    "type": "folder",
    "children": [
      {
        "id": "folder_2",
        "raw_id": 2,
        "name": "登录模块",
        "type": "folder",
        "children": [
          {
            "id": "case_1",
            "raw_id": 1,
            "name": "测试正常登录",
            "case_no": "TC-001",
            "priority": "P1",
            "case_type": "功能",
            "case_status": "已评审",
            "type": "case"
          }
        ]
      }
    ]
  }
]
```

## UI 变更

### 中间面板
- 下拉菜单："新建模块" → "新建目录"
- 树节点操作："新建子模块" → "新建子目录"
- 新增："初始化目录" 功能

### 右侧详情面板
- 字段标签："所属模块" → "所属目录"

### 对话框
- "模块对话框" → "目录对话框"
- 移除"模块编号"字段
- 简化为只需要"目录名称"和"目录描述"

## 功能特性

### 1. 目录管理
- ✅ 创建目录（支持多级）
- ✅ 编辑目录
- ✅ 删除目录
- ✅ 目录树形展示
- ✅ 初始化默认目录结构

### 2. 用例管理
- ✅ 创建用例（关联到目录）
- ✅ 编辑用例
- ✅ 删除用例
- ✅ 用例详情查看
- ✅ 在目录树中展示

### 3. 树形交互
- ✅ 展开/收起目录
- ✅ 点击节点查看详情
- ✅ 右键菜单操作
- ✅ 统计信息显示

## 与 Bug 管理的一致性

现在三个模块都使用相同的目录管理方式：

| 特性 | 接口管理 | Bug管理 | 测试用例 |
|------|---------|---------|----------|
| 数据表 | api_folders | api_folders | api_folders |
| 目录类型 | api | bug | test_case |
| 树形结构 | ✅ | ✅ | ✅ |
| 多级目录 | ✅ | ✅ | ✅ |
| 初始化功能 | ✅ | ✅ | ✅ |
| 未分类节点 | ✅ | ✅ | ✅ |

## 测试建议

1. **目录操作测试**
   - 创建根目录
   - 创建子目录（多级）
   - 编辑目录名称和描述
   - 删除空目录
   - 删除包含用例的目录（应提示）

2. **用例操作测试**
   - 在目录下创建用例
   - 编辑用例并更改所属目录
   - 删除用例
   - 查看用例详情

3. **树形交互测试**
   - 展开/收起目录
   - 点击目录节点
   - 点击用例节点
   - 右键菜单操作

4. **初始化测试**
   - 点击"初始化目录"
   - 验证默认目录结构创建

5. **数据一致性测试**
   - 验证目录在不同模块间不互相干扰
   - 验证 type 字段正确设置为 'test_case'

## 注意事项

1. **数据迁移**：如果之前有使用 module 表的测试用例数据，需要进行数据迁移
2. **权限控制**：确保测试用例的目录操作权限正确配置
3. **级联删除**：删除目录时需要处理其下的用例
4. **未分类处理**：folder_id 为 null 的用例会显示在"未分类"节点下

## 后续优化

1. 支持目录拖拽排序
2. 支持用例在目录间拖拽移动
3. 批量移动用例到指定目录
4. 目录导入/导出功能
5. 目录模板功能
