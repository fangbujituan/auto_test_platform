<template>
  <el-drawer
    :model-value="visible"
    title="环境变量管理"
    direction="rtl"
    size="650px"
    @close="$emit('update:visible', false)"
  >
    <div class="env-panel">
      <div class="panel-toolbar">
        <el-button type="primary" size="small" @click="addRow">
          <el-icon><Plus /></el-icon> 新增
        </el-button>
      </div>

      <el-table :data="variables" border style="width: 100%" v-loading="loading">
        <el-table-column label="变量名" min-width="150">
          <template #default="{ row }">
            <el-input
              v-model="row.name"
              size="small"
              placeholder="变量名"
              spellcheck="false"
            />
          </template>
        </el-table-column>

        <el-table-column label="变量值" min-width="180">
          <template #default="{ row }">
            <el-input
              v-model="row.value"
              size="small"
              placeholder="变量值"
              spellcheck="false"
            />
          </template>
        </el-table-column>

        <el-table-column label="备注" min-width="140">
          <template #default="{ row }">
            <el-input
              v-model="row.remark"
              size="small"
              placeholder="备注"
              spellcheck="false"
            />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="130" align="center">
          <template #default="{ row, $index }">
            <el-button type="primary" link size="small" @click="saveRow(row, $index)">
              保存
            </el-button>
            <el-button type="danger" link size="small" @click="deleteRow(row, $index)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getEnvVariables,
  createEnvVariable,
  updateEnvVariable,
  deleteEnvVariable
} from '../api/envVariable'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [Number, String], required: true }
})

defineEmits(['update:visible'])

const loading = ref(false)
const variables = ref([])

const loadVariables = async () => {
  loading.value = true
  try {
    const res = await getEnvVariables(props.projectId)
    variables.value = (res.data || []).map(v => ({ ...v, _isNew: false }))
  } catch (e) {
    console.error('加载环境变量失败:', e)
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (val) => {
  if (val) loadVariables()
})

const addRow = () => {
  variables.value.unshift({ id: null, name: '', value: '', remark: '', _isNew: true })
}

const saveRow = async (row) => {
  const data = { name: row.name, value: row.value, remark: row.remark }
  try {
    if (row._isNew) {
      const res = await createEnvVariable(props.projectId, data)
      row.id = res.data.id
      row._isNew = false
      ElMessage.success('创建成功')
    } else {
      await updateEnvVariable(props.projectId, row.id, data)
      ElMessage.success('更新成功')
    }
  } catch (e) {
    // 错误已由 request.js 拦截器处理
  }
}

const deleteRow = async (row, index) => {
  if (row._isNew) {
    variables.value.splice(index, 1)
    return
  }
  try {
    await ElMessageBox.confirm('确定要删除该环境变量吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteEnvVariable(props.projectId, row.id)
    variables.value.splice(index, 1)
    ElMessage.success('删除成功')
  } catch (e) {
    // 取消或错误
  }
}
</script>

<style scoped>
.env-panel {
  padding: 0 4px;
}
.panel-toolbar {
  margin-bottom: 12px;
}
</style>
