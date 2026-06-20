<template>
  <div class="automation-detail-panel">
    <!-- 顶部操作栏 -->
    <div class="panel-header">
      <div class="header-left">
        <el-input
          v-model="form.name"
          placeholder="任务名称"
          size="small"
          class="name-input"
          spellcheck="false"
        />
        <el-tag v-if="task?.task_no" size="small" type="info">{{ task.task_no }}</el-tag>
        <el-tag v-if="form.status === 0" size="small" type="warning">已禁用</el-tag>
      </div>
      <div class="header-right">
        <el-button :icon="Clock" size="small" @click="emit('show-history')">历史</el-button>
        <el-button :icon="VideoPlay" size="small" type="success" @click="emit('execute')">执行</el-button>
        <el-button :icon="Check" size="small" type="primary" :loading="saving" @click="onSave">保存</el-button>
      </div>
    </div>

    <el-scrollbar class="panel-body">
      <!-- 基础配置 -->
      <el-card shadow="never" class="section-card">
        <template #header><div class="section-title">基础信息</div></template>
        <el-form label-width="100px" label-position="right" size="small">
          <el-form-item label="任务描述">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="2"
              placeholder="请输入任务描述"
            />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="所属目录">
                <el-tree-select
                  v-model="form.folder_id"
                  :data="folderOptions"
                  :props="{ children: 'children', label: 'name', value: 'raw_id' }"
                  placeholder="不选则放未分类"
                  check-strictly
                  clearable
                  :render-after-expand="false"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="启用状态">
                <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 触发方式 -->
      <el-card shadow="never" class="section-card">
        <template #header><div class="section-title">触发方式</div></template>
        <el-form label-width="100px" label-position="right" size="small">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="触发方式">
                <el-select v-model="form.trigger_type" style="width: 100%">
                  <el-option label="手动触发" value="manual" />
                  <el-option label="定时触发 (Cron)" value="cron" />
                  <el-option label="Webhook 触发" value="webhook" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col v-if="form.trigger_type === 'cron'" :span="12">
              <el-form-item label="Cron 表达式">
                <el-input v-model="form.cron_expression" placeholder="例如 */5 * * * *" />
              </el-form-item>
            </el-col>
            <el-col v-if="form.trigger_type === 'webhook' && task?.webhook_token" :span="24">
              <el-form-item label="Webhook URL">
                <el-input :model-value="webhookUrl" readonly>
                  <template #append>
                    <el-button @click="copyWebhook">复制</el-button>
                  </template>
                </el-input>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 执行配置 -->
      <el-card shadow="never" class="section-card">
        <template #header><div class="section-title">执行配置</div></template>
        <el-form label-width="100px" label-position="right" size="small">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="执行环境">
                <el-select v-model="form.environment_id" clearable placeholder="默认环境" style="width: 100%">
                  <el-option
                    v-for="env in environments"
                    :key="env.id"
                    :label="env.name"
                    :value="env.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="循环次数">
                <el-input-number v-model="form.loop_count" :min="1" :max="9999" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="间隔时间(s)">
                <el-input-number v-model="form.interval_seconds" :min="0" :precision="2" :step="0.5" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-collapse v-model="advancedOpen">
            <el-collapse-item title="高级设置" name="advanced">
              <el-form-item label="失败策略">
                <el-radio-group v-model="form.fail_strategy">
                  <el-radio value="continue">遇到错误继续</el-radio>
                  <el-radio value="stop">遇到错误终止</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </el-form>
      </el-card>

      <!-- 关联接口/用例 -->
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="section-title-row">
            <div class="section-title">执行步骤（{{ cases.length }}）</div>
            <div>
              <el-button :icon="Connection" size="small" type="primary" @click="emit('import-api')">
                导入接口
              </el-button>
              <el-button size="small" disabled title="开发中">导入接口用例</el-button>
            </div>
          </div>
        </template>
        <el-table :data="cases" size="small" row-key="id" stripe empty-text="暂无步骤，点击「导入接口」添加">
          <el-table-column label="顺序" width="70" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="caseKindType(row.ref?.kind)">
                {{ caseKindLabel(row.ref?.kind) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="方法/编号" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.ref?.method" size="small" :type="methodTagType(row.ref.method)">
                {{ row.ref.method }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="名称" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.ref?.missing" class="missing-tip">关联资源已删除</span>
              <span v-else>{{ row.ref?.name || `#${row.id}` }}</span>
            </template>
          </el-table-column>
          <el-table-column label="路径" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.ref?.path || row.ref?.url || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row, $index }">
              <el-button :icon="Top" link size="small" :disabled="$index === 0" @click="moveCase($index, -1)" />
              <el-button :icon="Bottom" link size="small" :disabled="$index === cases.length - 1" @click="moveCase($index, 1)" />
              <el-button :icon="Delete" link type="danger" size="small" @click="removeCase(row)" />
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-scrollbar>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Clock, VideoPlay, Check, Connection, Top, Bottom, Delete
} from '@element-plus/icons-vue'

const props = defineProps({
  task: { type: Object, default: () => null },
  cases: { type: Array, default: () => [] },
  environments: { type: Array, default: () => [] },
  folderOptions: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits([
  'save', 'execute', 'show-history', 'import-api',
  'remove-case', 'reorder-cases'
])

const advancedOpen = ref(['advanced'])

const form = reactive({
  name: '',
  description: '',
  folder_id: null,
  status: 1,
  trigger_type: 'manual',
  cron_expression: '',
  environment_id: null,
  loop_count: 1,
  interval_seconds: 0,
  fail_strategy: 'continue'
})

const syncFromTask = (task) => {
  if (!task) return
  Object.assign(form, {
    name: task.name || '',
    description: task.description || '',
    folder_id: task.folder_id ?? null,
    status: task.status ?? 1,
    trigger_type: task.trigger_type || 'manual',
    cron_expression: task.cron_expression || '',
    environment_id: task.environment_id ?? null,
    loop_count: task.loop_count ?? 1,
    interval_seconds: task.interval_seconds ?? 0,
    fail_strategy: task.fail_strategy || 'continue'
  })
}

watch(() => props.task, (val) => syncFromTask(val), { immediate: true, deep: false })

const webhookUrl = computed(() => {
  if (!props.task?.webhook_token) return ''
  return `${window.location.origin}/api/webhooks/${props.task.webhook_token}`
})

const copyWebhook = () => {
  navigator.clipboard.writeText(webhookUrl.value)
  ElMessage.success('已复制到剪贴板')
}

const onSave = () => {
  if (!form.name?.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (form.trigger_type === 'cron' && !form.cron_expression?.trim()) {
    ElMessage.warning('请输入 Cron 表达式')
    return
  }
  emit('save', { ...form })
}

const removeCase = async (row) => {
  try {
    await ElMessageBox.confirm('确定移除此步骤？仅解除关联，不会删除原接口/用例。', '提示', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消'
    })
    emit('remove-case', row)
  } catch (e) { /* cancel */ }
}

const moveCase = (index, delta) => {
  const next = index + delta
  if (next < 0 || next >= props.cases.length) return
  const newList = [...props.cases]
  const [moved] = newList.splice(index, 1)
  newList.splice(next, 0, moved)
  // 给上层重排：让父组件以新的顺序计算 sort_order
  emit('reorder-cases', newList)
}

const caseKindLabel = (kind) => ({
  api: '接口',
  case: '接口用例',
  case_mgmt: '测试用例'
})[kind] || '-'

const caseKindType = (kind) => ({
  api: 'primary',
  case: 'success',
  case_mgmt: 'warning'
})[kind] || 'info'

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
.automation-detail-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color-page);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}
.name-input {
  max-width: 360px;
}
.header-right {
  display: flex;
  gap: 8px;
}
.panel-body {
  flex: 1;
  padding: 12px 16px 24px;
}
.section-card {
  margin-bottom: 12px;
}
.section-title {
  font-weight: 600;
}
.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.missing-tip {
  color: var(--el-color-danger);
  font-size: 12px;
}
:deep(.el-card__header) {
  padding: 10px 14px;
}
:deep(.el-card__body) {
  padding: 14px 14px 4px;
}
</style>
