<template>
  <el-dialog
    :model-value="visible"
    title="环境管理"
    width="960px"
    :close-on-click-modal="false"
    destroy-on-close
    @close="handleClose"
    class="env-manager-dialog"
  >
    <div class="env-manager-body">
      <!-- 左侧导航栏 -->
      <div class="env-nav">
        <!-- 全局区域 -->
        <div class="nav-section">
          <div class="nav-section-title">全局</div>
          <div
            class="nav-item"
            :class="{ active: activePanel === 'globalVariables' }"
            @click="activePanel = 'globalVariables'"
          >
            全局变量
          </div>
          <div
            class="nav-item"
            :class="{ active: activePanel === 'globalParams' }"
            @click="activePanel = 'globalParams'"
          >
            全局参数
          </div>
        </div>

        <!-- 环境区域 -->
        <div class="nav-section">
          <div class="nav-section-title">环境</div>
          <div
            v-for="env in environments"
            :key="env.id"
            class="nav-item env-item"
            :class="{ active: activePanel === 'env' && selectedEnvId === env.id }"
            @click="selectEnv(env)"
          >
            <span
              class="env-logo"
              :style="{ backgroundColor: getEnvColor(env.name) }"
            >{{ env.name.charAt(0) }}</span>
            <span class="env-name" :title="env.name">{{ env.name }}</span>
            <el-icon
              class="env-delete-icon"
              @click.stop="confirmDeleteEnv(env)"
            ><Close /></el-icon>
          </div>
          <div class="nav-item add-env" @click="handleAddEnv">
            <el-icon><Plus /></el-icon>
            <span>新建环境</span>
          </div>
        </div>
      </div>

      <!-- 右侧内容区 -->
      <div class="env-content">
        <!-- 全局变量 -->
        <GlobalVariablesPanel
          v-if="activePanel === 'globalVariables'"
          :project-id="projectId"
          ref="globalVarRef"
        />
        <!-- 全局参数 -->
        <GlobalParamsPanel
          v-if="activePanel === 'globalParams'"
          :project-id="projectId"
          ref="globalParamRef"
        />
        <!-- 环境详情 -->
        <EnvironmentDetailPanel
          v-if="activePanel === 'env' && selectedEnvId"
          :project-id="projectId"
          :env-id="selectedEnvId"
          :env-name="selectedEnvName"
          ref="envDetailRef"
          @env-renamed="handleEnvRenamed"
        />
        <!-- 空状态 -->
        <el-empty
          v-if="activePanel === 'env' && !selectedEnvId"
          description="请选择一个环境或新建环境"
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
      <el-button type="primary" @click="handleSaveAndClose">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Close } from '@element-plus/icons-vue'
import {
  getEnvironments,
  createEnvironment,
  deleteEnvironment
} from '../api/envVariable'
import GlobalVariablesPanel from './env/GlobalVariablesPanel.vue'
import GlobalParamsPanel from './env/GlobalParamsPanel.vue'
import EnvironmentDetailPanel from './env/EnvironmentDetailPanel.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [Number, String], required: true },
  currentEnvId: { type: [Number, String, null], default: null }
})

const emit = defineEmits(['update:visible', 'env-changed'])

const activePanel = ref('globalVariables')
const selectedEnvId = ref(null)
const selectedEnvName = ref('')
const environments = ref([])
const globalVarRef = ref(null)
const globalParamRef = ref(null)
const envDetailRef = ref(null)

// 预定义颜色池
const colorPool = [
  '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
  '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6', '#f97316'
]

const envColorMap = {}

function getEnvColor(name) {
  if (!envColorMap[name]) {
    const idx = Object.keys(envColorMap).length % colorPool.length
    envColorMap[name] = colorPool[idx]
  }
  return envColorMap[name]
}

async function loadEnvironments() {
  try {
    const res = await getEnvironments(props.projectId)
    environments.value = res.data || []
  } catch (e) {
    console.error('加载环境列表失败:', e)
  }
}

function selectEnv(env) {
  activePanel.value = 'env'
  selectedEnvId.value = env.id
  selectedEnvName.value = env.name
}

async function handleAddEnv() {
  try {
    const { value } = await ElMessageBox.prompt('请输入环境名称', '新建环境', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '环境名称不能为空'
    })
    const res = await createEnvironment(props.projectId, { name: value.trim() })
    ElMessage.success('创建成功')
    await loadEnvironments()
    // 自动选中新建的环境
    if (res.data) {
      selectEnv(res.data)
    }
    emit('env-changed')
  } catch (e) {
    // 取消或错误
  }
}

async function handleEnvRenamed(envId, newName) {
  // 更新本地列表中的环境名
  const env = environments.value.find(e => e.id === envId)
  if (env) {
    env.name = newName
  }
  if (selectedEnvId.value === envId) {
    selectedEnvName.value = newName
  }
  emit('env-changed')
}

async function confirmDeleteEnv(env) {
  try {
    await ElMessageBox.confirm(
      `确定要删除环境"${env.name}"吗？该环境下的所有前置 URL 和环境变量将被一并删除。`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteEnvironment(props.projectId, env.id)
    ElMessage.success('删除成功')
    if (selectedEnvId.value === env.id) {
      selectedEnvId.value = null
      selectedEnvName.value = ''
      activePanel.value = 'globalVariables'
    }
    await loadEnvironments()
    emit('env-changed')
  } catch (e) {
    // 取消或错误
  }
}

function handleClose() {
  emit('update:visible', false)
}

function handleSave() {
  ElMessage.success('保存成功')
  emit('update:visible', false)
}

function handleSaveAndClose() {
  ElMessage.success('保存成功')
  emit('update:visible', false)
}

watch(() => props.visible, async (val) => {
  if (val) {
    selectedEnvId.value = null
    selectedEnvName.value = ''
    activePanel.value = 'globalVariables'
    await loadEnvironments()
    // 优先定位到当前选中的环境，其次第一个环境，都没有则留在全局变量
    const target = props.currentEnvId
      ? environments.value.find(e => e.id === props.currentEnvId)
      : environments.value[0]
    if (target) {
      selectEnv(target)
    }
  }
})
</script>

<style scoped>
.env-manager-body {
  display: flex;
  height: 520px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
}

.env-nav {
  width: 200px;
  min-width: 200px;
  background: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.nav-section {
  padding: 8px 0;
}

.nav-section:not(:last-child) {
  border-bottom: 1px solid #e4e7ed;
}

.nav-section-title {
  padding: 6px 16px;
  font-size: 12px;
  color: #909399;
  font-weight: 500;
  text-transform: uppercase;
}

.nav-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-item:hover {
  background: #ecf5ff;
  color: #409eff;
}

.nav-item.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}

.env-item {
  position: relative;
}

.env-item .env-delete-icon {
  display: none;
  position: absolute;
  right: 10px;
  font-size: 12px;
  color: #c0c4cc;
  padding: 2px;
  border-radius: 50%;
}

.env-item:hover .env-delete-icon {
  display: inline-flex;
}

.env-item .env-delete-icon:hover {
  color: #f56c6c;
  background: #fef0f0;
}

.env-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.env-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.add-env {
  color: #409eff;
  font-size: 13px;
}

.add-env:hover {
  background: #ecf5ff;
}

.env-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
</style>

<style>
.env-manager-dialog .el-dialog__body {
  padding: 12px 20px;
}
</style>
