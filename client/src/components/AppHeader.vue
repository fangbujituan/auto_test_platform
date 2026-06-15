<template>
  <div class="app-header">
    <div class="header-left">
      <div class="logo" @click="goToDashboard">
        <el-icon :size="24"><Platform /></el-icon>
        <span class="logo-text">ATP</span>
      </div>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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

const router = useRouter()
const username = ref('')

onMounted(() => {
  username.value = localStorage.getItem('username') || '用户'
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
}
</style>
