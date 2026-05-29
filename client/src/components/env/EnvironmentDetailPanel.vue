<template>
  <div class="env-detail-panel">
    <!-- 顶部标题栏 -->
    <div class="panel-title-bar">
      <div class="title-left">
        <span
          class="env-logo"
          :style="{ backgroundColor: envColor }"
        >{{ (editingName || envName).charAt(0) }}</span>
        <el-input
          v-if="isEditingName"
          ref="nameInputRef"
          v-model="editingName"
          size="small"
          class="env-name-input"
          @blur="confirmRename"
          @keyup.enter="confirmRename"
          @keyup.escape="cancelRename"
        />
        <h4
          v-else
          class="env-name-text"
          title="点击修改环境名称"
          @click="startRename"
        >{{ envName }}</h4>
      </div>
    </div>

    <!-- 前置 URL 表格 -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">前置 URL</span>
        <el-button type="primary" link size="small" @click="addPrefixRow">
          <el-icon><Plus /></el-icon> 新增
        </el-button>
      </div>
      <el-table :data="prefixUrls" border style="width: 100%" v-loading="loadingPrefix" size="small">
        <el-table-column label="模块" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.module" size="small" placeholder="模块" spellcheck="false" />
          </template>
        </el-table-column>
        <el-table-column label="服务" min-width="120">
          <template #default="{ row }">
            <el-input v-model="row.service" size="small" placeholder="服务" spellcheck="false" />
          </template>
        </el-table-column>
        <el-table-column label="前置 URL" min-width="220">
          <template #default="{ row }">
            <el-input
              v-model="row.url"
              size="small"
              placeholder="http:// 或 https:// 起始的前置 URL"
              spellcheck="false"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row, $index }">
            <el-button type="primary" link size="small" @click="savePrefixRow(row)">
              保存
            </el-button>
            <el-button type="danger" link size="small" @click="deletePrefixRow(row, $index)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 环境变量表格 -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">环境变量</span>
        <el-button type="primary" link size="small" @click="addVarRow">
          <el-icon><Plus /></el-icon> 新增
        </el-button>
      </div>
      <el-table :data="envVariables" border style="width: 100%" v-loading="loadingVars" size="small">
        <el-table-column label="变量名" min-width="180">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" placeholder="添加变量" spellcheck="false" />
          </template>
        </el-table-column>
        <el-table-column label="变量值" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.value" size="small" placeholder="变量值" spellcheck="false" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row, $index }">
            <el-button type="primary" link size="small" @click="saveVarRow(row)">
              保存
            </el-button>
            <el-button type="danger" link size="small" @click="deleteVarRow(row, $index)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getPrefixUrls,
  createPrefixUrl,
  updatePrefixUrl,
  deletePrefixUrl,
  getEnvVariablesByEnv,
  createEnvVariableByEnv,
  updateEnvVariableByEnv,
  deleteEnvVariableByEnv,
  updateEnvironment
} from '../../api/envVariable'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  envId: { type: [Number, String], required: true },
  envName: { type: String, default: '' }
})

const emit = defineEmits(['env-renamed'])

// 颜色池（与 EnvironmentManager 保持一致）
const colorPool = [
  '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
  '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6', '#f97316'
]
const envColor = colorPool[0]

const loadingPrefix = ref(false)
const loadingVars = ref(false)
const prefixUrls = ref([])
const envVariables = ref([])

// ========== 环境名编辑 ==========
const isEditingName = ref(false)
const editingName = ref('')
const nameInputRef = ref(null)

const startRename = () => {
  editingName.value = props.envName
  isEditingName.value = true
  nextTick(() => {
    nameInputRef.value?.focus()
  })
}

const confirmRename = async () => {
  const newName = (editingName.value || '').trim()
  if (!newName) {
    ElMessage.warning('环境名称不能为空')
    cancelRename()
    return
  }
  if (newName === props.envName) {
    isEditingName.value = false
    return
  }
  try {
    await updateEnvironment(props.projectId, props.envId, { name: newName })
    isEditingName.value = false
    ElMessage.success('重命名成功')
    emit('env-renamed', props.envId, newName)
  } catch (e) {
    // 错误已由 request.js 拦截器处理
    isEditingName.value = false
  }
}

const cancelRename = () => {
  isEditingName.value = false
  editingName.value = ''
}

// ========== 数据加载 ==========
const loadPrefixUrls = async () => {
  loadingPrefix.value = true
  try {
    const res = await getPrefixUrls(props.projectId, props.envId)
    prefixUrls.value = (res.data || []).map(p => ({ ...p, _isNew: false }))
  } catch (e) {
    console.error('加载前置URL失败:', e)
  } finally {
    loadingPrefix.value = false
  }
}

const loadEnvVariables = async () => {
  loadingVars.value = true
  try {
    const res = await getEnvVariablesByEnv(props.projectId, props.envId)
    envVariables.value = (res.data || []).map(v => ({ ...v, _isNew: false }))
  } catch (e) {
    console.error('加载环境变量失败:', e)
  } finally {
    loadingVars.value = false
  }
}

// 配合父级 destroy-on-close，每次挂载自动加载
watch(() => props.envId, () => {
  loadPrefixUrls()
  loadEnvVariables()
}, { immediate: true })

// ========== 前置 URL 操作 ==========
const addPrefixRow = () => {
  prefixUrls.value.unshift({
    id: null, module: '默认模块', service: '默认服务', url: '', _isNew: true
  })
}

const savePrefixRow = async (row) => {
  if (!row.url || !row.url.trim()) {
    ElMessage.warning('前置 URL 不能为空')
    return
  }
  try {
    const payload = { module: row.module || '', service: row.service || '', url: row.url.trim() }
    if (row._isNew) {
      const res = await createPrefixUrl(props.projectId, props.envId, payload)
      row.id = res.data.id
      row._isNew = false
      ElMessage.success('创建成功')
    } else {
      await updatePrefixUrl(props.projectId, props.envId, row.id, payload)
      ElMessage.success('更新成功')
    }
  } catch (e) {
    // 错误已由 request.js 拦截器处理
  }
}

const deletePrefixRow = async (row, index) => {
  if (row._isNew) {
    prefixUrls.value.splice(index, 1)
    return
  }
  try {
    await ElMessageBox.confirm('确定要删除该前置 URL 吗？', '删除确认', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
    })
    await deletePrefixUrl(props.projectId, props.envId, row.id)
    prefixUrls.value.splice(index, 1)
    ElMessage.success('删除成功')
  } catch (e) {
    // 取消或错误
  }
}

// ========== 环境变量操作 ==========
const addVarRow = () => {
  envVariables.value.unshift({ id: null, name: '', value: '', _isNew: true })
}

const saveVarRow = async (row) => {
  if (!row.name || !row.name.trim()) {
    ElMessage.warning('变量名不能为空')
    return
  }
  try {
    const payload = { name: row.name.trim(), value: row.value }
    if (row._isNew) {
      const res = await createEnvVariableByEnv(props.projectId, props.envId, payload)
      row.id = res.data.id
      row._isNew = false
      ElMessage.success('创建成功')
    } else {
      await updateEnvVariableByEnv(props.projectId, props.envId, row.id, payload)
      ElMessage.success('更新成功')
    }
  } catch (e) {
    // 错误已由 request.js 拦截器处理
  }
}

const deleteVarRow = async (row, index) => {
  if (row._isNew) {
    envVariables.value.splice(index, 1)
    return
  }
  try {
    await ElMessageBox.confirm('确定要删除该环境变量吗？', '删除确认', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
    })
    await deleteEnvVariableByEnv(props.projectId, props.envId, row.id)
    envVariables.value.splice(index, 1)
    ElMessage.success('删除成功')
  } catch (e) {
    // 取消或错误
  }
}
</script>

<style scoped>
.env-detail-panel {
  height: 100%;
}

.panel-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-left h4 {
  margin: 0;
  font-size: 15px;
  color: var(--el-text-color-primary);
}

.env-name-text {
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}

.env-name-text:hover {
  background: var(--el-fill-color);
}

.env-name-input {
  width: 200px;
}

.env-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>
