<template>
  <main-layout>
    <div class="project-list-container">
      <div class="header-actions">
        <h3>项目管理</h3>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建项目
        </el-button>
      </div>

      <div class="project-cards" v-loading="loading">
        <div
          v-for="project in projects"
          :key="project.id"
          class="project-card"
          @click="viewProject(project)"
        >
          <!-- 右上角：角色 + 状态 -->
          <div class="card-top-right">
            <el-tag :type="getRoleType(project.role)" size="small">
              {{ getRoleText(project.role) }}
            </el-tag>
            <el-tag :type="project.status === 1 ? 'success' : 'info'" size="small">
              {{ project.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </div>

          <!-- 三个点菜单 -->
          <div class="card-menu" v-if="canEdit(project.role)" @click.stop>
            <el-dropdown trigger="hover" @command="(cmd) => handleCommand(cmd, project)">
              <el-icon class="more-icon"><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="members" v-if="canManageMembers(project.role)">
                    成员管理
                  </el-dropdown-item>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="delete" v-if="canDelete(project.role)">
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 项目名 + 描述 -->
          <div class="card-body">
            <div class="project-name">{{ project.name }}</div>
            <div class="project-desc" :title="project.description">
              {{ truncateDesc(project.description) }}
            </div>
          </div>

          <!-- 右下角：创建时间 -->
          <div class="card-bottom-right">
            {{ project.created_at }}
          </div>
        </div>

        <el-empty v-if="!loading && projects.length === 0" description="暂无项目" />
      </div>

      <!-- 创建/编辑项目对话框 -->
      <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
          <el-form-item label="项目名称" prop="name">
            <el-input v-model="form.name" placeholder="请输入项目名称" />
          </el-form-item>
          <el-form-item label="项目描述" prop="description">
            <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请输入项目描述" />
          </el-form-item>
          <el-form-item label="状态" prop="status" v-if="isEdit">
            <el-radio-group v-model="form.status">
              <el-radio :label="1">启用</el-radio>
              <el-radio :label="0">禁用</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
        </template>
      </el-dialog>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MoreFilled } from '@element-plus/icons-vue'
import { getProjects, createProject, updateProject, deleteProject as deleteProjectApi } from '../api/project'
import MainLayout from '../components/MainLayout.vue'

const router = useRouter()
const loading = ref(false)
const projects = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建项目')
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const form = ref({
  id: null,
  name: '',
  description: '',
  status: 1
})

const rules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ]
}

onMounted(() => {
  loadProjects()
})

const truncateDesc = (desc) => {
  if (!desc) return '暂无描述'
  return desc.length > 15 ? desc.slice(0, 15) + '...' : desc
}

const loadProjects = async () => {
  loading.value = true
  try {
    const res = await getProjects()
    projects.value = res.data || []
  } catch (error) {
    console.error('加载项目失败:', error)
  } finally {
    loading.value = false
  }
}

const getRoleType = (role) => {
  const typeMap = { admin: 'danger', owner: 'warning', member: 'success', viewer: 'info' }
  return typeMap[role] || 'info'
}

const getRoleText = (role) => {
  const textMap = { admin: '管理员', owner: '负责人', member: '成员', viewer: '只读' }
  return textMap[role] || role
}

const canManageMembers = (role) => ['admin', 'owner'].includes(role)
const canEdit = (role) => ['admin', 'owner'].includes(role)
const canDelete = (role) => ['admin', 'owner'].includes(role)

const handleCommand = (command, project) => {
  if (command === 'members') manageMembers(project)
  else if (command === 'edit') editProject(project)
  else if (command === 'delete') deleteProject(project)
}

const showCreateDialog = () => {
  isEdit.value = false
  dialogTitle.value = '新建项目'
  form.value = { id: null, name: '', description: '', status: 1 }
  dialogVisible.value = true
}

const editProject = (project) => {
  isEdit.value = true
  dialogTitle.value = '编辑项目'
  form.value = { id: project.id, name: project.name, description: project.description, status: project.status }
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (isEdit.value) {
        await updateProject(form.value.id, form.value)
        ElMessage.success('更新成功')
      } else {
        await createProject(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadProjects()
    } catch (error) {
      console.error('操作失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

const deleteProject = (project) => {
  ElMessageBox.confirm(
    `确定要删除项目"${project.name}"吗？删除后将无法恢复。`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteProjectApi(project.id)
      ElMessage.success('删除成功')
      loadProjects()
    } catch (error) {
      console.error('删除失败:', error)
    }
  }).catch(() => {})
}

const viewProject = (project) => {
  router.push({ name: 'ProjectDetail', params: { projectId: project.id }, query: { projectName: project.name } })
}

const manageMembers = (project) => {
  router.push({ name: 'ProjectMembers', params: { projectId: project.id }, query: { projectName: project.name } })
}
</script>

<style scoped>
.project-list-container {
  padding: 20px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-actions h3 {
  margin: 0;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.project-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.project-card {
  position: relative;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.25s ease;
  min-height: 140px;
  display: flex;
  flex-direction: column;
}

.project-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  border-color: var(--el-color-primary);
}

.card-top-right {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 6px;
}

.card-menu {
  position: absolute;
  top: 12px;
  right: 12px;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 1;
}

.project-card:hover .card-menu {
  opacity: 1;
}

.project-card:hover .card-top-right {
  opacity: 0;
}

.more-icon {
  font-size: 18px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.more-icon:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.card-body {
  flex: 1;
  padding-top: 8px;
}

.project-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.project-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.card-bottom-right {
  text-align: right;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 12px;
}
</style>