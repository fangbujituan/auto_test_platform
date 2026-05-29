<template>
  <el-dialog
    v-model="visible"
    title="批量导入"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="import-section">
      <div class="section-label">导入格式</div>
      <el-radio-group v-model="importFormat">
        <el-radio-button value="swagger">Swagger</el-radio-button>
      </el-radio-group>
    </div>

    <div class="import-section">
      <div class="section-label">导入方式</div>
      <el-radio-group v-model="importMethod">
        <el-radio-button value="file">附件</el-radio-button>
        <el-radio-button value="url">连接</el-radio-button>
      </el-radio-group>
    </div>

    <div class="import-section">
      <div class="section-label">导入内容</div>
      <div v-if="importMethod === 'file'" class="import-content-area">
        <el-upload
          ref="uploadRef"
          drag
          accept=".json,.yaml,.yml"
          :limit="1"
          :auto-upload="false"
          :before-upload="beforeUpload"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          :file-list="fileList"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 .json、.yaml、.yml 格式，文件大小不超过 10MB
            </div>
          </template>
        </el-upload>
        <div v-if="parsedFileName" class="parsed-file-info">
          <el-icon><SuccessFilled /></el-icon>
          <span>{{ parsedFileName }} 解析成功</span>
        </div>
      </div>
      <div v-else class="import-content-url">
        <el-input
          v-model="swaggerUrl"
          placeholder="请输入 Swagger 文档 URL 地址"
          clearable
          @clear="errorMessage = ''"
        />
      </div>
    </div>

    <div v-if="errorMessage" class="error-message">
      {{ errorMessage }}
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="loading">
        确认导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, SuccessFilled } from '@element-plus/icons-vue'
import yaml from 'js-yaml'
import { fetchSwaggerUrl, importSwagger } from '../api/apiImport'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: Number, required: true }
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = ref(false)
const importFormat = ref('swagger')
const importMethod = ref('file')
const fileList = ref([])
const swaggerUrl = ref('')
const loading = ref(false)
const errorMessage = ref('')
const parsedData = ref(null)
const parsedFileName = ref('')
const uploadRef = ref(null)

watch(() => props.modelValue, (val) => { visible.value = val })
watch(visible, (val) => { emit('update:modelValue', val) })

const resetForm = () => {
  importFormat.value = 'swagger'
  importMethod.value = 'file'
  fileList.value = []
  swaggerUrl.value = ''
  loading.value = false
  errorMessage.value = ''
  parsedData.value = null
  parsedFileName.value = ''
}

const handleClose = () => {
  resetForm()
}

const beforeUpload = (file) => {
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  return true
}

const validateSwaggerData = (data) => {
  if (!data || typeof data !== 'object') return false
  const hasVersion = ('swagger' in data) || ('openapi' in data)
  const hasPaths = 'paths' in data
  return hasVersion && hasPaths
}

const handleFileChange = (uploadFile) => {
  errorMessage.value = ''
  parsedData.value = null
  parsedFileName.value = ''

  const rawFile = uploadFile.raw
  if (!rawFile) return

  // Check file size
  if (rawFile.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    fileList.value = []
    return
  }

  const fileName = rawFile.name.toLowerCase()
  const reader = new FileReader()

  reader.onload = (e) => {
    const content = e.target.result
    let parsed = null

    try {
      if (fileName.endsWith('.json')) {
        parsed = JSON.parse(content)
      } else if (fileName.endsWith('.yaml') || fileName.endsWith('.yml')) {
        parsed = yaml.load(content)
      } else {
        errorMessage.value = '文件解析失败，请检查文件内容'
        fileList.value = []
        return
      }
    } catch {
      errorMessage.value = '文件解析失败，请检查文件内容'
      fileList.value = []
      return
    }

    if (!validateSwaggerData(parsed)) {
      errorMessage.value = '文件格式不正确，请上传有效的 Swagger/OpenAPI 文档'
      fileList.value = []
      return
    }

    parsedData.value = parsed
    parsedFileName.value = rawFile.name
    errorMessage.value = ''
  }

  reader.onerror = () => {
    errorMessage.value = '文件解析失败，请检查文件内容'
    fileList.value = []
  }

  reader.readAsText(rawFile)
}

const handleFileRemove = () => {
  parsedData.value = null
  parsedFileName.value = ''
  errorMessage.value = ''
}

const validateUrl = (url) => {
  return /^https?:\/\/.+/.test(url)
}

const handleConfirm = async () => {
  errorMessage.value = ''

  if (importMethod.value === 'file') {
    if (!parsedData.value) {
      errorMessage.value = '请先选择文件'
      return
    }
  } else if (importMethod.value === 'url') {
    if (!swaggerUrl.value || !swaggerUrl.value.trim()) {
      errorMessage.value = '请输入 Swagger 文档 URL 地址'
      return
    }
    if (!validateUrl(swaggerUrl.value.trim())) {
      errorMessage.value = '请输入有效的 URL 地址'
      return
    }

    loading.value = true
    try {
      const res = await fetchSwaggerUrl(props.projectId, { url: swaggerUrl.value.trim() })
      if (res.code === 0) {
        parsedData.value = res.data
      } else {
        errorMessage.value = res.message || '获取 Swagger 文档失败，请检查 URL 是否可访问'
        loading.value = false
        return
      }
    } catch {
      errorMessage.value = '获取 Swagger 文档失败，请检查 URL 是否可访问'
      loading.value = false
      return
    }
  }

  // 调用 importSwagger 执行批量导入
  loading.value = true
  try {
    const res = await importSwagger(props.projectId, {
      swagger_data: parsedData.value,
      folder_id: null
    })
    if (res.code === 0) {
      const createdCount = (res.data && res.data.created_count) || 0
      ElMessage.success(`导入成功，共导入 ${createdCount} 个接口`)
      visible.value = false
      emit('success')
    } else {
      errorMessage.value = res.message || '导入失败，请稍后重试'
    }
  } catch {
    errorMessage.value = '导入失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.import-section {
  margin-bottom: 20px;
}

.section-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
}

.import-content-area {
  margin-top: 4px;
}

.import-content-url {
  margin-top: 4px;
}

.import-content-url .el-input {
  width: 100%;
}

.parsed-file-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: #67c23a;
  font-size: 13px;
}

.error-message {
  color: #f56c6c;
  font-size: 13px;
  margin-top: 8px;
}
</style>
