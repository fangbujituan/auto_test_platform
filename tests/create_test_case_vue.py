# -*- coding: utf-8 -*-
"""创建测试用例管理Vue组件"""

vue_content = '''<template>
  <main-layout>
    <div class="test-case-layout">
      <div class="left-sidebar">
        <div class="sidebar-header">
          <h3>测试模块</h3>
          <el-button type="primary" size="small" @click="showCreateModuleDialog()">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>
        <div class="tree-container" v-loading="moduleLoading">
          <el-tree
            ref="moduleTreeRef"
            :data="moduleTree"
            :props="{ children: 'children', label: 'name' }"
            :expand-on-click-node="false"
            default-expand-all
            @node-click="handleModuleClick"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <span>{{ data.name }} ({{ data.module_no }})</span>
                <el-button-group size="small">
                  <el-button @click.stop="editModule(data)"><el-icon><Edit /></el-icon></el-button>
                  <el-button @click.stop="deleteModule(data)"><el-icon><Delete /></el-icon></el-button>
                </el-button-group>
              </div>
            </template>
          </el-tree>
        </div>
      </div>

      <div class="middle-panel">
        <div class="panel-header">
          <el-input v-model="searchKeyword" placeholder="搜索用例" clearable size="small">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" size="small" @click="showCreateCaseDialog">
            <el-icon><Plus /></el-icon>新建用例
          </el-button>
        </div>

        <div class="case-list" v-loading="caseLoading">
          <div v-for="testCase in testCases" :key="testCase.id" 
               class="case-item" 
               :class="{ active: currentCase && currentCase.id === testCase.id }"
               @click="selectCase(testCase)">
            <div class="case-header">
              <el-tag :type="getPriorityType(testCase.priority)" size="small">{{ testCase.priority }}</el-tag>
              <span class="case-no">{{ testCase.case_no }}</span>
            </div>
            <div class="case-title">{{ testCase.title }}</div>
            <div class="case-meta">
              <el-tag size="small">{{ testCase.case_type }}</el-tag>
              <el-tag size="small" :type="getStatusType(testCase.case_status)">{{ testCase.case_status }}</el-tag>
            </div>
          </div>
          <el-empty v-if="!caseLoading && testCases.length === 0" description="暂无用例" />
        </div>

        <el-pagination
          v-if="total > 0"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadTestCases"
        />
      </div>

      <div class="right-panel">
        <div v-if="!currentCase" class="empty-state">
          <el-empty description="请选择一个用例查看详情" />
        </div>
        <div v-else class="case-detail">
          <div class="detail-header">
            <h3>{{ currentCase.title }}</h3>
            <div>
              <el-button size="small" @click="editCase(currentCase)"><el-icon><Edit /></el-icon>编辑</el-button>
              <el-button size="small" type="danger" @click="deleteCase(currentCase)"><el-icon><Delete /></el-icon>删除</el-button>
            </div>
          </div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用例编号">{{ currentCase.case_no }}</el-descriptions-item>
            <el-descriptions-item label="优先级">
              <el-tag :type="getPriorityType(currentCase.priority)">{{ currentCase.priority }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="用例类型">{{ currentCase.case_type }}</el-descriptions-item>
            <el-descriptions-item label="用例状态">
              <el-tag :type="getStatusType(currentCase.case_status)">{{ currentCase.case_status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ currentCase.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="前置条件" :span="2">{{ currentCase.precondition || '-' }}</el-descriptions-item>
            <el-descriptions-item label="测试步骤" :span="2">
              <pre>{{ currentCase.steps || '-' }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="预期结果" :span="2">{{ currentCase.expected_result || '-' }}</el-descriptions-item>
            <el-descriptions-item label="绑定API" :span="2">
              <el-tag v-for="apiId in currentCase.api_ids" :key="apiId" size="small" style="margin-right: 5px;">
                API-{{ apiId }}
              </el-tag>
              <span v-if="!currentCase.api_ids || currentCase.api_ids.length === 0">-</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 模块对话框 -->
      <el-dialog v-model="moduleDialogVisible" :title="moduleDialogTitle" width="500px">
        <el-form ref="moduleFormRef" :model="moduleForm" label-width="100px">
          <el-form-item label="模块编号" prop="module_no" required>
            <el-input v-model="moduleForm.module_no" placeholder="MOD-001" />
          </el-form-item>
          <el-form-item label="模块名称" prop="name" required>
            <el-input v-model="moduleForm.name" />
          </el-form-item>
          <el-form-item label="模块描述">
            <el-input v-model="moduleForm.description" type="textarea" :rows="3" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="moduleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitModuleForm">确定</el-button>
        </template>
      </el-dialog>

      <!-- 用例对话框 -->
      <el-dialog v-model="caseDialogVisible" :title="caseDialogTitle" width="700px">
        <el-form ref="caseFormRef" :model="caseForm" label-width="100px">
          <el-form-item label="用例标题" prop="title" required>
            <el-input v-model="caseForm.title" />
          </el-form-item>
          <el-form-item label="所属模块" prop="module_id" required>
            <el-tree-select
              v-model="caseForm.module_id"
              :data="moduleTree"
              :props="{ children: 'children', label: 'name', value: 'id' }"
              check-strictly
              placeholder="请选择模块"
            />
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="优先级">
                <el-select v-model="caseForm.priority">
                  <el-option label="P0" value="P0" />
                  <el-option label="P1" value="P1" />
                  <el-option label="P2" value="P2" />
                  <el-option label="P3" value="P3" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="用例类型">
                <el-select v-model="caseForm.case_type">
                  <el-option label="功能" value="功能" />
                  <el-option label="性能" value="性能" />
                  <el-option label="安全" value="安全" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="用例状态">
                <el-select v-model="caseForm.case_status">
                  <el-option label="草稿" value="草稿" />
                  <el-option label="已评审" value="已评审" />
                  <el-option label="已废弃" value="已废弃" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="用例描述">
            <el-input v-model="caseForm.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="前置条件">
            <el-input v-model="caseForm.precondition" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="测试步骤">
            <el-input v-model="caseForm.steps" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="预期结果">
            <el-input v-model="caseForm.expected_result" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="caseDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitCaseForm">确定</el-button>
        </template>
      </el-dialog>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Search, Folder, FolderOpened } from '@element-plus/icons-vue'
import { getModuleTree, createModule, updateModule, deleteModule as deleteModuleApi } from '../api/module'
import { getTestCases, createTestCase, updateTestCase, deleteTestCase as deleteTestCaseApi } from '../api/testCase'
import MainLayout from '../components/MainLayout.vue'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.projectId))

const moduleLoading = ref(false)
const caseLoading = ref(false)
const moduleTree = ref([])
const testCases = ref([])
const currentModule = ref(null)
const currentCase = ref(null)
const searchKeyword = ref('')
const filterPriority = ref('')
const filterType = ref('')
const filterStatus = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const moduleDialogVisible = ref(false)
const moduleDialogTitle = ref('新建模块')
const moduleForm = ref({ id: null, module_no: '', name: '', description: '', parent_id: null })

const caseDialogVisible = ref(false)
const caseDialogTitle = ref('新建用例')
const caseForm = ref({
  id: null, title: '', description: '', precondition: '', steps: '', expected_result: '',
  module_id: null, priority: 'P2', case_type: '功能', case_status: '草稿'
})

onMounted(() => {
  loadModuleTree()
  loadTestCases()
})

const loadModuleTree = async () => {
  moduleLoading.value = true
  try {
    const res = await getModuleTree(projectId.value)
    moduleTree.value = res.data || []
  } catch (error) {
    ElMessage.error('加载模块失败')
  } finally {
    moduleLoading.value = false
  }
}

const loadTestCases = async () => {
  caseLoading.value = true
  try {
    const params = {
      project_id: projectId.value,
      page: page.value,
      per_page: pageSize.value
    }
    if (currentModule.value) params.module_id = currentModule.value.id
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterType.value) params.case_type = filterType.value
    if (filterStatus.value) params.case_status = filterStatus.value

    const res = await getTestCases(params)
    testCases.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (error) {
    ElMessage.error('加载用例失败')
  } finally {
    caseLoading.value = false
  }
}

const handleModuleClick = (data) => {
  currentModule.value = data
  page.value = 1
  loadTestCases()
}

const selectCase = (testCase) => {
  currentCase.value = testCase
}

const showCreateModuleDialog = (parentId = null) => {
  moduleDialogTitle.value = '新建模块'
  moduleForm.value = { id: null, module_no: '', name: '', description: '', parent_id: parentId, project_id: projectId.value }
  moduleDialogVisible.value = true
}

const editModule = (module) => {
  moduleDialogTitle.value = '编辑模块'
  moduleForm.value = { ...module }
  moduleDialogVisible.value = true
}

const submitModuleForm = async () => {
  try {
    if (moduleForm.value.id) {
      await updateModule(moduleForm.value.id, moduleForm.value)
      ElMessage.success('更新成功')
    } else {
      await createModule(moduleForm.value)
      ElMessage.success('创建成功')
    }
    moduleDialogVisible.value = false
    loadModuleTree()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  }
}

const deleteModule = async (module) => {
  try {
    await ElMessageBox.confirm(`确定删除模块"${module.name}"吗？`, '删除确认', { type: 'warning' })
    await deleteModuleApi(module.id)
    ElMessage.success('删除成功')
    loadModuleTree()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '删除失败')
    }
  }
}

const showCreateCaseDialog = () => {
  caseDialogTitle.value = '新建用例'
  caseForm.value = {
    id: null, title: '', description: '', precondition: '', steps: '', expected_result: '',
    module_id: currentModule.value?.id, priority: 'P2', case_type: '功能', case_status: '草稿',
    project_id: projectId.value
  }
  caseDialogVisible.value = true
}

const editCase = (testCase) => {
  caseDialogTitle.value = '编辑用例'
  caseForm.value = { ...testCase }
  caseDialogVisible.value = true
}

const submitCaseForm = async () => {
  try {
    if (caseForm.value.id) {
      await updateTestCase(caseForm.value.id, caseForm.value)
      ElMessage.success('更新成功')
    } else {
      await createTestCase(caseForm.value)
      ElMessage.success('创建成功')
    }
    caseDialogVisible.value = false
    loadTestCases()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  }
}

const deleteCase = async (testCase) => {
  try {
    await ElMessageBox.confirm(`确定删除用例"${testCase.title}"吗？`, '删除确认', { type: 'warning' })
    await deleteTestCaseApi(testCase.id)
    ElMessage.success('删除成功')
    currentCase.value = null
    loadTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '删除失败')
    }
  }
}

const getPriorityType = (priority) => {
  const map = { P0: 'danger', P1: 'warning', P2: '', P3: 'info' }
  return map[priority] || ''
}

const getStatusType = (status) => {
  const map = { '草稿': 'info', '已评审': 'success', '已废弃': 'danger' }
  return map[status] || ''
}
</script>

<style scoped>
.test-case-layout {
  display: flex;
  height: calc(100vh - 60px);
  background: #f5f5f5;
}

.left-sidebar {
  width: 280px;
  background: white;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 15px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 10px;
}

.middle-panel {
  width: 400px;
  background: white;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 15px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  gap: 10px;
}

.filter-bar {
  padding: 10px 15px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  gap: 10px;
}

.case-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.case-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #fafafa;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
}

.case-item:hover {
  background: #f0f0f0;
}

.case-item.active {
  background: #e6f7ff;
  border-left: 3px solid #1890ff;
}

.case-header {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.case-no {
  color: #999;
  font-size: 12px;
}

.case-title {
  font-weight: 500;
  margin-bottom: 8px;
}

.case-meta {
  display: flex;
  gap: 5px;
}

.right-panel {
  flex: 1;
  background: white;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.case-detail {
  padding: 20px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #e8e8e8;
}

.detail-header h3 {
  margin: 0;
}

pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}
</style>
'''

with open('client/src/views/TestCaseManagement.vue', 'w', encoding='utf-8') as f:
    f.write(vue_content)

print("✓ TestCaseManagement.vue 创建成功")
