<template>
  <div class="api-detail-new">
    <!-- 请求行：统一容器 -->
    <div class="api-request-bar">
      <div class="url-container">
        <el-select
          v-model="editableApi.method"
          class="method-select"
          :class="`method-select-${editableApi.method.toLowerCase()}`"
          size="large"
        >
          <el-option label="GET" value="GET"><span class="method-option method-get">GET</span></el-option>
          <el-option label="POST" value="POST"><span class="method-option method-post">POST</span></el-option>
          <el-option label="PUT" value="PUT"><span class="method-option method-put">PUT</span></el-option>
          <el-option label="DELETE" value="DELETE"><span class="method-option method-delete">DELETE</span></el-option>
          <el-option label="PATCH" value="PATCH"><span class="method-option method-patch">PATCH</span></el-option>
        </el-select>
        <span class="url-divider"></span>
        <el-select
          v-if="prefixUrlOptions.length > 0 && !editableApi.base_url"
          v-model="selectedPrefixUrlId"
          class="prefix-url-select"
          :style="{ width: prefixSelectWidth }"
          placeholder="选择前置URL"
          clearable
          @change="handlePrefixUrlChange"
        >
          <template #prefix>
            <span class="prefix-url-hint">环境</span>
          </template>
          <el-option
            v-for="item in prefixUrlOptions"
            :key="item.id"
            :label="item.url"
            :value="item.id"
          >
            <div class="prefix-url-option">
              <span class="prefix-url-value">{{ item.url || '未设置前置 URL' }}</span>
              <span class="prefix-url-label">{{ item.module }} / {{ item.service }}</span>
            </div>
          </el-option>
        </el-select>
        <input
          v-else
          v-model="editableApi.base_url"
          placeholder="基础URL"
          class="url-segment base-url"
          spellcheck="false"
        />
        <input
          v-model="editableApi.path"
          placeholder="/接口路径"
          class="url-segment path-url"
          spellcheck="false"
        />
      </div>
      <button class="glass-send-btn" :class="{ 'is-loading': testing }" @click="$emit('send')" :disabled="testing">
        <span class="glass-send-inner">
          <el-icon v-if="!testing"><VideoPlay /></el-icon>
          <el-icon v-else class="is-loading-icon"><Loading /></el-icon>
          <span>发送</span>
        </span>
      </button>
      <el-button size="large" @click="$emit('save')" :loading="saving">
        <el-icon><Select /></el-icon> 保存
      </el-button>
    </div>

    <!-- 接口名称 + 目录 + 时间 + 状态 -->
    <div class="api-meta-line">
      <el-input v-model="editableApi.name" placeholder="请输入接口名称" class="api-name-input" spellcheck="false" />
      <span class="meta-separator">|</span>
      <el-tree-select
        :model-value="folderId"
        @update:model-value="(val) => $emit('update:folderId', val)"
        :data="folderOptions"
        :props="{ label: 'label', children: 'children', value: 'value' }"
        placeholder="未分类"
        clearable
        check-strictly
        :render-after-expand="false"
        size="small"
        class="folder-select"
        popper-class="folder-select-popper"
      >
        <template #prefix>
          <el-icon><FolderOpened /></el-icon>
        </template>
      </el-tree-select>
      <template v-if="apiData?.created_at">
        <span class="meta-separator">|</span>
        <span class="meta-info"><el-icon><Clock /></el-icon>创建 <span class="meta-value">{{ apiData.created_at }}</span></span>
      </template>
      <template v-if="apiData?.updated_at">
        <span class="meta-separator">|</span>
        <span class="meta-info"><el-icon><RefreshRight /></el-icon>修改 <span class="meta-value">{{ apiData.updated_at }}</span></span>
      </template>
      <span class="meta-separator">|</span>
      <span
        class="status-badge"
        :class="statusConfig.class"
        @click="toggleStatus"
      >
        <span class="status-indicator"></span>
        {{ statusConfig.label }}
      </span>
    </div>

    <!-- 接口描述 -->
    <div class="api-desc-line">
      <div class="desc-toggle" @click="descExpanded = !descExpanded">
        <el-icon class="desc-arrow" :class="{ expanded: descExpanded }"><ArrowRight /></el-icon>
        <span class="desc-label">描述</span>
        <span class="desc-divider"></span>
      </div>
      <div v-if="descExpanded" class="desc-content">
        <el-input v-model="editableApi.description" placeholder="请输入接口描述" type="textarea" :rows="2" resize="none" spellcheck="false" />
      </div>
    </div>

    <!-- 请求参数 -->
    <div class="api-params-section" :style="{ flexBasis: requestHeight + 'px', flexGrow: 0, flexShrink: 0 }">
      <el-tabs v-model="activeRequestTab" class="request-tabs">
        <el-tab-pane label="Params" name="params">
          <key-value-editor ref="paramsEditorRef" v-model="editableApi.params" />
        </el-tab-pane>
        <el-tab-pane label="Headers" name="headers">
          <key-value-editor ref="headersEditorRef" v-model="editableApi.headers" />
        </el-tab-pane>
        <el-tab-pane label="Body" name="body">
          <div class="body-type-selector">
            <el-radio-group v-model="editableApi.body_type" size="small">
              <el-radio label="json">JSON</el-radio>
              <el-radio label="form">Form</el-radio>
              <el-radio label="raw">Raw</el-radio>
            </el-radio-group>
          </div>
          <key-value-editor v-if="editableApi.body_type === 'form'" ref="bodyFormEditorRef" v-model="editableApi.body" />
          <json-editor v-else v-model="editableApi.body" placeholder='{"key": "value"}' />
        </el-tab-pane>
        <el-tab-pane label="前置脚本" name="pre-script" disabled>
          <el-empty description="功能开发中..." :image-size="60" />
        </el-tab-pane>
        <el-tab-pane label="后置脚本" name="post-script" disabled>
          <el-empty description="功能开发中..." :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 可拖拽分割条 -->
    <div class="resize-handle" @mousedown="onResizeStart">
      <div class="resize-handle-bar"></div>
    </div>

    <!-- 响应结果 -->
    <div class="api-response-section">
      <div class="response-header">
        <span class="response-title">响应结果</span>
        <el-tag :type="getStatusCodeType(responseData.statusCode)" size="large" class="status-code-tag">
          {{ responseData.statusCode || 200 }}
        </el-tag>
      </div>
      <div class="response-content">
        <el-tabs v-model="activeResponseTab" class="response-tabs">
          <el-tab-pane label="Body" name="body">
            <div v-if="responseData.body" class="response-body">
              <pre class="json-view json-highlighted" v-html="highlightJson(responseData.bodyRaw || responseData.body)"></pre>
            </div>
            <el-empty v-else description="暂无响应数据，点击发送按钮测试接口" :image-size="80" />
          </el-tab-pane>
          <el-tab-pane label="Headers" name="headers">
            <div v-if="responseData.headers" class="response-headers">
              <pre class="json-view">{{ JSON.stringify(responseData.headers, null, 2) }}</pre>
            </div>
            <el-empty v-else description="暂无响应头数据" :image-size="80" />
          </el-tab-pane>
          <el-tab-pane label="Info" name="info">
            <div v-if="responseData.info || responseData.body" class="response-info">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="状态码">
                  <el-tag :type="getStatusCodeType(responseData.statusCode)" size="small">{{ responseData.statusCode }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="耗时">{{ responseData.duration || '-' }}</el-descriptions-item>
                <el-descriptions-item label="响应大小">{{ formatSize(responseData.size) }}</el-descriptions-item>
                <el-descriptions-item label="时间">{{ responseData.timestamp || '-' }}</el-descriptions-item>
                <el-descriptions-item label="请求方式" :span="2">
                  <el-tag :type="getMethodTagType(responseData.requestInfo?.method)" size="small">
                    {{ responseData.requestInfo?.method || editableApi.method }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="完整URL" :span="2">
                  <span class="info-url">{{ responseData.requestInfo?.url || buildFullUrl() }}</span>
                </el-descriptions-item>
              </el-descriptions>

              <div class="info-block" v-if="responseData.requestInfo?.headers && Object.keys(responseData.requestInfo.headers).length">
                <div class="info-block-title">请求 Headers</div>
                <pre class="json-view">{{ JSON.stringify(responseData.requestInfo.headers, null, 2) }}</pre>
              </div>
              <div class="info-block" v-if="responseData.requestInfo?.params && Object.keys(responseData.requestInfo.params).length">
                <div class="info-block-title">请求参数 (Params)</div>
                <pre class="json-view">{{ JSON.stringify(responseData.requestInfo.params, null, 2) }}</pre>
              </div>
              <div class="info-block" v-if="responseData.requestInfo?.body && Object.keys(responseData.requestInfo.body).length">
                <div class="info-block-title">请求体 (Body)</div>
                <pre class="json-view">{{ JSON.stringify(responseData.requestInfo.body, null, 2) }}</pre>
              </div>
            </div>
            <el-empty v-else description="暂无响应信息" :image-size="80" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { VideoPlay, Select, FolderOpened, Clock, RefreshRight, ArrowRight, Loading } from '@element-plus/icons-vue'
import KeyValueEditor from './KeyValueEditor.vue'
import JsonEditor from './JsonEditor.vue'

const props = defineProps({
  editableApi: { type: Object, required: true },
  responseData: { type: Object, required: true },
  testing: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  folderId: { type: [Number, String], default: null },
  folderOptions: { type: Array, default: () => [] },
  apiData: { type: Object, default: null },
  prefixUrls: { type: Array, default: () => [] }
})

defineEmits(['send', 'save', 'update:folderId'])

// 前置 URL 下拉选项
const prefixUrlOptions = computed(() => {
  return props.prefixUrls || []
})

// 当前选中的前置 URL ID（从 apiData 回显持久化的绑定）
const selectedPrefixUrlId = ref(null)

// 初始化时回显已绑定的前置 URL
watch(() => props.apiData, (apiData) => {
  if (apiData && apiData.prefix_url_id) {
    selectedPrefixUrlId.value = apiData.prefix_url_id
  } else {
    selectedPrefixUrlId.value = null
  }
}, { immediate: true })

// 选中的前置 URL 对象
const selectedPrefixUrl = computed(() => {
  if (!selectedPrefixUrlId.value) return null
  return prefixUrlOptions.value.find(p => p.id === selectedPrefixUrlId.value) || null
})

// 根据选中的 URL 文本长度自适应宽度
const prefixSelectWidth = computed(() => {
  const url = selectedPrefixUrl.value?.url || ''
  if (!url) return '160px'
  // 每个字符约 8px，加上 padding 和图标空间
  const charWidth = Math.max(url.length * 7.5, 100)
  return Math.min(charWidth + 80, 400) + 'px'
})

const handlePrefixUrlChange = (id) => {
  selectedPrefixUrlId.value = id
  // 同步到 editableApi 以便保存时能拿到
  props.editableApi.prefix_url_id = id || null
}

// 用于 Info 面板和 buildFullUrl 的解析
const resolvedBaseUrl = computed(() => {
  if (props.editableApi.base_url) return props.editableApi.base_url
  if (selectedPrefixUrl.value?.url) return selectedPrefixUrl.value.url
  return ''
})

const activeRequestTab = ref('params')
const activeResponseTab = ref('body')
const descExpanded = ref(false)
const paramsEditorRef = ref(null)
const headersEditorRef = ref(null)
const bodyFormEditorRef = ref(null)

// 切换接口时，如果 body 有值则自动定位到 Body 页签
watch(() => props.apiData, () => {
  const body = props.editableApi?.body
  const hasBody = body && typeof body === 'object'
    ? Object.keys(body).length > 0
    : !!body
  activeRequestTab.value = hasBody ? 'body' : 'params'
}, { immediate: true })

// ── 可拖拽分割 ──
const requestHeight = ref(280)
const MIN_REQUEST_HEIGHT = 120
const MIN_RESPONSE_HEIGHT = 120
let startY = 0
let startHeight = 0

const onResizeStart = (e) => {
  e.preventDefault()
  startY = e.clientY
  startHeight = requestHeight.value
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

const onResizeMove = (e) => {
  const delta = e.clientY - startY
  const container = document.querySelector('.api-detail-new')
  if (!container) return
  const maxHeight = container.clientHeight - MIN_RESPONSE_HEIGHT - 200 // 留出顶部固定区域
  const newHeight = Math.max(MIN_REQUEST_HEIGHT, Math.min(startHeight + delta, maxHeight))
  requestHeight.value = newHeight
}

const onResizeEnd = () => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})

// 状态配置
const STATUS_MAP = {
  1: { label: '启用', class: 'status-enabled' },
  0: { label: '禁用', class: 'status-disabled' }
}

const statusConfig = computed(() => {
  return STATUS_MAP[props.editableApi.status] || STATUS_MAP[1]
})

const toggleStatus = () => {
  props.editableApi.status = props.editableApi.status === 1 ? 0 : 1
}

const getStatusCodeType = (code) => {
  if (code >= 200 && code < 300) return 'success'
  if (code >= 300 && code < 400) return 'info'
  if (code >= 400 && code < 500) return 'warning'
  if (code >= 500) return 'danger'
  return 'info'
}

const getMethodTagType = (method) => {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return map[method] || 'info'
}

const buildFullUrl = () => {
  const base = resolvedBaseUrl.value || ''
  const path = props.editableApi.path || ''
  if (!base && !path) return '-'
  if (base && !base.endsWith('/') && path && !path.startsWith('/')) return `${base}/${path}`
  return `${base}${path}`
}

const formatSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// ── JSON 语法高亮（浏览器 DevTools 风格）──
const escapeHtml = (str) => {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// 格式化 JSON 字符串，保持原始 key 顺序（不经过 parse → stringify）
const formatJsonPreserveOrder = (jsonStr) => {
  let result = ''
  let indent = 0
  let inString = false
  let escaped = false
  const INDENT = '  '

  for (let i = 0; i < jsonStr.length; i++) {
    const ch = jsonStr[i]

    if (escaped) {
      result += ch
      escaped = false
      continue
    }

    if (ch === '\\' && inString) {
      result += ch
      escaped = true
      continue
    }

    if (ch === '"') {
      inString = !inString
      result += ch
      continue
    }

    if (inString) {
      result += ch
      continue
    }

    // 跳过原始空白
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') continue

    if (ch === '{' || ch === '[') {
      result += ch
      // 向前看是否紧跟关闭符
      let next = i + 1
      while (next < jsonStr.length && /\s/.test(jsonStr[next])) next++
      if ((ch === '{' && jsonStr[next] === '}') || (ch === '[' && jsonStr[next] === ']')) {
        result += ch === '{' ? '}' : ']'
        i = next
        continue
      }
      indent++
      result += '\n' + INDENT.repeat(indent)
    } else if (ch === '}' || ch === ']') {
      indent--
      result += '\n' + INDENT.repeat(indent) + ch
    } else if (ch === ',') {
      result += ',\n' + INDENT.repeat(indent)
    } else if (ch === ':') {
      result += ': '
    } else {
      result += ch
    }
  }
  return result
}

const highlightJson = (body) => {
  let raw
  if (typeof body === 'string') {
    // 优先使用原始文本，仅做缩进格式化（保持字段顺序）
    try {
      // 用 JSON.parse 的 reviver 无法保序，所以直接用正则缩进原始文本
      // 先验证是合法 JSON，再手动格式化保持原始 key 顺序
      JSON.parse(body) // 仅验证
      raw = formatJsonPreserveOrder(body)
    } catch {
      return escapeHtml(body)
    }
  } else if (typeof body === 'object') {
    // 已经被 parse 过的对象，只能用 stringify（顺序可能已变）
    raw = JSON.stringify(body, null, 2)
  } else {
    return escapeHtml(String(body))
  }

  // 逐行着色，避免跨 token 误匹配
  return raw.split('\n').map(line => {
    // key: string value
    if (/^\s*".*":\s*"/.test(line)) {
      return line.replace(
        /^(\s*)("(?:\\.|[^"\\])*")(\s*:\s*)("(?:\\.|[^"\\])*")(,?)$/,
        '$1<span class="json-key">$2</span>$3<span class="json-string">$4</span>$5'
      )
    }
    // key: number value
    if (/^\s*".*":\s*-?\d/.test(line)) {
      return line.replace(
        /^(\s*)("(?:\\.|[^"\\])*")(\s*:\s*)(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(,?)$/,
        '$1<span class="json-key">$2</span>$3<span class="json-number">$4</span>$5'
      )
    }
    // key: boolean
    if (/^\s*".*":\s*(true|false)/.test(line)) {
      return line.replace(
        /^(\s*)("(?:\\.|[^"\\])*")(\s*:\s*)(true|false)(,?)$/,
        '$1<span class="json-key">$2</span>$3<span class="json-boolean">$4</span>$5'
      )
    }
    // key: null
    if (/^\s*".*":\s*null/.test(line)) {
      return line.replace(
        /^(\s*)("(?:\\.|[^"\\])*")(\s*:\s*)(null)(,?)$/,
        '$1<span class="json-key">$2</span>$3<span class="json-null">$4</span>$5'
      )
    }
    // key: object/array (只高亮 key)
    if (/^\s*".*":\s*[\[{]/.test(line)) {
      return line.replace(
        /^(\s*)("(?:\\.|[^"\\])*")(\s*:\s*)/,
        '$1<span class="json-key">$2</span>$3'
      )
    }
    // 数组中的纯 string 值
    if (/^\s*"(?:\\.|[^"\\])*"\s*,?\s*$/.test(line) && !/^\s*".*"\s*:/.test(line)) {
      return line.replace(
        /^(\s*)("(?:\\.|[^"\\])*")(,?)$/,
        '$1<span class="json-string">$2</span>$3'
      )
    }
    // 数组中的纯 number
    if (/^\s*-?\d+/.test(line)) {
      return line.replace(
        /^(\s*)(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(,?)$/,
        '$1<span class="json-number">$2</span>$3'
      )
    }
    // 数组中的 boolean / null
    line = line.replace(/^(\s*)(true|false)(,?)$/, '$1<span class="json-boolean">$2</span>$3')
    line = line.replace(/^(\s*)(null)(,?)$/, '$1<span class="json-null">$2</span>$3')
    return line
  }).join('\n')
}

const formatResponseBody = (body) => {
  if (typeof body === 'string') {
    try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
  } else if (typeof body === 'object') {
    return JSON.stringify(body, null, 2)
  }
  return String(body)
}

const resetEditors = () => {
  if (paramsEditorRef.value) paramsEditorRef.value.resetInitialization()
  if (headersEditorRef.value) headersEditorRef.value.resetInitialization()
  if (bodyFormEditorRef.value) bodyFormEditorRef.value.resetInitialization()
}

defineExpose({ resetEditors })
</script>

<style scoped>
.api-detail-new {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
  gap: 12px;
}

.api-request-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.url-container {
  display: flex;
  align-items: center;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  height: 40px;
  flex: 1;
  overflow: hidden;
  transition: border-color 0.2s;
}

.url-container:focus-within {
  border-color: #409eff;
}

.method-select {
  width: 110px;
  flex-shrink: 0;
}

:deep(.method-select .el-input__wrapper) {
  box-shadow: none !important;
  background: transparent !important;
  border: none !important;
  border-radius: 0;
  padding-left: 12px;
}

.url-divider {
  width: 1px;
  height: 20px;
  background: #dcdfe6;
  flex-shrink: 0;
}

.url-segment {
  border: none;
  outline: none;
  background: transparent;
  height: 100%;
  font-size: 14px;
  color: #303133;
  padding: 0 10px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.url-segment::placeholder {
  color: #c0c4cc;
}

.base-url {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px dashed #dcdfe6;
}

/* 前置 URL 下拉选择器 */
.prefix-url-select {
  flex-shrink: 0;
  border-right: 1px dashed #dcdfe6;
  min-width: 140px;
  max-width: 400px;
}

:deep(.prefix-url-select .el-input__wrapper) {
  box-shadow: none !important;
  background: transparent !important;
  border: none !important;
  border-radius: 0;
  height: 100%;
}

:deep(.prefix-url-select .el-input__inner) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  color: #409eff;
}

:deep(.prefix-url-select .el-select__suffix) {
  margin-right: 4px;
}

.prefix-url-hint {
  font-size: 11px;
  color: #909399;
  background: #f0f2f5;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}

.prefix-url-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 16px;
}

.prefix-url-value {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  color: #303133;
}

.prefix-url-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  flex-shrink: 0;
}

.path-url {
  flex: 1;
  min-width: 0;
}

.api-meta-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.api-name-input { width: auto; min-width: 120px; max-width: 260px; }

.folder-select {
  width: auto;
  min-width: 160px;
  flex-shrink: 0;
}

/* 目录选择器：彻底去掉边框和背景框 */
:deep(.folder-select .el-input__wrapper) {
  box-shadow: none !important;
  background: transparent !important;
  border: none !important;
  outline: none !important;
  padding: 0 2px;
}

:deep(.folder-select .el-input__wrapper:hover) {
  background: transparent !important;
}

:deep(.folder-select .el-input__inner) {
  font-size: 14px;
  color: #606266;
}

:deep(.folder-select .el-input__prefix .el-icon) {
  color: #409eff;
}

:deep(.folder-select .el-select__suffix) {
  display: none;
}

/* 接口名：去掉下划线，纯文本风格 */
:deep(.api-name-input .el-input__wrapper) {
  box-shadow: none !important;
  background: transparent;
  padding-left: 0;
  border-radius: 0;
}

:deep(.api-name-input .el-input__wrapper:hover) {
  background: #f5f7fa;
  border-radius: 4px;
}

:deep(.api-name-input .el-input__wrapper.is-focus) {
  background: #f5f7fa;
  border-radius: 4px;
}

:deep(.api-name-input .el-input__inner) {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.meta-separator {
  color: #dcdfe6;
  font-size: 14px;
  user-select: none;
}

.meta-info {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 14px;
  color: #909399;
  white-space: nowrap;
}

.meta-info .el-icon {
  font-size: 14px;
  color: #909399;
}

.meta-value {
  color: #000;
  font-weight: 700;
}

/* 状态标识 */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  padding: 2px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  white-space: nowrap;
}

.status-badge .status-indicator {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-badge.status-enabled {
  color: #67c23a;
  background: #f0f9eb;
}

.status-badge.status-enabled .status-indicator {
  background: #67c23a;
}

.status-badge.status-enabled:hover {
  background: #e1f3d8;
}

.status-badge.status-disabled {
  color: #f56c6c;
  background: #fef0f0;
}

.status-badge.status-disabled .status-indicator {
  background: #f56c6c;
}

.status-badge.status-disabled:hover {
  background: #fde2e2;
}

.api-desc-line { flex-shrink: 0; }

.desc-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  height: 28px;
}

.desc-arrow {
  font-size: 12px;
  color: #909399;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.desc-arrow.expanded {
  transform: rotate(90deg);
}

.desc-label {
  font-size: 13px;
  color: #909399;
  flex-shrink: 0;
  white-space: nowrap;
}

.desc-divider {
  flex: 1;
  height: 1px;
  background: #e4e7ed;
}

.desc-content {
  margin-top: 8px;
}

.method-option { font-weight: 600; }
.method-get { color: #67c23a; }
.method-post { color: #409eff; }
.method-put { color: #e6a23c; }
.method-delete { color: #f56c6c; }
.method-patch { color: #909399; }

:deep(.method-select .el-input__inner),
:deep(.method-select .el-select__selected-item),
:deep(.method-select .el-select__placeholder) { font-weight: 600 !important; }

:deep(.method-select-get .el-input__inner),
:deep(.method-select-get .el-select__selected-item),
:deep(.method-select-get .el-select__placeholder) { color: #67c23a !important; }

:deep(.method-select-post .el-input__inner),
:deep(.method-select-post .el-select__selected-item),
:deep(.method-select-post .el-select__placeholder) { color: #409eff !important; }

:deep(.method-select-put .el-input__inner),
:deep(.method-select-put .el-select__selected-item),
:deep(.method-select-put .el-select__placeholder) { color: #e6a23c !important; }

:deep(.method-select-delete .el-input__inner),
:deep(.method-select-delete .el-select__selected-item),
:deep(.method-select-delete .el-select__placeholder) { color: #f56c6c !important; }

:deep(.method-select-patch .el-input__inner),
:deep(.method-select-patch .el-select__selected-item),
:deep(.method-select-patch .el-select__placeholder) { color: #909399 !important; }

.api-params-section {
  min-height: 120px; display: flex; flex-direction: column;
  border: 1px solid #e4e7ed; border-radius: 4px; overflow: hidden;
}

.request-tabs {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}
.request-tabs :deep(.el-tabs__header) { padding-left: 12px; flex-shrink: 0; }
.request-tabs :deep(.el-tabs__content) { flex: 1; overflow: auto; padding: 12px; display: flex; flex-direction: column; }
.request-tabs :deep(.el-tab-pane) { flex: 1; display: flex; flex-direction: column; min-height: 0; }

.body-type-selector { margin-bottom: 12px; flex-shrink: 0; }

/* 可拖拽分割条 */
.resize-handle {
  flex-shrink: 0;
  height: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: row-resize;
  user-select: none;
  position: relative;
  z-index: 1;
}

.resize-handle:hover .resize-handle-bar,
.resize-handle:active .resize-handle-bar {
  background: #409eff;
  width: 60px;
}

.resize-handle-bar {
  width: 36px;
  height: 3px;
  border-radius: 2px;
  background: #dcdfe6;
  transition: all 0.2s;
}

.api-response-section {
  flex: 1; min-height: 0; display: flex; flex-direction: column;
  border: 1px solid #e4e7ed; border-radius: 4px; overflow: hidden;
}

.response-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #f5f7fa; border-bottom: 1px solid #e4e7ed;
}
.response-title { font-size: 14px; font-weight: 600; color: #303133; }
.status-code-tag { font-size: 14px; font-weight: 600; }

.response-content {
  flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden;
}
.response-tabs {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}
.response-tabs :deep(.el-tabs__header) { padding-left: 12px; }
.response-tabs :deep(.el-tabs__content) { flex: 1; overflow: auto; padding: 12px; display: flex; flex-direction: column; }
.response-tabs :deep(.el-tab-pane) { flex: 1; display: flex; flex-direction: column; min-height: 0; }

.response-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.response-headers {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.json-view {
  background: #f5f7fa; padding: 12px; border-radius: 4px;
  font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.6;
  color: #303133; flex: 1; overflow: auto; margin: 0;
  white-space: pre-wrap; word-break: break-all;
}

/* 浏览器 DevTools 风格 JSON 语法高亮 */
.json-highlighted :deep(.json-key) {
  color: #881391;
}
.json-highlighted :deep(.json-string) {
  color: #c41a16;
}
.json-highlighted :deep(.json-number) {
  color: #1c00cf;
}
.json-highlighted :deep(.json-boolean) {
  color: #0d22aa;
}
.json-highlighted :deep(.json-null) {
  color: #808080;
}

.info-url {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.info-block {
  margin-top: 12px;
}

.info-block-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 6px;
}

/* Apple Glassmorphism Send Button */
.glass-send-btn {
  position: relative;
  height: 40px;
  padding: 0 22px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  outline: none;
  flex-shrink: 0;
  /* 玻璃底色 */
  background: linear-gradient(135deg, rgba(60, 130, 246, 0.72), rgba(100, 160, 255, 0.60));
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  /* 内发光边框 */
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.45),
    inset 0 -1px 1px rgba(0, 0, 0, 0.08),
    0 2px 8px rgba(60, 130, 246, 0.30),
    0 0 0 0.5px rgba(255, 255, 255, 0.25);
  transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  overflow: hidden;
}

/* 顶部高光条 */
.glass-send-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: 10%;
  right: 10%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.7), transparent);
  border-radius: 50%;
}

/* 上半部分光泽 */
.glass-send-btn::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0.04) 100%);
  border-radius: 12px 12px 0 0;
  pointer-events: none;
}

.glass-send-inner {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.3px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
}

.glass-send-inner .el-icon {
  font-size: 16px;
}

/* Hover */
.glass-send-btn:hover {
  background: linear-gradient(135deg, rgba(60, 130, 246, 0.85), rgba(100, 160, 255, 0.75));
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.50),
    inset 0 -1px 1px rgba(0, 0, 0, 0.08),
    0 4px 16px rgba(60, 130, 246, 0.40),
    0 0 0 0.5px rgba(255, 255, 255, 0.30);
  transform: translateY(-0.5px);
}

/* Active / Press */
.glass-send-btn:active {
  background: linear-gradient(135deg, rgba(45, 110, 220, 0.80), rgba(80, 140, 240, 0.68));
  box-shadow:
    inset 0 2px 4px rgba(0, 0, 0, 0.15),
    inset 0 -1px 1px rgba(255, 255, 255, 0.10),
    0 1px 4px rgba(60, 130, 246, 0.25);
  transform: translateY(0.5px) scale(0.98);
}

/* Loading */
.glass-send-btn.is-loading {
  pointer-events: none;
  opacity: 0.78;
}

.is-loading-icon {
  animation: glass-spin 1s linear infinite;
}

@keyframes glass-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Disabled */
.glass-send-btn:disabled:not(.is-loading) {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
