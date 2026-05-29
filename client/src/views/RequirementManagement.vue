<template>
  <main-layout>
    <div class="requirement-layout">
      <!-- 左侧功能模块栏 -->
      <project-sidebar
        active-module="requirement"
        :project-id="projectId"
        :project-name="projectName"
        @stay="loadRequirements"
      />

      <!-- 主内容区 -->
      <div class="main-content">
        <!-- 顶部工具栏 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <el-select v-model="filterSprint" placeholder="全部冲刺" clearable size="small" style="width: 160px" @change="loadRequirements">
              <el-option v-for="s in sprints" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="全部状态" clearable size="small" style="width: 120px" @change="loadRequirements">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-select v-model="filterPriority" placeholder="全部优先级" clearable size="small" style="width: 120px" @change="loadRequirements">
              <el-option label="低" value="low" /><el-option label="中" value="medium" />
              <el-option label="高" value="high" /><el-option label="紧急" value="critical" />
            </el-select>
            <el-select v-model="filterAssignee" placeholder="关联人" clearable filterable size="small" style="width: 140px" @change="loadRequirements">
              <el-option v-for="m in members" :key="m.user_id" :label="m.username" :value="m.user_id" />
            </el-select>
            <el-input v-model="keyword" placeholder="搜索需求" clearable size="small" style="width: 200px" @keyup.enter="loadRequirements">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
          <div class="toolbar-right">
            <el-button size="small" @click="sprintDialogVisible = true">
              <el-icon><Timer /></el-icon> 冲刺管理
            </el-button>
            <el-button size="small" @click="tagDialogVisible = true">
              <el-icon><PriceTag /></el-icon> 标签管理
            </el-button>
            <el-button type="primary" size="small" @click="openCreateReq">
              <el-icon><Plus /></el-icon> 新建需求
            </el-button>
          </div>
        </div>

        <!-- 需求表格 -->
        <div class="table-area" v-loading="loading">
          <el-table :data="requirements" stripe highlight-current-row style="width: 100%">
            <el-table-column prop="req_number" label="编号" width="120">
              <template #default="{ row }">
                <span class="req-number-link" @click="goToDetail(row)">{{ row.req_number }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="需求名称" width="500" show-overflow-tooltip />
            <el-table-column prop="description" label="描述" min-width="160">
              <template #default="{ row }">
                <span class="desc-cell" :title="stripHtml(row.description)">{{ stripHtml(row.description) || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="110">
              <template #default="{ row }">
                <el-popover trigger="click" :width="140" :show-arrow="false" :hide-after="0" v-model:visible="row._statusOpen">
                  <template #reference>
                    <span :class="['status-badge', 'status-' + row.status]">{{ statusLabel(row.status) }}</span>
                  </template>
                  <div class="inline-dropdown">
                    <div
                      v-for="s in statusOptions" :key="s.value"
                      :class="['dropdown-item', { active: row.status === s.value }]"
                      @click="row._statusOpen = false; inlineUpdate(row, { status: s.value })"
                    >
                      <span :class="['status-dot', 'dot-' + s.value]"></span>{{ s.label }}
                    </div>
                  </div>
                </el-popover>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="100">
              <template #default="{ row }">
                <el-popover trigger="click" :width="120" :show-arrow="false" :hide-after="0" v-model:visible="row._priorityOpen">
                  <template #reference>
                    <span :class="['priority-badge', 'priority-' + row.priority]">{{ priorityLabel(row.priority) }}</span>
                  </template>
                  <div class="inline-dropdown">
                    <div
                      v-for="p in priorityOptions" :key="p.value"
                      :class="['dropdown-item', { active: row.priority === p.value }]"
                      @click="row._priorityOpen = false; inlineUpdate(row, { priority: p.value })"
                    >
                      <span :class="['priority-dot', 'pdot-' + p.value]"></span>{{ p.label }}
                    </div>
                  </div>
                </el-popover>
              </template>
            </el-table-column>
            <el-table-column label="标签" width="180">
              <template #default="{ row }">
                <el-popover trigger="click" :width="200" :show-arrow="false" :hide-after="0">
                  <template #reference>
                    <div class="tag-cell">
                      <span v-if="row.tags && row.tags.length" v-for="t in row.tags" :key="t.id" class="tag-pill" :style="{ background: t.color || '#409EFF' }">{{ t.name }}</span>
                      <span v-else class="tag-placeholder">+ 标签</span>
                    </div>
                  </template>
                  <div class="inline-dropdown tag-dropdown">
                    <label
                      v-for="t in allTags" :key="t.id"
                      class="tag-check-item"
                    >
                      <input
                        type="checkbox"
                        :checked="(row.tags || []).some(rt => rt.id === t.id)"
                        @change="toggleTag(row, t.id)"
                      />
                      <span class="tag-dot" :style="{ background: t.color || '#409EFF' }"></span>
                      {{ t.name }}
                    </label>
                    <div v-if="allTags.length === 0" style="color:#999;font-size:12px;padding:4px 0">暂无标签</div>
                  </div>
                </el-popover>
              </template>
            </el-table-column>
            <el-table-column prop="creator_name" label="创建人" width="90" />
            <el-table-column prop="created_at" label="创建时间" width="160" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click.stop="deleteReq(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="total > 0"
            class="pagination"
            background
            layout="total, prev, pager, next"
            :total="total"
            :page-size="pageSize"
            v-model:current-page="currentPage"
            @current-change="loadRequirements"
          />
        </div>
      </div>

      <!-- 新建/编辑需求对话框 -->
      <el-dialog v-model="reqDialogVisible" :title="reqForm.id ? '编辑需求' : '新建需求'" width="700px" destroy-on-close>
        <el-form ref="reqFormRef" :model="reqForm" :rules="reqRules" label-width="90px">
          <el-form-item label="需求名称" prop="title">
            <el-input v-model="reqForm.title" placeholder="请输入需求名称" />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="关联冲刺">
                <el-select v-model="reqForm.sprint_id" placeholder="选择冲刺" clearable style="width:100%">
                  <el-option v-for="s in sprints" :key="s.id" :label="s.name" :value="s.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="优先级">
                <el-select v-model="reqForm.priority" style="width:100%">
                  <el-option label="低" value="low" /><el-option label="中" value="medium" />
                  <el-option label="高" value="high" /><el-option label="紧急" value="critical" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="状态">
                <el-select v-model="reqForm.status" style="width:100%">
                  <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="标签">
                <el-select v-model="reqForm.tag_ids" multiple placeholder="选择标签" style="width:100%">
                  <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="关联人员">
            <el-select v-model="reqForm.assignee_ids" multiple placeholder="选择负责人" style="width:100%">
              <el-option v-for="m in members" :key="m.user_id" :label="m.username" :value="m.user_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="需求描述">
            <el-input v-model="reqForm.description" type="textarea" :rows="6" placeholder="支持输入需求描述（可包含HTML格式）" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="reqDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitReq">确定</el-button>
        </template>
      </el-dialog>

      <!-- 冲刺管理对话框 -->
      <el-dialog v-model="sprintDialogVisible" title="冲刺管理" width="750px" destroy-on-close>
        <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
          <el-button type="primary" size="small" @click="openCreateSprint"><el-icon><Plus /></el-icon> 新建冲刺</el-button>
        </div>
        <el-table :data="sprints" stripe size="small">
          <el-table-column prop="name" label="冲刺名称" min-width="140" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="sprintStatusType(row.status)" size="small">{{ sprintStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="160">
            <template #default="{ row }">{{ row.start_date?.slice(0, 10) }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="160">
            <template #default="{ row }">{{ row.end_date?.slice(0, 10) }}</template>
          </el-table-column>
          <el-table-column prop="creator_name" label="创建人" width="90" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEditSprint(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="deleteSprintConfirm(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 内嵌冲刺表单 -->
        <el-dialog v-model="sprintFormVisible" :title="sprintForm.id ? '编辑冲刺' : '新建冲刺'" width="500px" append-to-body>
          <el-form ref="sprintFormRef" :model="sprintForm" :rules="sprintRules" label-width="80px">
            <el-form-item label="冲刺名称" prop="name">
              <el-input v-model="sprintForm.name" placeholder="如：Sprint 1" />
            </el-form-item>
            <el-form-item label="时间范围" prop="dateRange">
              <el-date-picker v-model="sprintForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="sprintForm.status" style="width:100%">
                <el-option label="规划中" value="planning" /><el-option label="进行中" value="active" />
                <el-option label="已完成" value="completed" /><el-option label="已取消" value="cancelled" />
              </el-select>
            </el-form-item>
            <el-form-item label="冲刺目标">
              <el-input v-model="sprintForm.goal" type="textarea" :rows="3" placeholder="本次冲刺目标" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="sprintFormVisible = false">取消</el-button>
            <el-button type="primary" :loading="submitting" @click="submitSprint">确定</el-button>
          </template>
        </el-dialog>
      </el-dialog>

      <!-- 标签管理对话框 -->
      <el-dialog v-model="tagDialogVisible" title="标签管理" width="450px" destroy-on-close>
        <div style="display:flex;gap:8px;margin-bottom:12px">
          <el-input v-model="newTagName" placeholder="标签名称" size="small" style="flex:1" />
          <el-color-picker v-model="newTagColor" size="small" />
          <el-button type="primary" size="small" @click="addTag">添加</el-button>
        </div>
        <div class="tag-list">
          <el-tag v-for="t in allTags" :key="t.id" closable :color="t.color" effect="dark" style="margin:4px;border:none;color:#fff" @close="removeTag(t)">{{ t.name }}</el-tag>
        </div>
        <el-empty v-if="allTags.length === 0" description="暂无标签" :image-size="60" />
      </el-dialog>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Timer, PriceTag } from '@element-plus/icons-vue'
import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import {
  getRequirements, createRequirement, updateRequirement, deleteRequirement,
  getSprints, createSprint, updateSprint, deleteSprint,
  getTags, createTag, deleteTag
} from '../api/requirement'
import { getProjectMembers } from '../api/member'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => parseInt(route.params.projectId))
const projectName = computed(() => route.query.projectName || '项目详情')

// ===== 状态 =====
const loading = ref(false)
const submitting = ref(false)
const requirements = ref([])
const sprints = ref([])
const allTags = ref([])
const members = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

// 筛选
const filterSprint = ref(null)
const filterStatus = ref(null)
const filterPriority = ref(null)
const filterAssignee = ref(null)
const keyword = ref('')

// 状态选项
const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'pending', label: '待评审' },
  { value: 'approved', label: '已评审' },
  { value: 'in_progress', label: '开发中' },
  { value: 'testing', label: '测试中' },
  { value: 'done', label: '已完成' },
  { value: 'closed', label: '已关闭' },
  { value: 'rejected', label: '已拒绝' }
]

const statusLabel = (v) => (statusOptions.find(s => s.value === v)?.label || v)
const priorityLabel = (v) => ({ low: '低', medium: '中', high: '高', critical: '紧急' }[v] || v)
const priorityOptions = [
  { value: 'low', label: '低' }, { value: 'medium', label: '中' },
  { value: 'high', label: '高' }, { value: 'critical', label: '紧急' }
]
const sprintStatusLabel = (v) => ({ planning: '规划中', active: '进行中', completed: '已完成', cancelled: '已取消' }[v] || v)
const sprintStatusType = (v) => ({ planning: 'info', active: 'primary', completed: 'success', cancelled: 'danger' }[v] || 'info')

const stripHtml = (html) => {
  if (!html) return ''
  return html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
}

// ===== 需求 CRUD =====
const reqDialogVisible = ref(false)
const reqFormRef = ref(null)
const reqForm = ref({ id: null, title: '', description: '', sprint_id: null, assignee_ids: [], status: 'draft', priority: 'medium', tag_ids: [] })
const reqRules = { title: [{ required: true, message: '请输入需求名称', trigger: 'blur' }] }

const loadRequirements = async () => {
  loading.value = true
  try {
    const params = { project_id: projectId.value, page: currentPage.value, per_page: pageSize }
    if (filterSprint.value) params.sprint_id = filterSprint.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterAssignee.value) params.assignee_id = filterAssignee.value
    if (keyword.value) params.keyword = keyword.value
    const res = await getRequirements(params)
    requirements.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e) { console.error(e) } finally { loading.value = false }
}

const openCreateReq = () => {
  reqForm.value = { id: null, title: '', description: '', sprint_id: filterSprint.value || null, assignee_ids: [], status: 'draft', priority: 'medium', tag_ids: [] }
  reqDialogVisible.value = true
}

const goToDetail = (row) => {
  router.push({ name: 'RequirementDetail', params: { projectId: projectId.value, reqId: row.id }, query: { projectName: projectName.value } })
}

const inlineUpdate = async (row, fields) => {
  try {
    await updateRequirement(row.id, { ...fields, project_id: projectId.value })
    ElMessage.success('更新成功')
    loadRequirements()
  } catch (e) {
    console.error(e)
    ElMessage.error('更新失败')
    loadRequirements()
  }
}

const toggleTag = (row, tagId) => {
  const currentIds = (row.tags || []).map(t => t.id)
  const idx = currentIds.indexOf(tagId)
  if (idx >= 0) {
    currentIds.splice(idx, 1)
  } else {
    currentIds.push(tagId)
  }
  inlineUpdate(row, { tag_ids: currentIds })
}

const submitReq = async () => {
  if (!reqFormRef.value) return
  await reqFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = { ...reqForm.value, project_id: projectId.value }
      if (reqForm.value.id) {
        await updateRequirement(reqForm.value.id, payload)
        ElMessage.success('更新成功')
      } else {
        await createRequirement(payload)
        ElMessage.success('创建成功')
      }
      reqDialogVisible.value = false
      loadRequirements()
    } catch (e) { console.error(e) } finally { submitting.value = false }
  })
}

const deleteReq = (row) => {
  ElMessageBox.confirm(`确定删除需求「${row.title}」？`, '删除确认', { type: 'warning' }).then(async () => {
    await deleteRequirement(row.id)
    ElMessage.success('删除成功')
    loadRequirements()
  }).catch(() => {})
}

// ===== 冲刺 CRUD =====
const sprintDialogVisible = ref(false)
const sprintFormVisible = ref(false)
const sprintFormRef = ref(null)
const sprintForm = ref({ id: null, name: '', dateRange: null, status: 'planning', goal: '' })
const sprintRules = {
  name: [{ required: true, message: '请输入冲刺名称', trigger: 'blur' }],
  dateRange: [{ required: true, message: '请选择时间范围', trigger: 'change' }]
}

const loadSprints = async () => {
  try {
    const res = await getSprints({ project_id: projectId.value })
    sprints.value = res.data || []
  } catch (e) { console.error(e) }
}

const openCreateSprint = () => {
  sprintForm.value = { id: null, name: '', dateRange: null, status: 'planning', goal: '' }
  sprintFormVisible.value = true
}

const openEditSprint = (row) => {
  sprintForm.value = { id: row.id, name: row.name, dateRange: [row.start_date?.slice(0, 10), row.end_date?.slice(0, 10)], status: row.status, goal: row.goal || '' }
  sprintFormVisible.value = true
}

const submitSprint = async () => {
  if (!sprintFormRef.value) return
  await sprintFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = { name: sprintForm.value.name, project_id: projectId.value, start_date: sprintForm.value.dateRange[0], end_date: sprintForm.value.dateRange[1], status: sprintForm.value.status, goal: sprintForm.value.goal }
      if (sprintForm.value.id) {
        await updateSprint(sprintForm.value.id, payload)
        ElMessage.success('更新成功')
      } else {
        await createSprint(payload)
        ElMessage.success('创建成功')
      }
      sprintFormVisible.value = false
      loadSprints()
    } catch (e) { console.error(e) } finally { submitting.value = false }
  })
}

const deleteSprintConfirm = (row) => {
  ElMessageBox.confirm(`确定删除冲刺「${row.name}」？`, '删除确认', { type: 'warning' }).then(async () => {
    await deleteSprint(row.id)
    ElMessage.success('删除成功')
    loadSprints()
  }).catch(() => {})
}

// ===== 标签 CRUD =====
const tagDialogVisible = ref(false)
const newTagName = ref('')
const newTagColor = ref('#409EFF')

const loadTags = async () => {
  try {
    const res = await getTags()
    allTags.value = res.data || []
  } catch (e) { console.error(e) }
}

const addTag = async () => {
  if (!newTagName.value.trim()) return ElMessage.warning('请输入标签名称')
  try {
    await createTag({ name: newTagName.value.trim(), color: newTagColor.value })
    newTagName.value = ''
    loadTags()
  } catch (e) { console.error(e) }
}

const removeTag = (tag) => {
  ElMessageBox.confirm(`确定删除标签「${tag.name}」？`, '删除确认', { type: 'warning' }).then(async () => {
    await deleteTag(tag.id)
    loadTags()
  }).catch(() => {})
}

// ===== 加载成员 =====
const loadMembers = async () => {
  try {
    const res = await getProjectMembers(projectId.value)
    members.value = res.data || []
  } catch (e) { console.error(e) }
}

// ===== 初始化 =====
const initLoad = () => {
  loadRequirements()
  loadSprints()
  loadTags()
  loadMembers()
}

onMounted(initLoad)
onActivated(initLoad)
</script>

<style scoped>
.requirement-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--el-bg-color-page);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.table-area {
  flex: 1;
  padding: 16px;
  overflow: auto;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.tag-list {
  min-height: 40px;
}
.req-number-link {
  color: var(--el-color-primary);
  cursor: pointer;
  font-weight: 500;
}
.req-number-link:hover {
  text-decoration: underline;
}

/* 描述列 */
.desc-cell {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 20px;
  max-width: 100%;
  word-break: break-all;
}

/* 状态徽章 */
.status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 20px;
  cursor: pointer;
  font-weight: 500;
  transition: opacity .2s;
  white-space: nowrap;
}
.status-badge:hover { opacity: .8; }
.status-draft      { background: #f0f0f0; color: #909399; }
.status-pending     { background: #fdf6ec; color: #e6a23c; }
.status-approved    { background: #ecf5ff; color: #409eff; }
.status-in_progress { background: #ecf5ff; color: #409eff; }
.status-testing     { background: #fef0f0; color: #f56c6c; }
.status-done        { background: #f0f9eb; color: #67c23a; }
.status-closed      { background: #f0f0f0; color: #909399; }
.status-rejected    { background: #fef0f0; color: #f56c6c; }

/* 优先级徽章 */
.priority-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 20px;
  cursor: pointer;
  font-weight: 500;
  transition: opacity .2s;
  white-space: nowrap;
}
.priority-badge:hover { opacity: .8; }
.priority-low      { background: #f0f0f0; color: #909399; }
.priority-medium   { background: #ecf5ff; color: #409eff; }
.priority-high     { background: #fdf6ec; color: #e6a23c; }
.priority-critical { background: #fef0f0; color: #f56c6c; }

/* 标签单元格 */
.tag-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  overflow: hidden;
  cursor: pointer;
  min-height: 24px;
}
.tag-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 20px;
  color: #fff;
  white-space: nowrap;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tag-placeholder {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
.tag-placeholder:hover {
  color: var(--el-color-primary);
}

/* 内联下拉面板 */
.inline-dropdown {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background .15s;
}
.dropdown-item:hover { background: var(--el-fill-color-light); }
.dropdown-item.active { background: #ecf5ff; font-weight: 600; }

/* 状态圆点 */
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.dot-draft      { background: var(--el-text-color-placeholder); }
.dot-pending    { background: var(--el-color-warning); }
.dot-approved   { background: var(--el-color-primary); }
.dot-in_progress { background: var(--el-color-primary); }
.dot-testing    { background: var(--el-color-danger); }
.dot-done       { background: var(--el-color-success); }
.dot-closed     { background: var(--el-text-color-placeholder); }
.dot-rejected   { background: var(--el-color-danger); }

/* 优先级圆点 */
.priority-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.pdot-low      { background: var(--el-text-color-placeholder); }
.pdot-medium   { background: var(--el-color-primary); }
.pdot-high     { background: var(--el-color-warning); }
.pdot-critical { background: var(--el-color-danger); }

/* 标签多选项 */
.tag-dropdown {
  gap: 4px;
}
.tag-check-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background .15s;
}
.tag-check-item:hover { background: var(--el-fill-color-light); }
.tag-check-item input[type="checkbox"] {
  width: 14px; height: 14px; accent-color: var(--el-color-primary); cursor: pointer;
}
.tag-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
</style>
