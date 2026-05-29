<template>
  <el-dialog
    v-model="visible"
    title="导入cURL"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-input
      v-model="curlCommand"
      type="textarea"
      :rows="8"
      placeholder="粘贴cURL命令到此处"
      spellcheck="false"
      class="curl-input"
    />

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="loading">
        确认
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { parseCurl } from '../utils/curlParser'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: Number, required: true }
})

const emit = defineEmits(['update:modelValue', 'parsed'])

const visible = ref(false)
const curlCommand = ref('')
const loading = ref(false)

watch(() => props.modelValue, (val) => { visible.value = val })
watch(visible, (val) => { emit('update:modelValue', val) })

const handleClose = () => {
  curlCommand.value = ''
}

const handleConfirm = () => {
  if (!curlCommand.value.trim()) {
    ElMessage.warning('请输入cURL命令')
    return
  }
  loading.value = true
  try {
    const parsed = parseCurl(curlCommand.value)
    emit('parsed', parsed)
    visible.value = false
  } catch (e) {
    ElMessage.error(e.message || 'cURL 解析失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.curl-input :deep(.el-textarea__inner) {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Source Code Pro', Menlo, Consolas, monospace;
  font-variant-ligatures: common-ligatures;
  font-size: 13px;
  line-height: 1.7;
  letter-spacing: 0.3px;
  border-radius: 10px;
  padding: 14px 16px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  resize: none;
}

.curl-input :deep(.el-textarea__inner):focus {
  background: var(--el-bg-color);
}

.curl-input :deep(.el-textarea__inner)::placeholder {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}
</style>
