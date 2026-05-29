<template>
  <main-layout>
    <div class="requirement-layout">
      <project-sidebar
        active-module="requirement"
        :project-id="projectId"
        :project-name="projectName"
      />
      <div class="main-content" v-loading="loading">
        <!-- 顶部栏 -->
        <div class="detail-header">
          <div class="header-left">
            <el-button link @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
            <span class="req-number">{{ req.req_number }}</span>
          </div>
          <div class="header-right">
            <el-button type="danger" size="small" plain @click="deleteReq"><el-icon><Delete /></el-icon> 删除</el-button>
            <el-button type="primary" size="small" :loading="submitting" @click="saveAll"><el-icon><Check /></el-icon> 保存</el-button>
          </div>
        </div>

        <div class="detail-body" v-if="req.id">
          <!-- 标题：直接编辑 -->
          <el-input
            v-model="form.title"
            class="title-input"
            placeholder="请输入需求名称"
            maxlength="200"
          />

          <!-- 第一部分：基础信息 -->
          <div class="section">
            <div class="section-title">基础信息</div>
            <div class="info-grid">
              <!-- 状态：popover 选择 -->
              <div class="info-item">
                <span class="info-label">状态：</span>
                <el-popover trigger="click" :width="140" :show-arrow="false" :hide-after="0" v-model:visible="statusOpen">
                  <template #reference>
                    <span :class="['status-badge', 'status-' + form.status]">{{ statusLabel(form.status) }}</span>
                  </template>
                  <div class="inline-dropdown">
                    <div
                      v-for="s in statusOptions" :key="s.value"
                      :class="['dropdown-item', { active: form.status === s.value }]"
                      @click="form.status = s.value; statusOpen = false"
                    >
                      <span :class="['status-dot', 'dot-' + s.value]"></span>{{ s.label }}
                    </div>
                  </div>
                </el-popover>
              </div>
              <!-- 优先级：popover 选择 -->
              <div class="info-item">
                <span class="info-label">优先级：</span>
                <el-popover trigger="click" :width="120" :show-arrow="false" :hide-after="0" v-model:visible="priorityOpen">
                  <template #reference>
                    <span :class="['priority-badge', 'priority-' + form.priority]">{{ priorityLabel(form.priority) }}</span>
                  </template>
                  <div class="inline-dropdown">
                    <div
                      v-for="p in priorityOptions" :key="p.value"
                      :class="['dropdown-item', { active: form.priority === p.value }]"
                      @click="form.priority = p.value; priorityOpen = false"
                    >
                      <span :class="['priority-dot', 'pdot-' + p.value]"></span>{{ p.label }}
                    </div>
                  </div>
                </el-popover>
              </div>
              <!-- 关联冲刺：popover 选择 -->
              <div class="info-item">
                <span class="info-label">关联冲刺：</span>
                <el-popover trigger="click" :width="180" :show-arrow="false" :hide-after="0" v-model:visible="sprintOpen">
                  <template #reference>
                    <span class="editable-value">{{ sprintName || '未关联' }}</span>
                  </template>
                  <div class="inline-dropdown">
                    <div
                      :class="['dropdown-item', { active: !form.sprint_id }]"
                      @click="form.sprint_id = null; sprintOpen = false"
                    >未关联</div>
                    <div
                      v-for="s in sprints" :key="s.id"
                      :class="['dropdown-item', { active: form.sprint_id === s.id }]"
                      @click="form.sprint_id = s.id; sprintOpen = false"
                    >{{ s.name }}</div>
                  </div>
                </el-popover>
              </div>
              <!-- 创建人 -->
              <div class="info-item">
                <span class="info-label">创建人：</span>
                <span class="info-value">{{ req.creator_name || '-' }}</span>
              </div>
              <!-- 创建时间 -->
              <div class="info-item">
                <span class="info-label">创建时间：</span>
                <span class="info-value">{{ req.created_at }}</span>
              </div>
              <!-- 标签：popover 多选 -->
              <div class="info-item">
                <span class="info-label">标签：</span>
                <el-popover trigger="click" :width="200" :show-arrow="false" :hide-after="0">
                  <template #reference>
                    <div class="tag-cell">
                      <span v-if="form.tag_ids && form.tag_ids.length" v-for="t in selectedTags" :key="t.id" class="tag-pill" :style="{ background: t.color || '#409EFF' }">{{ t.name }}</span>
                      <span v-else class="tag-placeholder">+ 标签</span>
                    </div>
                  </template>
                  <div class="inline-dropdown tag-dropdown">
                    <label v-for="t in allTags" :key="t.id" class="tag-check-item">
                      <input
                        type="checkbox"
                        :checked="form.tag_ids.includes(t.id)"
                        @change="toggleTag(t.id)"
                      />
                      <span class="tag-dot" :style="{ background: t.color || '#409EFF' }"></span>
                      {{ t.name }}
                    </label>
                    <div v-if="allTags.length === 0" style="color:#999;font-size:12px;padding:4px 0">暂无标签</div>
                  </div>
                </el-popover>
              </div>
              <!-- 关联人员：popover 多选 -->
              <div class="info-item">
                <span class="info-label">关联人员：</span>
                <el-popover trigger="click" :width="220" :show-arrow="false" :hide-after="0">
                  <template #reference>
                    <div class="tag-cell">
                      <span v-if="form.assignee_ids && form.assignee_ids.length" v-for="m in selectedMembers" :key="m.user_id" class="member-pill">{{ m.username }}</span>
                      <span v-else class="tag-placeholder">+ 人员</span>
                    </div>
                  </template>
                  <div class="inline-dropdown tag-dropdown">
                    <label v-for="m in members" :key="m.user_id" class="tag-check-item">
                      <input
                        type="checkbox"
                        :checked="form.assignee_ids.includes(m.user_id)"
                        @change="toggleAssignee(m.user_id)"
                      />
                      {{ m.username }}
                    </label>
                    <div v-if="members.length === 0" style="color:#999;font-size:12px;padding:4px 0">暂无成员</div>
                  </div>
                </el-popover>
              </div>
            </div>
          </div>
          <div class="section">
            <div class="section-title">描述信息</div>
            <div class="editor-wrap">
              <Toolbar :editor="editorRef" :defaultConfig="toolbarConfig" mode="simple" class="editor-toolbar" />
              <Editor
                :defaultConfig="editorConfig"
                mode="simple"
                class="editor-content"
                v-model="form.description"
                @onCreated="handleEditorCreated"
              />
            </div>
          </div>

          <!-- 第三部分：溯源信息 -->
          <div class="section">
            <div class="section-title">溯源信息</div>
            <el-tabs v-model="traceTab">
              <el-tab-pane label="评论" name="comments">
                <div class="trace-placeholder">
                  <el-empty description="评论功能开发中..." :image-size="80" />
                </div>
              </el-tab-pane>
              <el-tab-pane label="操作日志" name="logs">
                <div class="trace-placeholder">
                  <el-empty description="日志功能开发中..." :image-size="80" />
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </div>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, computed, shallowRef, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, Check } from '@element-plus/icons-vue'
import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import { getRequirement, updateRequirement, deleteRequirement, getSprints, getTags } from '../api/requirement'
import { getProjectMembers } from '../api/member'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import '@wangeditor/editor/dist/css/style.css'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => parseInt(route.params.projectId))
const projectName = computed(() => route.query.projectName || '项目详情')
const reqId = computed(() => parseInt(route.params.reqId))

const loading = ref(false)
const submitting = ref(false)
const req = ref({})
const sprints = ref([])
const allTags = ref([])
const members = ref([])
const traceTab = ref('comments')

// wangEditor
const editorRef = shallowRef(null)
const toolbarConfig = {}
const editorConfig = { placeholder: '请输入需求描述...' }
const handleEditorCreated = (editor) => { editorRef.value = editor }
onBeforeUnmount(() => { if (editorRef.value) editorRef.value.destroy() })

// 表单数据（进入即可编辑）
const form = ref({ title: '', description: '', sprint_id: null, status: 'draft', priority: 'medium', tag_ids: [], assignee_ids: [] })

// popover 控制
const statusOpen = ref(false)
const priorityOpen = ref(false)
const sprintOpen = ref(false)

const statusOptions = [
  { value: 'draft', label: '草稿' }, { value: 'pending', label: '待评审' },
  { value: 'approved', label: '已评审' }, { value: 'in_progress', label: '开发中' },
  { value: 'testing', label: '测试中' }, { value: 'done', label: '已完成' },
  { value: 'closed', label: '已关闭' }, { value: 'rejected', label: '已拒绝' }
]
const priorityOptions = [
  { value: 'low', label: '低' }, { value: 'medium', label: '中' },
  { value: 'high', label: '高' }, { value: 'critical', label: '紧急' }
]
const statusLabel = (v) => (statusOptions.find(s => s.value === v)?.label || v)
const priorityLabel = (v) => ({ low: '低', medium: '中', high: '高', critical: '紧急' }[v] || v)

const sprintName = computed(() => {
  if (!form.value.sprint_id) return ''
  const s = sprints.value.find(s => s.id === form.value.sprint_id)
  return s ? s.name : ''
})

const selectedTags = computed(() => {
  return allTags.value.filter(t => form.value.tag_ids.includes(t.id))
})

const toggleTag = (tagId) => {
  const idx = form.value.tag_ids.indexOf(tagId)
  if (idx >= 0) {
    form.value.tag_ids.splice(idx, 1)
  } else {
    form.value.tag_ids.push(tagId)
  }
}

const selectedMembers = computed(() => {
  return members.value.filter(m => form.value.assignee_ids.includes(m.user_id))
})

const toggleAssignee = (userId) => {
  const idx = form.value.assignee_ids.indexOf(userId)
  if (idx >= 0) {
    form.value.assignee_ids.splice(idx, 1)
  } else {
    form.value.assignee_ids.push(userId)
  }
}

const goBack = () => {
  router.push({ name: 'RequirementManagement', params: { projectId: projectId.value }, query: { projectName: projectName.value } })
}

const loadDetail = async () => {
  loading.value = true
  try {
    const res = await getRequirement(reqId.value)
    const r = res.data || {}
    req.value = r
    form.value = {
      title: r.title || '',
      description: r.description || '',
      sprint_id: r.sprint_id || null,
      status: r.status || 'draft',
      priority: r.priority || 'medium',
      tag_ids: (r.tags || []).map(t => t.id),
      assignee_ids: r.assignee_ids || []
    }
  } catch (e) { console.error(e) } finally { loading.value = false }
}

const saveAll = async () => {
  if (!form.value.title?.trim()) {
    ElMessage.warning('请输入需求名称')
    return
  }
  submitting.value = true
  try {
    await updateRequirement(reqId.value, { ...form.value, project_id: projectId.value })
    ElMessage.success('保存成功')
    loadDetail()
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  } finally { submitting.value = false }
}

const deleteReq = () => {
  ElMessageBox.confirm(`确定删除需求「${req.value.title}」？`, '删除确认', { type: 'warning' }).then(async () => {
    await deleteRequirement(reqId.value)
    ElMessage.success('删除成功')
    goBack()
  }).catch(() => {})
}

onMounted(async () => {
  loadDetail()
  getSprints({ project_id: projectId.value }).then(res => { sprints.value = res.data || [] })
  getTags().then(res => { allTags.value = res.data || [] })
  getProjectMembers(projectId.value).then(res => { members.value = res.data || [] })
})
</script>

<style scoped>
.requirement-layout { display: flex; height: 100%; overflow: hidden; }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: auto; background: var(--el-bg-color-page); position: relative; z-index: 0; }

/* 顶部栏 */
.detail-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: var(--el-bg-color); border-bottom: 1px solid var(--el-border-color-light);
}
.header-left { display: flex; align-items: center; gap: 8px; overflow: hidden; }
.header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.req-number { font-size: 14px; font-weight: 600; color: var(--el-color-primary); white-space: nowrap; }

/* 标题输入框 */
.title-input { margin-bottom: 20px; }
.title-input :deep(.el-input__wrapper) {
  box-shadow: none; background: transparent; padding: 0; border-radius: 6px;
}
.title-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--el-border-color); background: var(--el-bg-color); padding: 0 12px;
}
.title-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary); background: var(--el-bg-color); padding: 0 12px;
}
.title-input :deep(.el-input__inner) {
  font-size: 18px; font-weight: 600; color: var(--el-text-color-primary);
  border: none; border-radius: 6px; padding: 8px 0;
  background: transparent; box-shadow: none;
}
.title-input :deep(.el-input__inner:hover) { border-color: var(--el-border-color); background: var(--el-bg-color); }
.title-input :deep(.el-input__inner:focus) { border-color: var(--el-color-primary); background: var(--el-bg-color); }

/* 主体 */
.detail-body { padding: 24px; max-width: 960px; }

/* 分区 */
.section { margin-bottom: 4px; }
.section-title {
  font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); margin-bottom: 16px;
  display: flex; align-items: center; gap: 12px;
}
.section-title::after {
  content: ''; flex: 1; height: 1px; background: var(--el-border-color);
}

/* 基础信息网格 */
.info-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px 32px; }
.info-item { display: flex; flex-direction: row; align-items: center; gap: 4px; }
.info-label { font-size: 13px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }
.info-value { font-size: 14px; color: var(--el-text-color-primary); }

/* 可编辑值 */
.editable-value {
  font-size: 14px; color: var(--el-text-color-primary); cursor: pointer;
  padding: 2px 10px; border-radius: 10px; background: var(--el-fill-color-light);
  display: inline-block; line-height: 20px; transition: opacity .2s;
}
.editable-value:hover { opacity: .8; }

/* 状态 / 优先级徽章 */
.status-badge, .priority-badge {
  display: inline-block; padding: 2px 10px; border-radius: 10px;
  font-size: 12px; line-height: 20px; font-weight: 500; white-space: nowrap;
  width: fit-content; cursor: pointer; transition: opacity .2s;
}
.status-badge:hover, .priority-badge:hover { opacity: .8; }
.status-draft      { background: #f0f0f0; color: #909399; }
.status-pending     { background: #fdf6ec; color: #e6a23c; }
.status-approved    { background: #ecf5ff; color: #409eff; }
.status-in_progress { background: #ecf5ff; color: #409eff; }
.status-testing     { background: #fef0f0; color: #f56c6c; }
.status-done        { background: #f0f9eb; color: #67c23a; }
.status-closed      { background: #f0f0f0; color: #909399; }
.status-rejected    { background: #fef0f0; color: #f56c6c; }
.priority-low      { background: #f0f0f0; color: #909399; }
.priority-medium   { background: #ecf5ff; color: #409eff; }
.priority-high     { background: #fdf6ec; color: #e6a23c; }
.priority-critical { background: #fef0f0; color: #f56c6c; }

/* 标签 */
.tag-cell {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  cursor: pointer; min-height: 24px;
}
.tag-pill {
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 12px; line-height: 20px; color: #fff; white-space: nowrap;
}
.tag-placeholder { color: var(--el-text-color-placeholder); font-size: 12px; cursor: pointer; }
.tag-placeholder:hover { color: var(--el-color-primary); }

/* 关联人员 */
.member-pill {
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 12px; line-height: 20px; color: var(--el-text-color-primary); background: #ecf5ff;
  white-space: nowrap;
}

/* 内联下拉面板 */
.inline-dropdown { display: flex; flex-direction: column; gap: 2px; }
.dropdown-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 6px; font-size: 13px;
  cursor: pointer; transition: background .15s;
}
.dropdown-item:hover { background: var(--el-fill-color-light); }
.dropdown-item.active { background: #ecf5ff; font-weight: 600; }

/* 状态圆点 */
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-draft      { background: var(--el-text-color-placeholder); }
.dot-pending    { background: var(--el-color-warning); }
.dot-approved   { background: var(--el-color-primary); }
.dot-in_progress { background: var(--el-color-primary); }
.dot-testing    { background: var(--el-color-danger); }
.dot-done       { background: var(--el-color-success); }
.dot-closed     { background: var(--el-text-color-placeholder); }
.dot-rejected   { background: var(--el-color-danger); }

/* 优先级圆点 */
.priority-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.pdot-low      { background: var(--el-text-color-placeholder); }
.pdot-medium   { background: var(--el-color-primary); }
.pdot-high     { background: var(--el-color-warning); }
.pdot-critical { background: var(--el-color-danger); }

/* 标签多选项 */
.tag-dropdown { gap: 4px; }
.tag-check-item {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 8px; border-radius: 6px; font-size: 13px;
  cursor: pointer; transition: background .15s;
}
.tag-check-item:hover { background: var(--el-fill-color-light); }
.tag-check-item input[type="checkbox"] { width: 14px; height: 14px; accent-color: var(--el-color-primary); cursor: pointer; }
.tag-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

/* 富文本编辑器 */
.editor-wrap {
  border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; background: var(--el-bg-color);
}
.editor-toolbar {
  border-bottom: 1px solid var(--el-border-color-light);
}
.editor-content {
  min-height: 260px; font-size: 14px; line-height: 1.8;
}
/* 全屏限制在 main-content 内 */
.main-content :deep(.w-e-full-screen-container) {
  position: absolute !important;
  z-index: 100 !important;
}

/* 溯源占位 */
.trace-placeholder { padding: 20px 0; }
</style>
