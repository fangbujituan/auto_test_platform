<template>
  <div class="global-params-panel">
    <div class="panel-header">
      <h4>全局参数（Header）</h4>
      <el-button type="primary" size="small" @click="addRow">
        <el-icon><Plus /></el-icon> 新增
      </el-button>
    </div>

    <el-table :data="params" border style="width: 100%" v-loading="loading" size="small">
      <el-table-column label="参数名" min-width="160">
        <template #default="{ row }">
          <el-input
            v-model="row.name"
            size="small"
            placeholder="添加参数"
            spellcheck="false"
          />
        </template>
      </el-table-column>

      <el-table-column label="参数值" min-width="180">
        <template #default="{ row }">
          <el-input
            v-model="row.value"
            size="small"
            placeholder="参数值"
            spellcheck="false"
          />
        </template>
      </el-table-column>

      <el-table-column label="说明" min-width="160">
        <template #default="{ row }">
          <el-input
            v-model="row.description"
            size="small"
            placeholder="说明"
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
  getGlobalParams,
  createGlobalParam,
  updateGlobalParam,
  deleteGlobalParam
} from '../../api/envVariable'

const props = defineProps({
  projectId: { type: [Number, String], required: true }
})

const loading = ref(false)
const params = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await getGlobalParams(props.projectId)
    params.value = (res.data || []).map(p => ({ ...p, _isNew: false }))
  } catch (e) {
    console.error('加载全局参数失败:', e)
  } finally {
    loading.value = false
  }
}

// 配合父级 destroy-on-close，每次挂载自动加载
watch(() => props.projectId, () => {
  loadData()
}, { immediate: true })

const addRow = () => {
  params.value.unshift({ id: null, name: '', value: '', description: '', _isNew: true })
}

const saveRow = async (row) => {
  if (!row.name || !row.name.trim()) {
    ElMessage.warning('参数名不能为空')
    return
  }
  try {
    const payload = {
      name: row.name.trim(),
      value: row.value,
      description: row.description || ''
    }
    if (row._isNew) {
      const res = await createGlobalParam(props.projectId, payload)
      row.id = res.data.id
      row._isNew = false
      ElMessage.success('创建成功')
    } else {
      await updateGlobalParam(props.projectId, row.id, payload)
      ElMessage.success('更新成功')
    }
  } catch (e) {
    // 错误已由 request.js 拦截器处理
  }
}

const deleteRow = async (row, index) => {
  if (row._isNew) {
    params.value.splice(index, 1)
    return
  }
  try {
    await ElMessageBox.confirm('确定要删除该全局参数吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteGlobalParam(props.projectId, row.id)
    params.value.splice(index, 1)
    ElMessage.success('删除成功')
  } catch (e) {
    // 取消或错误
  }
}
</script>

<style scoped>
.global-params-panel {
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
