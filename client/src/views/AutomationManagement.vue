<template>
  <main-layout>
    <div class="automation-layout">
      <!-- 左侧功能模块栏 -->
      <project-sidebar
        active-module="automation"
        :project-id="projectId"
        :project-name="projectName"
        @stay="loadTree()"
      />

      <!-- 中间目录树 -->
      <automation-folder-tree
        ref="treeRef"
        :tree-data="treeData"
        :loading="treeLoading"
        @select-task="handleSelectTask"
        @add-folder="handleAddFolder"
        @add-automation="handleAddAutomation"
        @folder-action="handleFolderAction"
        @task-action="handleTaskAction"
      />

      <!-- 右侧详情面板 -->
      <div class="right-area">
        <div v-if="!currentTask" class="empty-state">
          <el-empty description="请选择一个自动化任务查看详情" :image-size="120" />
        </div>
        <automation-detail-panel
          v-else
          :task="currentTask"
          :cases="currentCases"
          :environments="environmentList"
          :folder-options="folderOptions"
          :saving="saving"
          @save="handleSaveTask"
          @execute="handleExecuteCurrent"
          @show-history="showHistory(currentTask)"
          @import-api="importDialogVisible = true"
          @remove-case="handleRemoveCase"
          @reorder-cases="handleReorderCases"
        />
      </div>
    </div>

    <!-- 创建/编辑目录对话框 -->
    <el-dialog
      v-model="folderDialogVisible"
      :title="folderDialogTitle"
      width="500px"
      destroy-on-close
    >
      <el-form
        :model="folderForm"
        :rules="{ name: [{ required: true, message: '请输入目录名称', trigger: 'blur' }] }"
        label-width="80px"
      >
        <el-form-item label="目录名称" prop="name">
          <el-input v-model="folderForm.name" placeholder="请输入目录名称" />
        </el-form-item>
        <el-form-item label="目录描述">
          <el-input v-model="folderForm.description" type="textarea" :rows="3" placeholder="请输入目录描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="folderDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="folderSubmitting" @click="submitFolderForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 创建自动化任务对话框 -->
    <el-dialog
      v-model="newTaskDialogVisible"
      title="新建自动化任务"
      width="520px"
      destroy-on-close
    >
      <el-form
        :model="newTaskForm"
        :rules="{ name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }] }"
        label-width="80px"
      >
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="newTaskForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="newTaskForm.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newTaskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="newTaskSubmitting" @click="submitNewTask">创建</el-button>
      </template>
    </el-dialog>

    <!-- 导入接口对话框 -->
    <import-api-dialog
      v-model:visible="importDialogVisible"
      :project-id="projectId"
      @confirm="handleImportConfirm"
    />

    <!-- 执行历史对话框 -->
    <el-dialog
      v-model="historyDialogVisible"
      :title="`执行历史 - ${historyTask?.name || ''}`"
      width="900px"
      destroy-on-close
    >
      <div class="stats-row" v-if="statistics">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ statistics.execution_count }}</div>
          <div class="stat-label">近30天执行次数</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ ((statistics.avg_pass_rate || 0) * 100).toFixed(1) }}%</div>
          <div class="stat-label">平均通过率</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ statistics.avg_duration?.toFixed(1) || 0 }}s</div>
          <div class="stat-label">平均耗时</div>
        </el-card>
      </div>

      <el-table :data="executionList" stripe v-loading="historyLoading" style="margin-top: 16px" size="small">
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
    <el-dialog v-model="execDialogVisible" title="执行详情" width="850px" destroy-on-close>
      <div v-if="execDetail">
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
  </main-layout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import AutomationFolderTree from '../components/automation/AutomationFolderTree.vue'
import AutomationDetailPanel from '../components/automation/AutomationDetailPanel.vue'
import ImportApiDialog from '../components/automation/ImportApiDialog.vue'

import {
  getAutomation, createAutomation, updateAutomation, deleteAutomation,
  executeAutomation, getExecutions, getExecutionDetail, getExecutionStatistics,
  importAutomationCases, deleteAutomationCase, reorderAutomationCases
} from '../api/automation'
import { getAutomationFolderTree, createFolder, updateFolder, deleteFolder } from '../api/folder'
import { getEnvironments } from '../api/envVariable'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.projectId))
const projectName = computed(() => route.query.projectName || '项目详情')

// ============ 目录树 ============
const treeRef = ref(null)
const treeData = ref([])
const treeLoading = ref(false)

const loadTree = async () => {
  treeLoading.value = true
  try {
    const res = await getAutomationFolderTree(projectId.value)
    treeData.value = res.data || []
  } catch (e) {
    console.error('加载目录树失败:', e)
    ElMessage.error('加载目录树失败')
  } finally {
    treeLoading.value = false
  }
}

// 仅用于"目录"下拉选择（去除 task 节点）
const folderOptions = computed(() => {
  const walk = (nodes) => nodes
    .filter(n => n.type === 'folder' && !n.is_virtual)
    .map(n => ({
      raw_id: n.raw_id,
      name: n.name,
      children: n.children ? walk(n.children) : []
    }))
  return walk(treeData.value || [])
})

// ============ 环境 ============
const environmentList = ref([])
const loadEnvironments = async () => {
  try {
    const res = await getEnvironments(projectId.value)
    environmentList.value = res.data || []
  } catch (e) { console.error(e) }
}

// ============ 当前选中任务 ============
const currentTask = ref(null)
const currentCases = ref([])
const saving = ref(false)

const loadTaskDetail = async (taskId) => {
  try {
    const res = await getAutomation(projectId.value, taskId)
    currentTask.value = res.data
    currentCases.value = res.data?.cases || []
    treeRef.value?.setCurrentKey(`automation_${taskId}`)
  } catch (e) {
    console.error('加载任务详情失败:', e)
    ElMessage.error('加载任务详情失败')
  }
}

const handleSelectTask = (data) => {
  if (!data?.raw_id) return
  loadTaskDetail(data.raw_id)
}

const handleSaveTask = async (formData) => {
  if (!currentTask.value) return
  saving.value = true
  try {
    const payload = { ...formData }
    if (payload.trigger_type !== 'cron') delete payload.cron_expression
    await updateAutomation(projectId.value, currentTask.value.id, payload)
    ElMessage.success('保存成功')
    await loadTaskDetail(currentTask.value.id)
    await loadTree()
  } catch (e) {
    console.error('保存失败:', e)
  } finally {
    saving.value = false
  }
}

const handleExecuteCurrent = async () => {
  if (!currentTask.value) return
  try {
    await ElMessageBox.confirm(`确定执行任务「${currentTask.value.name}」吗？`, '执行确认', {
      type: 'info',
      confirmButtonText: '执行',
      cancelButtonText: '取消'
    })
    await executeAutomation(currentTask.value.id)
    ElMessage.success('执行已触发')
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

// ============ 步骤管理 ============
const importDialogVisible = ref(false)

const handleImportConfirm = async (items) => {
  if (!currentTask.value) {
    ElMessage.warning('请先选择一个任务')
    return
  }
  try {
    await importAutomationCases(projectId.value, currentTask.value.id, {
      items, append: true
    })
    ElMessage.success(`已导入 ${items.length} 个步骤`)
    importDialogVisible.value = false
    await loadTaskDetail(currentTask.value.id)
  } catch (e) {
    console.error('导入失败:', e)
  }
}

const handleRemoveCase = async (row) => {
  if (!currentTask.value) return
  try {
    await deleteAutomationCase(projectId.value, currentTask.value.id, row.id)
    ElMessage.success('已移除')
    await loadTaskDetail(currentTask.value.id)
  } catch (e) {
    console.error('移除失败:', e)
  }
}

const handleReorderCases = async (newList) => {
  if (!currentTask.value) return
  // 预先 UI 排序，调接口同步
  currentCases.value = newList
  const order = newList.map((row, idx) => ({ id: row.id, sort_order: idx + 1 }))
  try {
    await reorderAutomationCases(projectId.value, currentTask.value.id, order)
  } catch (e) {
    console.error('调整顺序失败:', e)
    await loadTaskDetail(currentTask.value.id)
  }
}

// ============ 目录 CRUD ============
const folderDialogVisible = ref(false)
const folderDialogTitle = ref('新建目录')
const folderSubmitting = ref(false)
const folderEditing = ref(null)
const folderParent = ref(null)
const folderForm = ref({ name: '', description: '' })

const handleAddFolder = (parent) => {
  folderEditing.value = null
  folderParent.value = parent || null
  folderDialogTitle.value = parent ? `新建子目录（在 ${parent.name} 下）` : '新建目录'
  folderForm.value = { name: '', description: '' }
  folderDialogVisible.value = true
}

const handleFolderAction = async ({ command, data }) => {
  if (command === 'rename') {
    folderEditing.value = data
    folderParent.value = null
    folderDialogTitle.value = '重命名目录'
    folderForm.value = { name: data.name, description: data.description || '' }
    folderDialogVisible.value = true
  } else if (command === 'delete') {
    try {
      await ElMessageBox.confirm(
        `确定删除目录「${data.name}」？目录下的任务将变为「未分类」。`,
        '删除确认',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
      )
      await deleteFolder(projectId.value, data.raw_id)
      ElMessage.success('已删除')
      await loadTree()
    } catch (e) { if (e !== 'cancel') console.error(e) }
  }
}

const submitFolderForm = async () => {
  if (!folderForm.value.name?.trim()) {
    ElMessage.warning('请输入目录名称')
    return
  }
  folderSubmitting.value = true
  try {
    if (folderEditing.value) {
      await updateFolder(projectId.value, folderEditing.value.raw_id, folderForm.value)
      ElMessage.success('已更新')
    } else {
      await createFolder(projectId.value, {
        ...folderForm.value,
        type: 'automation',
        parent_id: folderParent.value?.raw_id || null
      })
      ElMessage.success('已创建')
    }
    folderDialogVisible.value = false
    await loadTree()
  } catch (e) {
    console.error('操作失败:', e)
  } finally {
    folderSubmitting.value = false
  }
}

// ============ 任务 CRUD ============
const newTaskDialogVisible = ref(false)
const newTaskSubmitting = ref(false)
const newTaskParent = ref(null)
const newTaskForm = ref({ name: '', description: '' })

const handleAddAutomation = (parent) => {
  newTaskParent.value = parent || null
  newTaskForm.value = { name: '', description: '' }
  newTaskDialogVisible.value = true
}

const submitNewTask = async () => {
  if (!newTaskForm.value.name?.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  newTaskSubmitting.value = true
  try {
    const res = await createAutomation(projectId.value, {
      name: newTaskForm.value.name,
      description: newTaskForm.value.description,
      folder_id: newTaskParent.value?.raw_id || null,
      trigger_type: 'manual',
      loop_count: 1,
      fail_strategy: 'continue',
      interval_seconds: 0
    })
    ElMessage.success('创建成功')
    newTaskDialogVisible.value = false
    await loadTree()
    if (res.data?.id) {
      await loadTaskDetail(res.data.id)
    }
  } catch (e) {
    console.error('创建失败:', e)
  } finally {
    newTaskSubmitting.value = false
  }
}

const handleTaskAction = async ({ command, data }) => {
  if (!data?.raw_id) return
  if (command === 'execute') {
    try {
      await ElMessageBox.confirm(`确定执行任务「${data.name}」吗？`, '执行确认', {
        type: 'info', confirmButtonText: '执行', cancelButtonText: '取消'
      })
      await executeAutomation(data.raw_id)
      ElMessage.success('执行已触发')
    } catch (e) { if (e !== 'cancel') console.error(e) }
  } else if (command === 'history') {
    showHistory({ id: data.raw_id, name: data.name })
  } else if (command === 'delete') {
    try {
      await ElMessageBox.confirm(`确定删除任务「${data.name}」？此操作不可恢复。`, '删除确认', {
        type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
      })
      await deleteAutomation(projectId.value, data.raw_id)
      ElMessage.success('已删除')
      if (currentTask.value?.id === data.raw_id) {
        currentTask.value = null
        currentCases.value = []
      }
      await loadTree()
    } catch (e) { if (e !== 'cancel') console.error(e) }
  }
}

// ============ 历史 ============
const historyDialogVisible = ref(false)
const historyTask = ref(null)
const historyLoading = ref(false)
const executionList = ref([])
const historyPage = ref(1)
const historyTotal = ref(0)
const statistics = ref(null)

const showHistory = async (task) => {
  historyTask.value = task
  historyPage.value = 1
  executionList.value = []
  statistics.value = null
  historyDialogVisible.value = true
  await Promise.all([loadExecutions(), loadStatistics(task.id)])
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
  } catch (e) { console.error(e) }
  finally { historyLoading.value = false }
}

const loadStatistics = async (taskId) => {
  try {
    const res = await getExecutionStatistics(taskId)
    statistics.value = res.data
  } catch (e) { console.error(e) }
}

const execDialogVisible = ref(false)
const execDetail = ref(null)
const showExecDetail = async (row) => {
  execDialogVisible.value = true
  execDetail.value = null
  try {
    const res = await getExecutionDetail(row.id)
    execDetail.value = res.data
  } catch (e) { console.error(e) }
}

// ============ 标签辅助 ============
const triggerLabel = (t) => ({ manual: '手动', cron: '定时', webhook: 'Webhook' })[t] || t || '-'

const execStatusType = (status) => ({
  completed: 'success', running: 'primary',
  failed: 'danger', cancelled: 'info', pending: 'warning'
})[status] || 'info'

const execStatusLabel = (status) => ({
  pending: '等待中', running: '执行中', completed: '已完成',
  failed: '失败', cancelled: '已取消'
})[status] || status

const caseStatusType = (status) => ({
  passed: 'success', failed: 'danger', error: 'warning', skipped: 'info'
})[status] || 'info'

// ============ 初始化 ============
onMounted(() => {
  loadTree()
  loadEnvironments()
})
</script>

<style scoped>
.automation-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}
.right-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--el-bg-color-page);
}
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stats-row {
  display: flex;
  gap: 12px;
}
.stat-card {
  flex: 1;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
}
</style>
