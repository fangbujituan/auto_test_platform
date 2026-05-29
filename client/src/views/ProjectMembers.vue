<template>
  <main-layout>
    <div class="members-layout">
      <project-sidebar
        active-module="requirement"
        :project-id="projectId"
        :project-name="projectName"
      />
      <div class="main-content">
        <!-- 顶部栏 -->
        <div class="page-header">
          <div class="header-left">
            <el-button link @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
            <span class="page-title">成员管理</span>
          </div>
          <el-button type="primary" size="small" @click="showAddDialog">
            <el-icon><Plus /></el-icon> 添加成员
          </el-button>
        </div>

        <!-- 成员列表 -->
        <div class="table-area" v-loading="loading">
          <el-table :data="members" stripe style="width: 100%">
            <el-table-column prop="username" label="用户名" width="140" />
            <el-table-column prop="role_name" label="角色" width="130">
              <template #default="{ row }">
                <el-tag :type="roleTypeMap[row.role_name]" size="small">{{ roleTextMap[row.role_name] || row.role_name }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="权限说明" min-width="260">
              <template #default="{ row }">
                <span class="perm-desc">{{ roleDescMap[row.role_name] || '' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="加入时间" width="170" />
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" :disabled="row.role_name === 'owner'" @click="openChangeRole(row)">修改角色</el-button>
                <el-button link type="danger" size="small" :disabled="row.role_name === 'owner'" @click="removeMember(row)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 添加成员对话框 -->
      <el-dialog v-model="addVisible" title="添加项目成员" width="520px" destroy-on-close>
        <el-form ref="addFormRef" :model="addForm" :rules="addRules" label-width="80px">
          <el-form-item label="选择用户" prop="user_ids">
            <el-select
              v-model="addForm.user_ids"
              multiple
              filterable
              placeholder="搜索并选择用户"
              style="width: 100%"
            >
              <el-option
                v-for="u in availableUsers"
                :key="u.id"
                :label="u.username"
                :value="u.id"
              >
                <span>{{ u.username }}</span>
                <span class="option-email">{{ u.email }}</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="分配角色" prop="role">
            <el-radio-group v-model="addForm.role" class="role-radio-group">
              <div v-for="r in assignableRoles" :key="r.value" class="role-card" :class="{ active: addForm.role === r.value }" @click="addForm.role = r.value">
                <el-radio :value="r.value" class="role-radio">
                  <span class="role-name">{{ r.label }}</span>
                </el-radio>
                <span class="role-card-desc">{{ r.desc }}</span>
              </div>
            </el-radio-group>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="addVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitAdd">确定</el-button>
        </template>
      </el-dialog>

      <!-- 修改角色对话框 -->
      <el-dialog v-model="roleVisible" title="修改成员角色" width="520px" destroy-on-close>
        <div class="change-role-info">
          <span class="cr-label">用户：</span><span>{{ currentMember?.username }}</span>
        </div>
        <div class="change-role-info" style="margin-bottom:16px">
          <span class="cr-label">当前角色：</span>
          <el-tag :type="roleTypeMap[currentMember?.role_name]" size="small">{{ roleTextMap[currentMember?.role_name] }}</el-tag>
        </div>
        <el-radio-group v-model="newRole" class="role-radio-group">
          <div v-for="r in assignableRoles" :key="r.value" class="role-card" :class="{ active: newRole === r.value }" @click="newRole = r.value">
            <el-radio :value="r.value" class="role-radio">
              <span class="role-name">{{ r.label }}</span>
            </el-radio>
            <span class="role-card-desc">{{ r.desc }}</span>
          </div>
        </el-radio-group>
        <template #footer>
          <el-button @click="roleVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitRoleChange">确定</el-button>
        </template>
      </el-dialog>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus } from '@element-plus/icons-vue'
import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import { getProjectMembers, addProjectMember, updateMemberRole, removeMember as removeMemberApi } from '../api/member'
import { getUsers } from '../api/user'

const router = useRouter()
const route = useRoute()
const projectId = computed(() => parseInt(route.params.projectId))
const projectName = computed(() => route.query.projectName || '项目')

const loading = ref(false)
const submitting = ref(false)
const members = ref([])
const allUsers = ref([])

const roleTypeMap = { admin: 'danger', owner: 'warning', member: 'success', viewer: 'info' }
const roleTextMap = { admin: '管理员', owner: '项目负责人', member: '项目成员', viewer: '只读用户' }
const roleDescMap = {
  admin: '拥有所有权限',
  owner: '可以管理项目、成员和所有用例',
  member: '可以创建、编辑用例和执行测试',
  viewer: '只能查看项目和用例，不能修改'
}
const assignableRoles = [
  { value: 'member', label: '项目成员', desc: '可以创建、编辑用例和执行测试' },
  { value: 'viewer', label: '只读用户', desc: '只能查看项目和用例，不能修改' }
]

// 可选用户（排除已是成员的）
const availableUsers = computed(() => {
  const memberIds = members.value.map(m => m.user_id)
  return allUsers.value.filter(u => !memberIds.includes(u.id))
})

// 添加成员
const addVisible = ref(false)
const addFormRef = ref(null)
const addForm = ref({ user_ids: [], role: 'member' })
const addRules = {
  user_ids: [{ required: true, type: 'array', min: 1, message: '请选择至少一个用户', trigger: 'change' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

// 修改角色
const roleVisible = ref(false)
const currentMember = ref(null)
const newRole = ref('')

const goBack = () => router.back()

const loadMembers = async () => {
  loading.value = true
  try {
    const res = await getProjectMembers(projectId.value)
    members.value = res.data || []
  } catch (e) { console.error(e) } finally { loading.value = false }
}

const loadUsers = async () => {
  try {
    const res = await getUsers()
    allUsers.value = res.data || []
  } catch (e) { console.error(e) }
}

const showAddDialog = () => {
  addForm.value = { user_ids: [], role: 'member' }
  addVisible.value = true
}

const submitAdd = async () => {
  if (!addFormRef.value) return
  await addFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      for (const uid of addForm.value.user_ids) {
        await addProjectMember({
          project_id: projectId.value,
          user_id: uid,
          role: addForm.value.role
        })
      }
      ElMessage.success(`成功添加 ${addForm.value.user_ids.length} 名成员`)
      addVisible.value = false
      loadMembers()
    } catch (e) {
      console.error(e)
      ElMessage.error('添加失败')
    } finally { submitting.value = false }
  })
}

const openChangeRole = (member) => {
  currentMember.value = member
  newRole.value = member.role_name
  roleVisible.value = true
}

const submitRoleChange = async () => {
  if (newRole.value === currentMember.value.role_name) {
    ElMessage.warning('角色未改变')
    return
  }
  submitting.value = true
  try {
    await updateMemberRole(currentMember.value.id, { role: newRole.value })
    ElMessage.success('修改成功')
    roleVisible.value = false
    loadMembers()
  } catch (e) { console.error(e) } finally { submitting.value = false }
}

const removeMember = (member) => {
  ElMessageBox.confirm(`确定将「${member.username}」移出项目？`, '移除确认', { type: 'warning' }).then(async () => {
    try {
      await removeMemberApi(member.id)
      ElMessage.success('移除成功')
      loadMembers()
    } catch (e) { console.error(e) }
  }).catch(() => {})
}

onMounted(() => { loadMembers(); loadUsers() })
</script>

<style scoped>
.members-layout { display: flex; height: 100%; overflow: hidden; }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: auto; background: var(--el-bg-color-page); }

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: var(--el-bg-color); border-bottom: 1px solid var(--el-border-color-light);
}
.header-left { display: flex; align-items: center; gap: 8px; }
.page-title { font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); }

.table-area { padding: 20px; flex: 1; overflow: auto; }
.perm-desc { color: var(--el-text-color-secondary); font-size: 13px; }

/* 下拉选项中的邮箱 */
.option-email { float: right; color: var(--el-text-color-secondary); font-size: 12px; }

/* 角色卡片选择 */
.role-radio-group { display: flex; flex-direction: column; gap: 10px; width: 100%; }
.role-card {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; border: 1px solid var(--el-border-color-light); border-radius: 8px;
  cursor: pointer; transition: all .2s;
}
.role-card:hover { border-color: var(--el-text-color-placeholder); }
.role-card.active { border-color: var(--el-color-primary); background: #ecf5ff; }
.role-radio { margin-right: 0; }
.role-name { font-size: 14px; font-weight: 500; color: var(--el-text-color-primary); }
.role-card-desc { font-size: 12px; color: var(--el-text-color-secondary); margin-left: auto; }

/* 修改角色对话框 */
.change-role-info { display: flex; align-items: center; gap: 4px; margin-bottom: 8px; font-size: 14px; }
.cr-label { color: var(--el-text-color-secondary); }
</style>
