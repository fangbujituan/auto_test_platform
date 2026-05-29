<template>
  <div class="key-value-editor">
    <div class="editor-toolbar">
      <el-button type="primary" size="small" @click="addRow">
        <el-icon><Plus /></el-icon>
        添加
      </el-button>
      <el-button size="small" @click="clearAll">
        <el-icon><Delete /></el-icon>
        清空
      </el-button>
    </div>

    <el-table
      :data="rows"
      stripe
      border
      size="small"
      class="kv-table"
    >
      <el-table-column prop="key" label="参数键" width="150" align="left">
        <template #default="{ row, $index }">
          <el-input
            v-model="row.key"
            placeholder="参数名"
            size="small"
            spellcheck="false"
            @input="updateModel"
          />
        </template>
      </el-table-column>

      <el-table-column prop="value" label="参数值" min-width="200" align="left">
        <template #default="{ row, $index }">
          <el-input
            v-model="row.value"
            placeholder="参数值"
            size="small"
            spellcheck="false"
            @input="updateModel"
          />
        </template>
      </el-table-column>

      <el-table-column prop="type" label="参数类型" width="100" align="center">
        <template #default="{ row, $index }">
          <el-select
            v-model="row.type"
            placeholder="类型"
            size="small"
            @change="updateModel"
          >
            <el-option label="string" value="string" />
            <el-option label="number" value="number" />
            <el-option label="boolean" value="boolean" />
            <el-option label="array" value="array" />
            <el-option label="object" value="object" />
          </el-select>
        </template>
      </el-table-column>

      <el-table-column prop="description" label="说明" min-width="150" align="left">
        <template #default="{ row, $index }">
          <el-input
            v-model="row.description"
            placeholder="参数说明"
            size="small"
            spellcheck="false"
            @input="updateModel"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row, $index }">
          <el-button
            type="danger"
            size="small"
            text
            @click="deleteRow($index)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue'])

const rows = ref([])
let isInitialized = false

// 初始化：将 JSON 对象转换为行数据（仅在第一次）
watch(() => props.modelValue, (newVal) => {
  // 只在未初始化时进行转换
  if (!isInitialized) {
    if (newVal && typeof newVal === 'object' && Object.keys(newVal).length > 0) {
      rows.value = Object.entries(newVal).map(([key, value]) => ({
        key,
        value: typeof value === 'string' ? value : JSON.stringify(value),
        type: typeof value,
        description: ''
      }))
    } else {
      rows.value = []
    }
    isInitialized = true
  }
}, { immediate: true, deep: true })

// 重置初始化状态（用于刷新后重新加载数据）
const resetInitialization = () => {
  isInitialized = false
}

// 暴露方法给父组件
defineExpose({
  resetInitialization
})

// 更新模型：将行数据转换为 JSON 对象
const updateModel = () => {
  const result = {}
  rows.value.forEach(row => {
    if (row.key.trim()) {
      try {
        // 尝试根据类型转换值
        let value = row.value
        if (row.type === 'number') {
          value = parseFloat(row.value)
        } else if (row.type === 'boolean') {
          value = row.value === 'true' || row.value === '1'
        } else if (row.type === 'array' || row.type === 'object') {
          value = JSON.parse(row.value)
        }
        result[row.key] = value
      } catch (e) {
        // 如果转换失败，保持为字符串
        result[row.key] = row.value
      }
    }
  })
  emit('update:modelValue', result)
}

// 添加行
const addRow = () => {
  rows.value.push({
    key: '',
    value: '',
    type: 'string',
    description: ''
  })
}

// 删除行
const deleteRow = (index) => {
  rows.value.splice(index, 1)
  updateModel()
}

// 清空所有
const clearAll = () => {
  rows.value = []
  emit('update:modelValue', {})
}
</script>

<style scoped>
.key-value-editor {
  width: 100%;
}

.editor-toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}

.kv-table {
  width: 100%;
}

:deep(.el-input__inner),
:deep(.el-textarea__inner) {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}
</style>
