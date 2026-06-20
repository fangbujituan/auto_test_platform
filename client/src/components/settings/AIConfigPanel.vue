<template>
  <div class="ai-config-panel">
    <el-tabs v-model="activeTab">
      <!-- ==================== 提供商管理 Tab ==================== -->
      <el-tab-pane label="提供商管理" name="providers">
        <div class="tab-toolbar">
          <el-button type="primary" @click="showProviderDialog()">
            <el-icon><Plus /></el-icon>
            新增提供商
          </el-button>
        </div>

        <el-table :data="providers" v-loading="providerLoading" stripe style="width: 100%">
          <el-table-column prop="name" label="名称" min-width="120" />
          <el-table-column prop="provider_type" label="类型" width="140">
            <template #default="{ row }">
              {{ providerTypeLabel(row.provider_type) }}
            </template>
          </el-table-column>
          <el-table-column prop="model_name" label="模型" min-width="120" />
          <el-table-column prop="api_key_masked" label="API Key" min-width="140">
            <template #default="{ row }">
              <span class="masked-key">{{ row.api_key_masked || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
                {{ row.is_enabled ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="默认" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="showProviderDialog(row)">编辑</el-button>
              <el-button
                size="small"
                type="success"
                :loading="testingProviderId === row.id"
                @click="handleTestSaved(row)"
              >测试连接</el-button>
              <!-- <el-button
                size="small"
                type="warning"
                :disabled="row.is_default"
                @click="handleSetDefault(row)"
              >设为默认</el-button> -->
              <el-button size="small" type="danger" @click="handleDeleteProvider(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ==================== 提示词模板 Tab ==================== -->
      <el-tab-pane label="提示词模板" name="prompts">
        <div class="tab-toolbar">
          <el-button type="primary" @click="showPromptDialog()">
            <el-icon><Plus /></el-icon>
            新增模板
          </el-button>
        </div>

        <el-table :data="prompts" v-loading="promptLoading" stripe style="width: 100%">
          <el-table-column prop="name" label="名称" min-width="120" />
          <el-table-column prop="scene" label="场景标识" min-width="140" />
          <el-table-column prop="description" label="描述" min-width="160">
            <template #default="{ row }">
              {{ row.description || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="内置" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_builtin" type="info" size="small">内置</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="showPromptDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDeletePrompt(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ==================== 提供商 新增/编辑 对话框 ==================== -->
    <el-dialog
      v-model="providerDialogVisible"
      :title="isEditProvider ? '编辑提供商' : '新增提供商'"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="providerFormRef"
        :model="providerForm"
        :rules="providerRules"
        label-width="100px"
        autocomplete="off"
      >
        <!-- 防止浏览器把后面的 API Key 输入识别为登录密码：
             加一对一像素级隐藏的假账号 / 密码字段诱导浏览器自动填充到这里，
             保护真正的 API Key 输入框不弹"保存密码""使用已保存密码"提示。 -->
        <input
          type="text"
          name="fake_username_for_chrome"
          autocomplete="username"
          tabindex="-1"
          aria-hidden="true"
          class="autofill-decoy"
        />
        <input
          type="password"
          name="fake_password_for_chrome"
          autocomplete="new-password"
          tabindex="-1"
          aria-hidden="true"
          class="autofill-decoy"
        />

        <el-form-item label="名称" prop="name">
          <el-input v-model="providerForm.name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="类型" prop="provider_type">
          <el-select v-model="providerForm.provider_type" placeholder="请选择提供商类型" style="width: 100%">
            <el-option label="OpenAI 兼容" value="openai" />
            <el-option label="通义千问" value="dashscope" />
            <el-option label="Ollama 本地模型" value="ollama" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <!--
            说明：原本用 type=password + show-password，但浏览器会把它当成登录字段
            弹出"保存密码"/自动填充。这里改成 type=text + CSS text-security 模拟
            掩码，并通过 autocomplete=new-password 与上方诱饵字段彻底抑制弹窗。
          -->
          <el-input
            v-model="providerForm.api_key"
            type="text"
            :class="{ 'masked-input': !showApiKey }"
            :placeholder="isEditProvider ? '留空则不修改' : '请输入 API Key（Ollama 可为空）'"
            autocomplete="new-password"
            spellcheck="false"
            name="ai_provider_secret"
          >
            <template #suffix>
              <el-icon class="api-key-eye" @click="showApiKey = !showApiKey">
                <View v-if="showApiKey" />
                <Hide v-else />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="Base URL" prop="base_url">
          <el-input v-model="providerForm.base_url" placeholder="如 https://api.openai.com" />
        </el-form-item>
        <el-form-item label="模型名称" prop="model_name">
          <el-input v-model="providerForm.model_name" placeholder="如 gpt-4o、qwen-plus" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="providerForm.is_enabled" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="providerForm.is_default" />
        </el-form-item>
      </el-form>

      <!-- 对话框内测试连接 -->
      <div class="dialog-test-section">
        <el-button
          type="success"
          :loading="testingUnsaved"
          @click="handleTestUnsaved"
        >测试连接</el-button>
        <span v-if="unsavedTestResult" :class="['test-result', unsavedTestResult.success ? 'success' : 'fail']">
          {{ unsavedTestResult.message }}
        </span>
      </div>

      <template #footer>
        <el-button @click="providerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProvider" :loading="providerSubmitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- ==================== 提示词模板 新增/编辑 对话框 ==================== -->
    <el-dialog
      v-model="promptDialogVisible"
      :title="isEditPrompt ? '编辑提示词模板' : '新增提示词模板'"
      width="680px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="promptFormRef"
        :model="promptForm"
        :rules="promptRules"
        label-width="120px"
      >
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="promptForm.name" placeholder="请输入模板名称" />
        </el-form-item>
        <el-form-item label="场景标识" prop="scene">
          <el-input v-model="promptForm.scene" placeholder="如 test_case_generation" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="promptForm.description" placeholder="模板描述（可选）" />
        </el-form-item>
        <el-form-item label="系统提示词" prop="system_prompt">
          <el-input
            v-model="promptForm.system_prompt"
            type="textarea"
            :rows="5"
            placeholder="请输入系统提示词"
          />
        </el-form-item>
        <el-form-item label="用户提示词模板" prop="user_prompt_template">
          <el-input
            v-model="promptForm.user_prompt_template"
            type="textarea"
            :rows="5"
            placeholder="支持 {variable_name} 占位符"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="promptDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPrompt" :loading="promptSubmitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>


<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, View, Hide } from '@element-plus/icons-vue'
import {
  getProviders, createProvider, updateProvider, deleteProvider,
  testProvider, testProviderUnsaved, setDefaultProvider,
  getPrompts, createPrompt, updatePrompt, deletePrompt
} from '../../api/ai'

// ==================== 通用 ====================
const activeTab = ref('providers')
// API Key 输入框的"显示明文 / 隐藏密文"切换状态
const showApiKey = ref(false)

const providerTypeMap = {
  openai: 'OpenAI 兼容',
  dashscope: '通义千问',
  ollama: 'Ollama 本地模型'
}
const providerTypeLabel = (type) => providerTypeMap[type] || type

// ==================== 提供商管理 ====================
const providers = ref([])
const providerLoading = ref(false)
const providerDialogVisible = ref(false)
const isEditProvider = ref(false)
const providerSubmitting = ref(false)
const providerFormRef = ref(null)
const editingProviderId = ref(null)
const testingProviderId = ref(null)
const testingUnsaved = ref(false)
const unsavedTestResult = ref(null)

const providerForm = ref({
  name: '',
  provider_type: '',
  api_key: '',
  base_url: '',
  model_name: '',
  is_enabled: true,
  is_default: false
})

const urlValidator = (rule, value, callback) => {
  if (!value) return callback()
  try {
    new URL(value)
    callback()
  } catch {
    callback(new Error('请输入有效的 URL 地址'))
  }
}

const providerRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  provider_type: [{ required: true, message: '请选择提供商类型', trigger: 'change' }],
  base_url: [
    { required: true, message: '请输入 Base URL', trigger: 'blur' },
    { validator: urlValidator, trigger: 'blur' }
  ],
  model_name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }]
}

const loadProviders = async () => {
  providerLoading.value = true
  try {
    const res = await getProviders()
    providers.value = res.data || []
  } catch (error) {
    console.error('加载提供商列表失败:', error)
  } finally {
    providerLoading.value = false
  }
}

const showProviderDialog = (row) => {
  unsavedTestResult.value = null
  if (row) {
    isEditProvider.value = true
    editingProviderId.value = row.id
    providerForm.value = {
      name: row.name,
      provider_type: row.provider_type,
      api_key: '',
      base_url: row.base_url,
      model_name: row.model_name,
      is_enabled: row.is_enabled,
      is_default: row.is_default
    }
  } else {
    isEditProvider.value = false
    editingProviderId.value = null
    providerForm.value = {
      name: '',
      provider_type: '',
      api_key: '',
      base_url: '',
      model_name: '',
      is_enabled: true,
      is_default: false
    }
  }
  providerDialogVisible.value = true
}

const submitProvider = async () => {
  if (!providerFormRef.value) return
  await providerFormRef.value.validate(async (valid) => {
    if (!valid) return
    providerSubmitting.value = true
    try {
      const payload = { ...providerForm.value }
      // 编辑时如果 api_key 为空，不传该字段（保持原值）
      if (isEditProvider.value && !payload.api_key) {
        delete payload.api_key
      }

      if (isEditProvider.value) {
        await updateProvider(editingProviderId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createProvider(payload)
        ElMessage.success('创建成功')
      }
      providerDialogVisible.value = false
      loadProviders()
    } catch (error) {
      console.error('操作失败:', error)
    } finally {
      providerSubmitting.value = false
    }
  })
}

const handleDeleteProvider = (row) => {
  ElMessageBox.confirm(
    `确定要删除提供商"${row.name}"吗？删除后将无法恢复。`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteProvider(row.id)
      ElMessage.success('删除成功')
      loadProviders()
    } catch (error) {
      console.error('删除失败:', error)
    }
  }).catch(() => {})
}

const handleTestSaved = async (row) => {
  testingProviderId.value = row.id
  const timer = setTimeout(() => {
    testingProviderId.value = null
    ElMessage.error('连接超时，请检查网络和配置')
  }, 30000)

  try {
    const res = await testProvider(row.id)
    clearTimeout(timer)
    const result = res.data
    if (result.success) {
      ElMessage.success(`连接成功（延迟 ${result.latency_ms}ms）`)
    } else {
      ElMessage.error(result.message || '连接失败')
    }
  } catch (error) {
    clearTimeout(timer)
    console.error('测试连接失败:', error)
  } finally {
    testingProviderId.value = null
  }
}

const handleTestUnsaved = async () => {
  unsavedTestResult.value = null
  testingUnsaved.value = true
  const timer = setTimeout(() => {
    testingUnsaved.value = false
    unsavedTestResult.value = { success: false, message: '连接超时，请检查网络和配置' }
  }, 30000)

  try {
    const res = await testProviderUnsaved({
      provider_type: providerForm.value.provider_type,
      api_key: providerForm.value.api_key || null,
      base_url: providerForm.value.base_url,
      model_name: providerForm.value.model_name
    })
    clearTimeout(timer)
    const result = res.data
    unsavedTestResult.value = result
    if (result.success) {
      ElMessage.success(`连接成功（延迟 ${result.latency_ms}ms）`)
    } else {
      ElMessage.error(result.message || '连接失败')
    }
  } catch (error) {
    clearTimeout(timer)
    unsavedTestResult.value = { success: false, message: '测试请求失败' }
    console.error('测试连接失败:', error)
  } finally {
    testingUnsaved.value = false
  }
}

const handleSetDefault = async (row) => {
  try {
    await setDefaultProvider(row.id)
    ElMessage.success(`已将"${row.name}"设为默认提供商`)
    loadProviders()
  } catch (error) {
    console.error('设置默认失败:', error)
  }
}

// ==================== 提示词模板管理 ====================
const prompts = ref([])
const promptLoading = ref(false)
const promptDialogVisible = ref(false)
const isEditPrompt = ref(false)
const promptSubmitting = ref(false)
const promptFormRef = ref(null)
const editingPromptId = ref(null)

const promptForm = ref({
  name: '',
  scene: '',
  description: '',
  system_prompt: '',
  user_prompt_template: ''
})

const promptRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  scene: [{ required: true, message: '请输入场景标识', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }],
  user_prompt_template: [{ required: true, message: '请输入用户提示词模板', trigger: 'blur' }]
}

const loadPrompts = async () => {
  promptLoading.value = true
  try {
    const res = await getPrompts()
    prompts.value = res.data || []
  } catch (error) {
    console.error('加载提示词模板失败:', error)
  } finally {
    promptLoading.value = false
  }
}

const showPromptDialog = (row) => {
  if (row) {
    isEditPrompt.value = true
    editingPromptId.value = row.id
    promptForm.value = {
      name: row.name,
      scene: row.scene,
      description: row.description || '',
      system_prompt: row.system_prompt,
      user_prompt_template: row.user_prompt_template
    }
  } else {
    isEditPrompt.value = false
    editingPromptId.value = null
    promptForm.value = {
      name: '',
      scene: '',
      description: '',
      system_prompt: '',
      user_prompt_template: ''
    }
  }
  promptDialogVisible.value = true
}

const submitPrompt = async () => {
  if (!promptFormRef.value) return
  await promptFormRef.value.validate(async (valid) => {
    if (!valid) return
    promptSubmitting.value = true
    try {
      const payload = { ...promptForm.value }
      if (!payload.description) {
        payload.description = null
      }

      if (isEditPrompt.value) {
        await updatePrompt(editingPromptId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createPrompt(payload)
        ElMessage.success('创建成功')
      }
      promptDialogVisible.value = false
      loadPrompts()
    } catch (error) {
      console.error('操作失败:', error)
    } finally {
      promptSubmitting.value = false
    }
  })
}

const handleDeletePrompt = (row) => {
  ElMessageBox.confirm(
    `确定要删除模板"${row.name}"吗？删除后将无法恢复。`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deletePrompt(row.id)
      ElMessage.success('删除成功')
      loadPrompts()
    } catch (error) {
      console.error('删除失败:', error)
    }
  }).catch(() => {})
}

// ==================== 初始化 ====================
onMounted(() => {
  loadProviders()
  loadPrompts()
})
</script>

<style scoped>
.ai-config-panel {
  padding: 0;
}

.tab-toolbar {
  margin-bottom: 16px;
}

.masked-key {
  font-family: monospace;
  color: #909399;
  font-size: 13px;
}

.dialog-test-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  margin-top: 8px;
}

.test-result {
  font-size: 13px;
}

.test-result.success {
  color: #67c23a;
}

.test-result.fail {
  color: #f56c6c;
}

/* ==================== API Key 输入框反密码弹窗方案 ====================
   思路：
   1. el-input 用 type=text，避免被浏览器识别为登录密码输入；
   2. 通过 -webkit-text-security: disc 把字符渲染成圆点，视觉上等同于密码框；
   3. 上方一对 .autofill-decoy 假字段诱导浏览器把"保存的密码"塞到那里；
   4. autocomplete=new-password 进一步抑制 Chrome 的自动填充与"保存密码"提示。
============================================================= */
.autofill-decoy {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.masked-input :deep(.el-input__inner) {
  /* 浏览器层面是 text，但视觉上仍然是圆点 */
  -webkit-text-security: disc;
  text-security: disc;
  font-family: 'caption';
  letter-spacing: 1px;
}

.api-key-eye {
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: color 0.2s;
}

.api-key-eye:hover {
  color: var(--el-color-primary);
}
</style>
