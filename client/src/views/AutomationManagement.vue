<template>
  <main-layout>
    <div class="automation-layout">
      <!-- 左侧功能模块栏 -->
      <project-sidebar
        active-module="automation"
        :project-id="projectId"
        :project-name="projectName"
        @stay="loadTasks()"
      />

      <!-- 主内容区 -->
      <div class="main-area">
        <!-- 顶部操作栏 -->
        <div class="toolbar">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索任务名称"
            clearable
            style="width: 260px"
            @keyup.enter="loadTasks"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建任务
          </el-button>
        </div>

        <!-- 任务列表表格 -->
        <el-table
          v-loading="loading"
          :data="taskList"
          stripe
          style="width: 100%"
          @row-click="handleRowClick"
          class="task-table"
        >
          <el-table-column prop="task_no" label="任务编号" width="150" />
          <el-table-column prop="name" label="任务名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="触发方式" width="130">
            <template #default="{ row }">
              <el-tag :type="triggerTagType(row.trigger_type)" size="small">
                {{ triggerLabel(row.trigger_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                {{ row.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="260" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="handleExecute(row)">
                <el-icon><VideoPlay /></el-icon> 执行
              </el-button>
              <el-button link type="primary" size="small" @click.stop="showHistory(row)">
                <el-icon><Clock /></el-icon> 历史
              </el-button>
              <el-button link type="primary" size="small" @click.stop="showEditDialog(row)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button link type="danger" size="small" @click.stop="handleDelete(row)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadTasks"
            @current-change="loadTasks"
          />
        </div>
      </div>

      <!-- 创建/编辑任务对话框 -->
      <el-dialog
        v-model="taskDialogVisible"
        :title="taskDialogTitle"
        width="680px"
        destroy-on-close
        :close-on-click-modal="false"
      >
        <el-form
          ref="taskFormRef"
          :model="taskForm"
          :rules="taskRules"
          label-width="100px"
        >
          <el-form-item label="任务名称" prop="name">
            <el-input v-model="taskForm.name" placeholder="请输入任务名称" />
          </el-form-item>
          <el-form-item label="任务描述">
            <el-input v-model="taskForm.description" type="textarea" :rows="3" placeholder="请输入任务描述" />
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="触发方式" prop="trigger_type">
                <el-select v-model="taskForm.trigger_type" style="width: 100%">
                  <el-option label="手动触发" value="manual" />
                  <el-option label="定时触发 (Cron)" value="cron" />
                  <el-option label="Webhook 触发" value="webhook" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="执行环境">
                <el-select v-model="taskForm.environment_id" clearable placeholder="默认环境" style="width: 100%">
                  <el-option
                    v-for="env in environmentList"
                    :key="env.id"
                    :label="env.name"
                    :value="env.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item v-if="taskForm.trigger_type === 'cron'" label="Cron 表达式" prop="cron_expression">
            <el-input v-model="taskForm.cron_expression" placeholder="例如: */5 * * * * (每5分钟)" />
          </el-form-item>
          <el-form-item v-if="taskForm.trigger_type === 'webhook' && editingTask?.webhook_token" label="Webhook URL">
            <el-input :model-value="webhookUrl" readonly>
              <template #append>
                <el-button @click="copyWebhookUrl">复制</el-button>
              </template>
            </el-input>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="taskDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitTask" :loading="submitting">确定</el-button>
        </template>
      </el-dialog>

      <!-- 执行历史对话框 -->
      <el-dialog
        v-model="historyDialogVisible"
        :title="`执行历史 - ${historyTask?.name || ''}`"
        width="900px"
        destroy-on-close
      >
        <!-- 统计卡片 -->
        <div class="stats-row" v-if="statistics">
          <el-card shadow="never" class="stat-card">
            <div class="stat-value">{{ statistics.execution_count }}</div>
            <div class="stat-label">近30天执行次数</div>
          </el-card>
          <el-card shadow="never" class="stat-card">
            <div class="stat-value">{{ (statistics.avg_pass_rate * 100).toFixed(1) }}%</div>
            <div class="stat-label">平均通过率</div>
          </el-card>
          <el-card shadow="never" class="stat-card">
            <div class="stat-value">{{ statistics.avg_duration?.toFixed(1) || 0 }}s</div>
            <div class="stat-label">平均耗时</div>
          </el-card>
        </div>

        <!-- 执行历史表格 -->
        <el-table :data="executionList" stripe v-loading="historyLoading" style="margin-top: 16px">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="execStatusType(row.status)" size="small">{{ execStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发方式" width="100">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ triggerLabel(row.trigger_source) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="通过/失败/错误" width="140">
            <template #default="{ row }">
              <span style="color: #67c23a">{{ row.passed_count }}</span> /
              <span style="color: #f56c6c">{{ row.failed_count }}</span> /
              <span style="color: #e6a23c">{{ row.error_count }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="耗时" width="90">
            <template #default="{ row }">{{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="执行时间" width="170" />
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="showExecDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap" style="margin-top: 12px">
          <el-pagination
            v-model:current-page="historyPage"
            :page-size="10"
            :total="historyTotal"
            layout="total, prev, pager, next"
            @current-change="loadExecutions"
          />
        </div>
      </el-dialog>

      <!-- 执行详情对话框 -->
      <el-dialog
        v-model="detailDialogVisible"
        title="执行详情"
        width="850px"
        destroy-on-close
      >
        <div v-if="execDetail" class="exec-detail">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="状态">
              <el-tag :type="execStatusType(execDetail.status)" size="small">{{ execStatusLabel(execDetail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ execDetail.duration ? execDetail.duration.toFixed(1) + 's' : '-' }}</el-descriptions-item>
            <el-descriptions-item label="用例总数">{{ execDetail.total_cases }}</el-descriptions-item>
            <el-descriptions-item label="通过">
              <span style="color: #67c23a; font-weight: 600">{{ execDetail.passed_count }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="失败">
              <span style="color: #f56c6c; font-weight: 600">{{ execDetail.failed_count }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="错误">
              <span style="color: #e6a23c; font-weight: 600">{{ execDetail.error_count }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-table :data="execDetail.details || []" stripe style="margin-top: 16px" size="small">
            <el-table-column prop="case_name" label="用例名称" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="caseStatusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="actual_status" label="HTTP状态码" width="110" align="center" />
            <el-table-column prop="duration" label="耗时" width="90">
              <template #default="{ row }">{{ row.duration ? row.duration.toFixed(2) + 's' : '-' }}</template>
            </el-table-column>
            <el-table-column prop="error_message" label="错误信息" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>
        <el-empty v-else description="加载中..." />
      </el-dialog>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Plus, Edit, Delete, VideoPlay, Clock
} from '@element-plus/icons-vue'
import {
  getAutomations, getAutomation, createAutomation, updateAutomation,
  deleteAutomation, executeAutomation, getExecutions,
  getExecutionDetail, getExecutionStatistics
} from '../api/automation'
import { getEnvironments } from '../api/envVariable'
import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.projectId))
const projectName = computed(() => route.query.projectName || '项目详情')

// ===== 任务列表 =====
const loading = ref(false)
const taskList = ref([])
const searchKeyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const loadTasks = async () => {
  loading.value = true
  try {
    const params = { page: page.value, per_page: pageSize.value }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await getAutomations(projectId.value, params)
    taskList.value = res.data || []
    total.value = res.total || 0
  } catch (e) {
    console.error('加载任务列表失败:', e)
  } finally {
    loading.value = false
  }
}

// ===== 辅助数据 =====
const environmentList = ref([])

const loadEnvironments = async () => {
  try {
    const res = await getEnvironments(projectId.value)
    environmentList.value = res.data || []
  } catch (e) { console.error(e) }
}

onMounted(() => {
  loadTasks()
  loadEnvironments()
})

// ===== 创建/编辑对话框 =====
const taskDialogVisible = ref(false)
const taskDialogTitle = ref('新建任务')
const submitting = ref(false)
const taskFormRef = ref(null)
const editingTask = ref(null)

const taskForm = ref({
  name: '',
  description: '',
  trigger_type: 'manual',
  cron_expression: '',
  environment_id: null
})

const taskRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  trigger_type: [{ required: true, message: '请选择触发方式', trigger: 'change' }],
  cron_expression: [{ required: true, message: '请输入 Cron 表达式', trigger: 'blur' }]
}

const webhookUrl = computed(() => {
  if (!editingTask.value?.webhook_token) return ''
  return `${window.location.origin}/api/webhooks/${editingTask.value.webhook_token}`
})

const showCreateDialog = () => {
  taskDialogTitle.value = '新建任务'
  editingTask.value = null
  taskForm.value = {
    name: '', description: '', trigger_type: 'manual',
    cron_expression: '', environment_id: null
  }
  taskDialogVisible.value = true
}

const showEditDialog = async (row) => {
  taskDialogTitle.value = '编辑任务'
  try {
    const res = await getAutomation(projectId.value, row.id)
    const task = res.data
    editingTask.value = task
    taskForm.value = {
      name: task.name,
      description: task.description || '',
      trigger_type: task.trigger_type,
      cron_expression: task.cron_expression || '',
      environment_id: task.environment_id
    }
    taskDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载任务详情失败')
  }
}

const submitTask = async () => {
  if (!taskFormRef.value) return
  await taskFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = { ...taskForm.value }
      if (payload.trigger_type !== 'cron') delete payload.cron_expression
      if (editingTask.value) {
        await updateAutomation(projectId.value, editingTask.value.id, payload)
        ElMessage.success('更新成功')
      } else {
        await createAutomation(projectId.value, payload)
        ElMessage.success('创建成功')
      }
      taskDialogVisible.value = false
      loadTasks()
    } catch (e) {
      console.error('操作失败:', e)
    } finally {
      submitting.value = false
    }
  })
}

const copyWebhookUrl = () => {
  navigator.clipboard.writeText(webhookUrl.value)
  ElMessage.success('已复制到剪贴板')
}

// ===== 执行 & 删除 =====
const handleExecute = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要执行任务「${row.name}」吗？`, '执行确认', {
      confirmButtonText: '执行', cancelButtonText: '取消', type: 'info'
    })
    await executeAutomation(row.id)
    ElMessage.success('执行已触发')
    loadTasks()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除任务「${row.name}」吗？此操作不可恢复。`, '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning'
    })
    await deleteAutomation(projectId.value, row.id)
    ElMessage.success('删除成功')
    loadTasks()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

const handleRowClick = (row) => {
  showHistory(row)
}

// ===== 执行历史 =====
const historyDialogVisible = ref(false)
const historyTask = ref(null)
const historyLoading = ref(false)
const executionList = ref([])
const historyPage = ref(1)
const historyTotal = ref(0)
const statistics = ref(null)

const showHistory = async (row) => {
  historyTask.value = row
  historyPage.value = 1
  executionList.value = []
  statistics.value = null
  historyDialogVisible.value = true
  await Promise.all([loadExecutions(), loadStatistics(row.id)])
}

const loadExecutions = async () => {
  if (!historyTask.value) return
  historyLoading.value = true
  try {
    const res = await getExecutions(historyTask.value.id, {
      page: historyPage.value, per_page: 10
    })
    executionList.value = res.data || []
    historyTotal.value = res.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    historyLoading.value = false
  }
}

const loadStatistics = async (taskId) => {
  try {
    const res = await getExecutionStatistics(taskId)
    statistics.value = res.data
  } catch (e) {
    console.error(e)
  }
}

// ===== 执行详情 =====
const detailDialogVisible = ref(false)
const execDetail = ref(null)

const showExecDetail = async (row) => {
  execDetail.value = null
  detailDialogVisible.value = true
  try {
    const res = await getExecutionDetail(row.id)
    execDetail.value = res.data
  } catch (e) {
    ElMessage.error('加载执行详情失败')
  }
}

// ===== 标签辅助函数 =====
const triggerLabel = (type) => {
  const map = { manual: '手动', cron: '定时', webhook: 'Webhook' }
  return map[type] || type
}
const triggerTagType = (type) => {
  const map = { manual: 'info', cron: 'warning', webhook: 'success' }
  return map[type] || 'info'
}
const execStatusLabel = (status) => {
  const map = { pending: '等待中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}
const execStatusType = (status) => {
  const map = { pending: 'info', running: 'primary', completed: 'success', failed: 'danger', cancelled: 'warning' }
  return map[status] || 'info'
}
const caseStatusType = (status) => {
  const map = { passed: 'success', failed: 'danger', error: 'warning', skipped: 'info' }
  return map[status] || 'info'
}
</script>

<style scoped>
.automation-layout {
  display: flex;
  height: calc(100vh - 90px);
  background: #f5f7fa;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.task-table {
  flex: 1;
  overflow: auto;
}

.task-table :deep(.el-table__row) {
  cursor: pointer;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  gap: 16px;
}

.stat-card {
  flex: 1;
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #409eff;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.exec-detail {
  max-height: 60vh;
  overflow-y: auto;
}
</style>
