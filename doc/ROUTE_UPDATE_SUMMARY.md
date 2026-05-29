# 路由更新说明

## 修改内容

已将所有页面中的测试用例和Bug管理跳转更新为新的三栏布局页面。

## 修改的文件

### 1. client/src/views/BugManagementNew.vue
- 修改 `handleModuleChange` 函数
- 将测试用例跳转从 `TestCaseManagement` 改为 `TestCaseManagement2`

### 2. client/src/views/ProjectDetail.vue
- 修改 `handleModuleChange` 函数
- 将测试用例跳转从 `TestCaseManagement` 改为 `TestCaseManagement2`
- 将Bug管理跳转从 `BugManagement` 改为 `BugManagementNew`

### 3. client/src/views/TestCaseManagement2.vue
- 已正确配置跳转到 `BugManagementNew`

## 路由映射

### 新的路由结构
```
接口管理 → ProjectDetail
Bug管理 → BugManagementNew
测试用例 → TestCaseManagement2
```

### 路由配置
```javascript
// 旧路由（保留用于兼容）
{
  path: '/projects/:projectId/test-cases',
  name: 'TestCaseManagement',
  component: TestCaseManagement
}

{
  path: '/projects/:projectId/bugs',
  name: 'BugManagement',
  component: BugManagementNew
}

// 新路由（三栏布局）
{
  path: '/projects/:projectId/bugs-new',
  name: 'BugManagementNew',
  component: BugManagementNew
}

{
  path: '/projects/:projectId/test-cases-new',
  name: 'TestCaseManagement2',
  component: TestCaseManagement2
}
```

## 效果

现在点击任何页面的"测试用例"按钮都会跳转到新的三栏布局页面 `TestCaseManagement2`。

## 测试步骤

1. 从项目列表进入项目详情
2. 点击左侧菜单的"测试用例" → 应跳转到三栏布局页面
3. 在测试用例页面点击"Bug管理" → 应跳转到Bug三栏布局页面
4. 在Bug管理页面点击"测试用例" → 应跳转到测试用例三栏布局页面
5. 点击"接口管理" → 应跳转到接口管理页面

## 注意事项

- 旧的路由仍然保留，可以通过直接访问URL使用
- 所有模块切换都使用新的三栏布局页面
- 保持了统一的用户体验
