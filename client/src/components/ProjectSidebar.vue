<template>
  <div class="left-sidebar" :class="{ collapsed }">
    <el-menu
      :default-active="activeModule"
      class="module-menu"
      :collapse="collapsed"
      :collapse-transition="false"
      @select="handleModuleChange"
    >
      <el-menu-item index="requirement">
        <el-icon><Tickets /></el-icon>
        <span>需求管理</span>
      </el-menu-item>
      <el-menu-item index="api">
        <el-icon><Connection /></el-icon>
        <span>接口管理</span>
      </el-menu-item>
      <el-menu-item index="automation">
        <el-icon><VideoPlay /></el-icon>
        <span>自动化管理</span>
      </el-menu-item>
      <el-menu-item index="case">
        <el-icon><Document /></el-icon>
        <span>用例管理</span>
      </el-menu-item>
      <el-menu-item index="bug">
        <el-icon><Warning /></el-icon>
        <span>Bug管理</span>
      </el-menu-item>
    </el-menu>

    <!-- 收起/展开切换按钮 -->
    <div
      class="sidebar-toggle"
      :title="collapsed ? '展开菜单' : '收起菜单'"
      @click="toggleCollapse"
    >
      <el-icon class="toggle-icon">
        <Expand v-if="collapsed" />
        <Fold v-else />
      </el-icon>
      <span v-if="!collapsed" class="toggle-text">收起菜单</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Connection, VideoPlay, Document, Warning, Tickets, Fold, Expand
} from '@element-plus/icons-vue'

const props = defineProps({
  activeModule: { type: String, required: true },
  projectId: { type: [Number, String], required: true },
  projectName: { type: String, default: '项目详情' }
})

const emit = defineEmits(['stay'])
const router = useRouter()
const route = useRoute()

const routeMap = {
  requirement: 'RequirementManagement',
  api: 'ProjectDetail',
  automation: 'AutomationManagement',
  case: 'TestCaseManagement',
  bug: 'BugManagementNew'
}

const handleModuleChange = (index) => {
  const routeName = routeMap[index]
  if (index === props.activeModule && route.name === routeName) {
    emit('stay')
    return
  }
  if (routeName) {
    router.push({
      name: routeName,
      params: { projectId: props.projectId },
      query: { projectName: props.projectName }
    })
  } else {
    ElMessage.info('该模块正在开发中...')
  }
}

/* ========== 侧边栏收起 / 展开 ========== */
const STORAGE_KEY = 'projectSidebarCollapsed'
const NARROW_BREAKPOINT = 992

const userCollapsed = ref(localStorage.getItem(STORAGE_KEY) === '1')
const isNarrow = ref(false)

const collapsed = computed(() => userCollapsed.value || isNarrow.value)

function checkNarrow() {
  isNarrow.value = window.innerWidth < NARROW_BREAKPOINT
}

function toggleCollapse() {
  userCollapsed.value = !userCollapsed.value
  localStorage.setItem(STORAGE_KEY, userCollapsed.value ? '1' : '0')
}

onMounted(() => {
  checkNarrow()
  window.addEventListener('resize', checkNarrow)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkNarrow)
})
</script>

<style scoped>
.left-sidebar {
  width: 200px;
  flex-shrink: 0;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.25s ease;
}

.left-sidebar.collapsed {
  width: 44px;
}

.module-menu {
  border: none;
  flex: 1;
  width: 100%;
}

/* 折叠态：覆盖 el-menu 默认 64px，收窄到 44px 并让图标居中 */
.left-sidebar.collapsed .module-menu.el-menu--collapse {
  width: 44px;
}

.left-sidebar.collapsed .module-menu :deep(.el-menu-item) {
  padding: 0;
  justify-content: center;
}

.left-sidebar.collapsed .module-menu :deep(.el-menu-item .el-icon) {
  margin-right: 0;
}

/* 切换按钮 */
.sidebar-toggle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  border-top: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-regular);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s, color 0.2s;
}

.sidebar-toggle:hover {
  background: var(--el-menu-hover-bg-color, var(--el-fill-color-light));
  color: var(--el-color-primary);
}

.sidebar-toggle .toggle-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.left-sidebar.collapsed .sidebar-toggle {
  padding: 0;
}
</style>
