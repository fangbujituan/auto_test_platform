<template>
  <div class="key-value-editor">
    <div class="editor-toolbar">
      <el-button size="small" @click="openBulkEdit">
        <el-icon><EditPen /></el-icon>
        批量编辑
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
        <template #default="{ row }">
          <el-input
            v-model="row.key"
            placeholder="参数名"
            size="small"
            spellcheck="false"
            @input="onRowInput"
          />
        </template>
      </el-table-column>

      <el-table-column prop="value" label="参数值" min-width="200" align="left">
        <template #default="{ row }">
          <el-input
            v-model="row.value"
            placeholder="参数值"
            size="small"
            spellcheck="false"
            @input="onRowInput"
          />
        </template>
      </el-table-column>

      <el-table-column prop="type" label="参数类型" width="100" align="center">
        <template #default="{ row }">
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
        <template #default="{ row }">
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
            v-if="row.key.trim() || row.value.trim() || row.description.trim()"
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

    <!-- 批量编辑对话框 -->
    <el-dialog
      v-model="bulkEditVisible"
      title="批量编辑（JSON 对象）"
      width="640px"
      :close-on-click-modal="false"
      append-to-body
    >
      <div class="bulk-edit-tips">
        粘贴或编辑 JSON 对象，键即字段名、值即字段值。<br>
        例：<code>{"Content-Type": "application/json", "Authorization": "Bearer xxx"}</code>
      </div>
      <el-input
        v-model="bulkEditText"
        type="textarea"
        :rows="14"
        spellcheck="false"
        placeholder='{"key1": "value1", "key2": 123, "key3": true}'
        class="bulk-edit-textarea"
      />
      <div v-if="bulkEditError" class="bulk-edit-error">
        <el-icon><WarningFilled /></el-icon>
        {{ bulkEditError }}
      </div>
      <template #footer>
        <el-button @click="bulkEditVisible = false">取消</el-button>
        <el-button type="primary" @click="applyBulkEdit">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { EditPen, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue'])

const rows = ref([])
let isInitialized = false

// 创建一行空数据
const makeEmptyRow = () => ({
  key: '',
  value: '',
  type: 'string',
  description: ''
})

// 判断一行是否为"空"（空行不会被提交给后台）
const isBlankRow = (row) =>
  !row.key.trim() &&
  !row.value.trim() &&
  !row.description.trim()

// 确保末尾始终保留一行空行（让用户随时可以继续输入）
const ensureTrailingEmptyRow = () => {
  const last = rows.value[rows.value.length - 1]
  if (!last || !isBlankRow(last)) {
    rows.value.push(makeEmptyRow())
  }
}

// 初始化：将 JSON 对象转换为行数据（仅在第一次）
watch(() => props.modelValue, (newVal) => {
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
    ensureTrailingEmptyRow()
    isInitialized = true
  }
}, { immediate: true, deep: true })

// 重置初始化状态（用于刷新后重新加载数据）
const resetInitialization = () => {
  isInitialized = false
}

defineExpose({ resetInitialization })

// 行内输入触发：更新模型 + 维护末尾空行
const onRowInput = () => {
  ensureTrailingEmptyRow()
  updateModel()
}

// 更新模型：将行数据转换为 JSON 对象（跳过空 key 行）
const updateModel = () => {
  const result = {}
  rows.value.forEach(row => {
    if (!row.key.trim()) return  // 空 key 行不提交
    try {
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
      result[row.key] = row.value
    }
  })
  emit('update:modelValue', result)
}

// 删除行（删完末尾空行不见了再补回来）
const deleteRow = (index) => {
  rows.value.splice(index, 1)
  ensureTrailingEmptyRow()
  updateModel()
}

// ── 批量编辑 ──
const bulkEditVisible = ref(false)
const bulkEditText = ref('')
const bulkEditError = ref('')

const openBulkEdit = () => {
  // 把当前已填的字段序列化成 JSON 给用户编辑
  const obj = {}
  rows.value.forEach(row => {
    if (!row.key.trim()) return
    obj[row.key] = row.value  // 批量编辑里只关心 key/value，类型由用户在 JSON 里写
  })
  bulkEditText.value = Object.keys(obj).length > 0
    ? JSON.stringify(obj, null, 2)
    : '{\n  \n}'
  bulkEditError.value = ''
  bulkEditVisible.value = true
}

const applyBulkEdit = () => {
  const text = bulkEditText.value.trim()
  let parsed
  try {
    parsed = text ? JSON.parse(text) : {}
  } catch (e) {
    bulkEditError.value = `JSON 解析失败: ${e.message}`
    return
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    bulkEditError.value = '请提供 JSON 对象（键值对），不接受数组或基本类型'
    return
  }

  // 替换 rows，保留每条的类型推断
  rows.value = Object.entries(parsed).map(([key, value]) => {
    let typeName = typeof value
    let strValue = value
    if (Array.isArray(value)) {
      typeName = 'array'
      strValue = JSON.stringify(value)
    } else if (typeName === 'object' && value !== null) {
      typeName = 'object'
      strValue = JSON.stringify(value)
    } else {
      strValue = String(value)
    }
    return {
      key: String(key),
      value: strValue,
      type: typeName === 'undefined' ? 'string' : typeName,
      description: ''
    }
  })

  ensureTrailingEmptyRow()
  bulkEditVisible.value = false
  bulkEditError.value = ''
  // 等下一帧 emit，避免输入框焦点状态干扰
  nextTick(updateModel)
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

/* 批量编辑对话框 */
.bulk-edit-tips {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  line-height: 1.6;
}

.bulk-edit-tips code {
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: #606266;
}

.bulk-edit-textarea :deep(.el-textarea__inner) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
}

.bulk-edit-error {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #f56c6c;
}
</style>
