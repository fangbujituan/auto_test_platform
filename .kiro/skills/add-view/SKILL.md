---
name: add-view
description: 在 client/src/views/ 新增一个 Vue 3 + Element Plus 页面，配套 client/src/api/ 接口模块，并在 client/src/router/index.js 注册路由（含 requiresAuth 守卫）。
---

# 新增 Vue 3 视图页

## 何时激活

用户说要"新增 / 加 / 写一个页面 / 视图 / Vue 页"，落在前端 `client/src/views/`。
典型触发词：「加一个 xxx 管理页」「新增 xxx 列表 / 详情页」「补一个 Vue view」。

## 必要输入

确认（缺哪个问哪个）：

- 页面名（PascalCase，如 `CommentManagement` / `RegressionReport`）→ 文件名直接用
- 路由路径（项目级 `/projects/:projectId/<resource>` / 全局 `/<resource>`）
- 路由 `name`（PascalCase，与页面名一致或加后缀，如 `CommentManagement`）
- 是否需要登录（默认 `meta: { requiresAuth: true }`）
- 调用哪些后端接口（决定 `client/src/api/<resource>.js` 是否需新建，若没有先调 `add-route` skill 同时配前端 API）

## 项目硬约束

1. **Vue 3 + `<script setup>`**（不要写 Options API），UI 组件统一用 **Element Plus**。
2. 全局已 `app.use(ElementPlus)`，**不要在视图里重复 import 整个 Element Plus**；具体组件 `<el-xxx>` 直接用，图标按需 `import { Plus, Search } from '@element-plus/icons-vue'`。
3. HTTP 请求一律走 `client/src/api/<resource>.js`，**不要在 view 里直接 `import axios`**，因为 `request.js` 已统一处理：
   - `baseURL = '/api'`
   - 自动塞 `Authorization: Bearer <token>` + `X-Username` 头
   - 拦截 `code !== 0` 弹 ElMessage，所以 view 里只接收 `data` 字段
4. 路由统一在 `client/src/router/index.js` 集中注册（不要散落配置）。需要登录的页面加 `meta: { requiresAuth: true }`。
5. 页面里 `useRoute()` 拿 `projectId`，从 `route.params.projectId` 取（数字字符串，需要时手动 `Number(...)`）。
6. 主题 / 路径 / token 都存 `localStorage`（参考 `main.js` / `request.js`），不要用 `sessionStorage`。
7. 业务列表页一般用 `MainLayout` + `ProjectSidebar` 三栏结构，参考 `views/BugManagementNew.vue`。简单页直接 `<div class="page-container">` 也可。

## 实现步骤

### 1. 阅读相邻样例

读：
- `client/src/views/BugManagementNew.vue` —— 三栏结构样板
- `client/src/views/ProjectList.vue` —— 简单列表页样板
- `client/src/api/bug.js` —— API 模块样板
- `client/src/api/request.js` —— 知道拦截器在做什么

### 2.（如未存在）新建前端 API 模块

新建 `client/src/api/<resource>.js`（参考 `add-route` skill 第 6 步），保证函数名 `getXxx / createXxx / updateXxx / deleteXxx` 风格。

### 3. 写 Vue 视图

新建 `client/src/views/<PageName>.vue`：

```vue
<template>
  <div class="page-container" v-loading="loading">
    <!-- 顶部操作区 -->
    <div class="page-header">
      <el-input
        v-model="keyword"
        placeholder="搜索"
        clearable
        size="small"
        style="width: 240px"
        @keyup.enter="loadList"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" size="small" @click="handleCreate">
        <el-icon><Plus /></el-icon>新建
      </el-button>
    </div>

    <!-- 列表 -->
    <el-table :data="list" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建 / 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑' : '新建'" width="500">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  get<Resource>s,
  create<Resource>,
  update<Resource>,
  delete<Resource>,
} from '@/api/<resource>'

const route = useRoute()
const projectId = Number(route.params.projectId)

const loading = ref(false)
const keyword = ref('')
const list = ref([])
const dialogVisible = ref(false)
const form = ref({ id: null, name: '', description: '' })

async function loadList() {
  loading.value = true
  try {
    const res = await get<Resource>s(projectId, { keyword: keyword.value })
    // 拦截器已剥掉 code/message，res.data 就是数组
    list.value = res.data || []
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  form.value = { id: null, name: '', description: '' }
  dialogVisible.value = true
}

function handleEdit(row) {
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.value.name) {
    ElMessage.warning('请填写名称')
    return
  }
  if (form.value.id) {
    await update<Resource>(projectId, form.value.id, form.value)
    ElMessage.success('更新成功')
  } else {
    await create<Resource>(projectId, form.value)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  loadList()
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除「${row.name}」?`, '提示', { type: 'warning' })
  await delete<Resource>(projectId, row.id)
  ElMessage.success('删除成功')
  loadList()
}

onMounted(loadList)
</script>

<style scoped>
.page-container {
  padding: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>
```

### 4. 注册路由

修改 `client/src/router/index.js`：

```js
// 顶部 import
import <PageName> from '../views/<PageName>.vue'

// routes 数组中追加（按字母 / 模块就近）
{
  path: '/projects/:projectId/<resource>',
  name: '<PageName>',
  component: <PageName>,
  meta: { requiresAuth: true },
},
```

## 验证

1. `cd client && npm run build` 通过（不要起 dev server，会阻塞）。
2. 视图里所有调用都走 `@/api/<resource>` 模块，**全文件不出现 `axios`**。
3. 路由 `meta.requiresAuth` 设置正确。
4. import 的 Element Plus 图标全部从 `@element-plus/icons-vue` 取，没有写死的 SVG。
5. 调试用：用户手动 `npm run dev`，访问对应路径自测。

## 反模式

- 在 `<script setup>` 之外定义全局变量 / mutate `localStorage` —— 状态管理走 ref / reactive。
- 用 fetch / 自己 new XMLHttpRequest —— 必须走 `request.js` 拿统一拦截。
- 把后端响应的 `code` 字段当业务字段拿（如 `if (res.code === 0)`）—— 拦截器已经把成功响应剥掉一层，view 里只看 `res.data`。
- 用中文路由路径 / 中文 name —— 路径、name 一律英文。
