<template>
  <div class="json-editor">
    <el-input
      v-model="jsonText"
      type="textarea"
      :autosize="false"
      :placeholder="placeholder"
      @blur="handleBlur"
      @input="handleInput"
      spellcheck="false"
    />
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: [Object, Array],
    default: () => ({})
  },
  placeholder: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const jsonText = ref('')
const error = ref('')
let inputTimer = null

// 初始化
watch(() => props.modelValue, (newVal) => {
  try {
    jsonText.value = JSON.stringify(newVal, null, 2)
    error.value = ''
  } catch (e) {
    jsonText.value = ''
  }
}, { immediate: true })

// 输入时延迟验证（防抖）
const handleInput = () => {
  if (inputTimer) {
    clearTimeout(inputTimer)
  }
  
  inputTimer = setTimeout(() => {
    tryParseAndEmit()
  }, 500) // 500ms 延迟
}

// 失焦时立即验证并更新
const handleBlur = () => {
  if (inputTimer) {
    clearTimeout(inputTimer)
  }
  tryParseAndEmit()
}

// 尝试解析并发送更新
const tryParseAndEmit = () => {
  if (!jsonText.value.trim()) {
    emit('update:modelValue', {})
    error.value = ''
    return
  }
  
  try {
    const parsed = JSON.parse(jsonText.value)
    emit('update:modelValue', parsed)
    error.value = ''
  } catch (e) {
    error.value = 'JSON 格式错误: ' + e.message
  }
}
</script>

<style scoped>
.json-editor {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.error-message {
  color: #f56c6c;
  font-size: 12px;
  margin-top: 5px;
  flex-shrink: 0;
}

:deep(.el-textarea) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:deep(.el-textarea__inner) {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  flex: 1;
  resize: none;
  min-height: 0;
}
</style>
