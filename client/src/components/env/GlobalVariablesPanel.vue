<template>
  <div class="global-variables-panel">
    <div class="panel-header">
      <h4>全局变量</h4>
      <el-button type="primary" size="small" @click="addRow">
        <el-icon><Plus /></el-icon> 新增
      </el-button>
    </div>

    <el-table :data="variables" border style="width: 100%" v-loading="loading" size="small">
      <el-table-column label="变量名" min-width="180">
        <template #default="{ row }">
          <el-input
            v-model="row.name"
            size="small"
            placeholder="添加变量"
            spellcheck="false"
          />
        </template>
      </el-table-column>

      <el-table-column label="变量值" min-width="220">
        <template #default="{ row }">
          <el-input
            v-model="row.value"
            size="small"
            placeholder="变量值"
            spellcheck="false"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row, $index }">
          <el-button type="primary" link size="small" @click="saveRow(row)">
            保存
          </el-button>
          <el-button type="danger" link size="small" @click="deleteRow(row, $index)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getGlobalVariables,
  createGlobalVariable,
  updateGlobalVariable,
  deleteGlobalVariable
} from '../../api/envVariable'

const props = defineProps({
  projectId: { type: [Number, String], required: true }
})

const loading = ref(false)
const variables = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await getGlobalVariables(props.projectId)
    variables.value = (res.data || []).map(v => ({ ...v, _isNew: false }))
  } catch (e) {
    console.error('加载全局变量失败:', e)
  } finally {
    loading.value = false
  }
}

// 配合父级 destroy-on-close，每次挂载自动加载
watch(() => props.projectId, () => {
  loadData()
}, { immediate: true })

const addRow = () => {
  variables.value.unshift({ id: null, name: '', value: '', _isNew: true })
}

const saveRow = async (row) => {
  if (!row.name || !row.name.trim()) {
    ElMessage.warning('变量名不能为空')
    return
  }
  try {
    if (row._isNew) {
      const res = await createGlobalVariable(props.projectId, {
        name: row.name.trim(),
        value: row.value
      })
      row.id = res.data.id
      row._isNew = false
      ElMessage.success('创建成功')
    } else {
      await updateGlobalVariable(props.projectId, row.id, {
        name: row.name.trim(),
        value: row.value
      })
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
    await ElMessageBox.confirm('确定要删除该全局变量吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteGlobalVariable(props.projectId, row.id)
    variables.value.splice(index, 1)
    ElMessage.success('删除成功')
  } catch (e) {
    // 取消或错误
  }
}
</script>

<style scoped>
.global-variables-panel {
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-header h4 {
  margin: 0;
  font-size: 15px;
  color: var(--el-text-color-primary);
}
</style>
