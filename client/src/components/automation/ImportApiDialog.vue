<template>
  <el-dialog
    :model-value="visible"
    title="导入接口"
    width="720px"
    append-to-body
    destroy-on-close
    @update:model-value="(val) => emit('update:visible', val)"
  >
    <div class="import-api-dialog">
      <el-input
        v-model="keyword"
        placeholder="按接口名称 / 路径 / 方法搜索"
        clearable
        size="small"
        spellcheck="false"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="filteredList"
        height="400"
        size="small"
        row-key="id"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="method" label="方法" width="80">
          <template #default="{ row }">
            <el-tag :type="methodTagType(row.method)" size="small">{{ row.method }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
      </el-table>

      <div class="footer-tip">
        已选 <span class="num">{{ selected.length }}</span> 个接口
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="selected.length === 0" @click="submit">
        导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getApis } from '../../api/api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [Number, String], required: true }
})

const emit = defineEmits(['update:visible', 'confirm'])

const loading = ref(false)
const submitting = ref(false)
const apiList = ref([])
const selected = ref([])
const keyword = ref('')
const tableRef = ref(null)

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return apiList.value
  return apiList.value.filter(it => {
    return (
      (it.name || '').toLowerCase().includes(kw) ||
      (it.path || '').toLowerCase().includes(kw) ||
      (it.method || '').toLowerCase().includes(kw)
    )
  })
})

const onSelectionChange = (rows) => {
  selected.value = rows
}

const loadApis = async () => {
  loading.value = true
  try {
    const res = await getApis(props.projectId, { per_page: 1000 })
    apiList.value = res.data || res || []
  } catch (e) {
    console.error('加载接口列表失败:', e)
    ElMessage.error('加载接口列表失败')
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    keyword.value = ''
    selected.value = []
    if (tableRef.value) tableRef.value.clearSelection()
    loadApis()
  }
})

const submit = async () => {
  if (selected.value.length === 0) return
  submitting.value = true
  try {
    const items = selected.value.map(api => ({ kind: 'api', id: api.id }))
    emit('confirm', items)
  } finally {
    submitting.value = false
  }
}

const methodTagType = (method) => {
  const m = (method || '').toUpperCase()
  return ({
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'warning'
  })[m] || 'info'
}
</script>

<style scoped>
.import-api-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.footer-tip {
  text-align: right;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.footer-tip .num {
  color: var(--el-color-primary);
  font-weight: 600;
  margin: 0 4px;
}
</style>
