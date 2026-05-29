# 前端权限管理使用指南

## 新增页面

### 1. 系统初始化页面 (`/init`)
- **路径**: `/init`
- **功能**: 初始化系统用户和权限
- **步骤**:
  1. 初始化默认用户（admin/admin123, test/test123）
  2. 初始化角色和权限（admin, owner, member, viewer）
  3. 完成后跳转到登录页

### 2. 项目列表页面 (`/projects`)
- **路径**: `/projects`
- **功能**: 
  - 查看用户有权限的所有项目
  - 创建新项目（创建者自动成为项目负责人）
  - 编辑项目（需要owner或admin角色）
  - 删除项目（需要owner或admin角色）
  - 管理项目成员（需要owner或admin角色）
- **权限控制**:
  - 根据用户在项目中的角色显示不同操作按钮
  - owner和admin可以看到"成员管理"、"编辑"、"删除"按钮
  - member和viewer只能看到"查看"按钮

### 3. 项目成员管理页面 (`/projects/:projectId/members`)
- **路径**: `/projects/:projectId/members`
- **功能**:
  - 查看项目所有成员
  - 添加新成员并分配角色
  - 修改成员角色
  - 移除成员（不能移除项目负责人）
- **权限控制**:
  - 只有owner和admin可以访问此页面
  - 项目负责人（owner）不能被修改角色或移除

## 新增API接口

### 项目管理 (`api/project.js`)
```javascript
getProjects()          // 获取项目列表
createProject(data)    // 创建项目
updateProject(id, data) // 更新项目
deleteProject(id)      // 删除项目
```

### 成员管理 (`api/member.js`)
```javascript
getProjectMembers(projectId)      // 获取项目成员
addProjectMember(data)            // 添加成员
updateMemberRole(memberId, data)  // 更新角色
removeMember(memberId)            // 移除成员
```

### 角色管理 (`api/role.js`)
```javascript
getRoles()        // 获取角色列表
getPermissions()  // 获取权限列表
initRoles()       // 初始化角色和权限
```

### 用户管理 (`api/user.js`)
```javascript
getUsers()   // 获取用户列表
initUsers()  // 初始化用户
```

## 使用流程

### 首次使用

1. **访问初始化页面**
   ```
   http://localhost:5173/init
   ```

2. **按步骤初始化**
   - 点击"初始化用户"按钮
   - 点击"初始化权限"按钮
   - 完成后点击"前往登录"

3. **登录系统**
   - 使用 admin/admin123 登录
   - 或使用 test/test123 登录

### 项目管理

1. **创建项目**
   - 在Dashboard点击"项目管理"或"新建项目"
   - 进入项目列表页面
   - 点击"新建项目"按钮
   - 填写项目名称和描述
   - 创建成功后，你将自动成为项目负责人

2. **管理项目成员**
   - 在项目列表中找到你的项目
   - 点击"成员管理"按钮（只有owner和admin可见）
   - 点击"添加成员"
   - 选择用户并分配角色（member或viewer）
   - 可以随时修改成员角色或移除成员

3. **编辑/删除项目**
   - 只有项目负责人（owner）和管理员（admin）可以编辑和删除项目
   - 点击"编辑"按钮修改项目信息
   - 点击"删除"按钮删除项目（需要确认）

## 角色权限说明

### admin - 平台管理员
- ✅ 所有项目的所有权限
- ✅ 创建、编辑、删除任何项目
- ✅ 管理任何项目的成员
- ✅ 创建、编辑、删除用例
- ✅ 执行测试

### owner - 项目负责人
- ✅ 项目内所有权限
- ✅ 编辑、删除项目
- ✅ 管理项目成员
- ✅ 创建、编辑、删除用例
- ✅ 执行测试

### member - 项目成员
- ✅ 查看项目
- ✅ 创建、编辑用例
- ✅ 执行测试
- ❌ 不能删除项目
- ❌ 不能管理成员

### viewer - 只读用户
- ✅ 查看项目
- ✅ 查看用例
- ✅ 查看执行结果
- ❌ 不能修改任何内容
- ❌ 不能执行测试

## 前端权限控制

### 1. 路由守卫
```javascript
// router/index.js
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})
```

### 2. 请求拦截器
```javascript
// api/request.js
service.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  const username = localStorage.getItem('username')
  
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  if (username) {
    config.headers['X-Username'] = username
  }
  return config
})
```

### 3. 页面级权限控制
```vue
<!-- 根据角色显示不同按钮 -->
<el-button
  v-if="canManageMembers(row.role)"
  @click="manageMembers(row)"
>
  成员管理
</el-button>

<script>
const canManageMembers = (role) => {
  return ['admin', 'owner'].includes(role)
}
</script>
```

## 注意事项

1. **Token存储**: 当前使用localStorage存储token和username，生产环境建议使用更安全的方式
2. **权限验证**: 前端权限控制只是辅助，真正的权限验证在后端
3. **角色显示**: 项目列表会显示用户在每个项目中的角色
4. **负责人保护**: 项目负责人不能被修改角色或移除
5. **数据隔离**: 用户只能看到自己参与的项目

## 开发计划

- [x] 项目列表页面
- [x] 项目成员管理页面
- [x] 系统初始化页面
- [ ] 用例管理页面（带权限控制）
- [ ] 执行记录页面
- [ ] 个人中心页面
- [ ] 权限审计日志
