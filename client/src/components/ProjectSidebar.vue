<template>
  <div class="left-sidebar">
    <el-menu
      :default-active="activeModule"
      class="module-menu"
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
  </div>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Connection, VideoPlay, Document, Warning, Tickets } from '@element-plus/icons-vue'

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
</script>

<style scoped>
.left-sidebar {
  width: 200px;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
}

.module-menu {
  border: none;
  flex: 1;
}

@media (max-width: 992px) {
  .left-sidebar {
    width: 60px;
  }

  .project-name,
  .module-menu :deep(.el-menu-item span) {
    display: none;
  }
}
</style>
