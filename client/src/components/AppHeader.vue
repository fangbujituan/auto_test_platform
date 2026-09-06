<template>
  <div class="app-header">
    <div class="header-left">
      <div class="logo" @click="goToDashboard">
        <el-icon :size="24"><Platform /></el-icon>
        <span class="logo-text">ATP</span>
      </div>

      <!-- 项目切换下拉框 -->
      <el-select
        v-if="projects.length > 0"
        :model-value="currentProjectId"
        placeholder="切换项目"
        class="project-select"
        popper-class="project-switch-popper"
        :teleported="true"
        filterable
        default-first-option
        filter-placeholder="搜索项目"
        no-match-text="无匹配项目"
        @change="handleProjectChange"
      >
        <template #prefix>
          <el-icon><FolderOpened /></el-icon>
        </template>
        <el-option
          v-for="proj in projects"
          :key="proj.id"
          :label="proj.name"
          :value="String(proj.id)"
        />
      </el-select>
    </div>
    
    <div class="header-right">

      <el-button text @click="goToProjects">
        <el-icon><FolderOpened /></el-icon>
        项目列表
      </el-button>

      <el-button text @click="goToToolbox">
        <el-icon><Tools /></el-icon>
        工具箱
      </el-button>

      <el-dropdown @command="handleCommand" trigger="click">
        <div class="user-info">
          <el-avatar :size="32" :icon="UserFilled" />
          <span class="username">{{ username }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="settings">
              <el-icon><Setting /></el-icon>
              设置
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Platform,
  FolderOpened,
  UserFilled,
  Setting,
  SwitchButton,
  ArrowDown,
  Tools
} from '@element-plus/icons-vue'
import { logout } from '../api/auth'
import { getProjects } from '../api/project'

const router = useRouter()
const route = useRoute()
const username = ref('')
const projects = ref([])

// 当前所在项目（仅项目内页面有 projectId）
const currentProjectId = computed(() => {
  const id = route.params.projectId
  return id !== undefined ? String(id) : ''
})

// 项目内页面路由：切换项目时停留在当前模块
const PROJECT_ROUTE_NAMES = [
  'ProjectDetail',
  'ProjectMembers',
  'RequirementManagement',
  'BugManagement',
  'BugManagementNew',
  'TestCaseManagement',
  'AutomationManagement'
]

async function loadProjects() {
  try {
    const res = await getProjects()
    projects.value = res.data || []
  } catch (e) {
    // 未登录或接口异常时静默处理，不展示下拉框
    projects.value = []
  }
}

function handleProjectChange(projectId) {
  const proj = projects.value.find(p => String(p.id) === String(projectId))
  const projectName = proj ? proj.name : ''
  let targetName = PROJECT_ROUTE_NAMES.includes(route.name) ? route.name : 'ProjectDetail'
  // 需求详情页绑定具体需求，切项目后回到新需求列表
  if (route.name === 'RequirementDetail') targetName = 'RequirementManagement'
  router.push({
    name: targetName,
    params: { projectId },
    query: { projectName }
  })
}

onMounted(() => {
  username.value = localStorage.getItem('username') || '用户'
  loadProjects()
})

// 跳转到仪表盘
const goToDashboard = () => {
  router.push('/dashboard')
}

// 跳转到工具箱
const goToToolbox = () => {
  router.push('/toolbox')
}

// 跳转到项目列表
const goToProjects = () => {
  router.push('/projects')
}

// 处理下拉菜单命令
const handleCommand = async (command) => {
  switch (command) {
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      await handleLogout()
      break
  }
}

// 退出登录
const handleLogout = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要退出登录吗？',
      '退出确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await logout()
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    ElMessage.success('退出成功')
    router.push('/login')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('退出失败:', error)
    }
  }
}
</script>

<style scoped>
.app-header {
  height: 48px;
  background: var(--el-bg-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 项目切换下拉框：固定宽度，超长项目名省略号 */
.project-select {
  width: 200px;
}

.project-select :deep(.el-select__wrapper),
.project-select :deep(.el-select__wrapper.is-hovering),
.project-select :deep(.el-select__wrapper.is-focused) {
  width: 100%;
  min-height: 32px;
  border-radius: 4px;
}

.project-select :deep(.el-select__placeholder),
.project-select :deep(.el-select__selected-item) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  color: var(--el-color-primary);
  transition: all 0.3s;
}

.logo:hover {
  opacity: 0.8;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 15px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s;
}

.user-info:hover {
  background-color: var(--el-fill-color-light);
}

.username {
  font-size: 14px;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

@media (max-width: 768px) {
  .logo-text {
    display: none;
  }
  
  .username {
    display: none;
  }

  .project-select {
    width: 140px;
  }
}
</style>

<!-- 非 scoped：下拉弹层 teleport 到 body，需要全局样式 -->
<style>
/* 项目切换下拉面板：宽度自适应最长项目名，而非强制等于触发框宽度 */
.project-switch-popper {
  min-width: max-content !important;
  max-width: 420px;
  border-radius: 4px !important;
}

.project-switch-popper .el-select-dropdown__list {
  padding: 6px 0;
}

.project-switch-popper .el-select-dropdown__item {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 400px;
}
</style>
