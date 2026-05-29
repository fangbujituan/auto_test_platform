<template>
  <div class="json-viewer">
    <pre v-if="hasData">{{ formattedData }}</pre>
    <el-empty v-else description="暂无数据" :image-size="60" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: {
    type: [Object, Array, String, Number, Boolean],
    default: null
  }
})

const hasData = computed(() => {
  if (props.data === null || props.data === undefined) return false
  if (typeof props.data === 'object') {
    return Object.keys(props.data).length > 0
  }
  return true
})

const formattedData = computed(() => {
  try {
    if (typeof props.data === 'string') {
      return props.data
    }
    return JSON.stringify(props.data, null, 2)
  } catch (e) {
    return String(props.data)
  }
})
</script>

<style scoped>
.json-viewer {
  width: 100%;
  min-height: 100px;
}

pre {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 0;
  font-family: 'Courier New', Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  border: 1px solid #e4e7ed;
}
</style>
