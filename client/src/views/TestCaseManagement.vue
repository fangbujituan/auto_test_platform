<template>
  <main-layout>
    <div class="test-case-layout">
      <!-- 左侧功能模块栏 -->
      <project-sidebar
        active-module="case"
        :project-id="projectId"
        :project-name="projectName"
        @stay="loadTree(); loadFolders()"
      />

      <!-- 中间用例列表栏 -->
      <div class="middle-panel">
        <div class="panel-header">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索用例"
            clearable
            size="small"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          
          <div class="header-actions">
            <el-dropdown @command="handleAddAction" trigger="click">
              <el-button type="primary" size="small">
                <el-icon><Plus /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="folder">
                    <el-icon><Folder /></el-icon>
                    新建目录
                  </el-dropdown-item>
                  <el-dropdown-item command="case">
                    <el-icon><Document /></el-icon>
                    新建用例
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            
            <el-dropdown @command="handleMoreAction" trigger="click">
              <el-button size="small">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="refresh">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-dropdown-item>
                  <el-dropdown-item command="init">
                    <el-icon><MagicStick /></el-icon>
                    初始化目录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <div class="tree-container" v-loading="loading">
          <el-tree
            ref="treeRef"
            :data="treeData"
            :props="treeProps"
            :expand-on-click-node="false"
            :highlight-current="true"
            default-expand-all
            @node-click="handleNodeClick"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <div class="node-content">
                  <!-- 目录图标 -->
                  <el-icon v-if="data.type === 'folder'" class="node-icon folder-icon">
                    <Folder v-if="!node.expanded" />
                    <FolderOpened v-else />
                  </el-icon>
                  
                  <!-- 用例优先级标签 -->
                  <el-tag
                    v-else-if="data.type === 'case'"
                    :type="getPriorityType(data.priority)"
                    size="small"
                    class="priority-tag"
                  >
                    {{ data.priority }}
                  </el-tag>
                  
                  <!-- 节点名称 -->
                  <span class="node-label" :title="data.description || data.name || data.title">
                    {{ data.name || data.title }}
                  </span>
                  
                  <!-- 用例状态标签 -->
                  <el-tag
                    v-if="data.type === 'case'"
                    :type="getStatusType(data.case_status)"
                    size="small"
                    class="status-tag"
                  >
                    {{ getStatusShort(data.case_status) }}
                  </el-tag>
                  
                  <!-- 节点统计信息 -->
                  <span v-if="data.type === 'folder' && data.children && data.children.length > 0" class="node-count">
                    ({{ getNodeStats(data) }})
                  </span>
                </div>
                
                <!-- 操作按钮 -->
                <div class="node-actions" @click.stop>
                  <!-- 目录操作 -->
                  <el-dropdown
                    v-if="data.type === 'folder' && !data.is_virtual"
                    @command="(cmd) => handleFolderAction(cmd, data)"
                    trigger="click"
                  >
                    <el-icon class="action-icon"><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="addFolder">
                          <el-icon><FolderAdd /></el-icon>
                          新建子目录
                        </el-dropdown-item>
                        <el-dropdown-item command="addCase">
                          <el-icon><DocumentAdd /></el-icon>
                          新建用例
                        </el-dropdown-item>
                        <el-dropdown-item command="rename">
                          <el-icon><Edit /></el-icon>
                          重命名
                        </el-dropdown-item>
                        <el-dropdown-item command="move">
                          <el-icon><Rank /></el-icon>
                          移动到
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  
                  <!-- 用例操作 -->
                  <el-dropdown
                    v-else-if="data.type === 'case'"
                    @command="(cmd) => handleCaseAction(cmd, data)"
                    trigger="click"
                  >
                    <el-icon class="action-icon"><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="edit">
                          <el-icon><Edit /></el-icon>
                          编辑
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
            </template>
          </el-tree>
          
          <el-empty v-if="!loading && treeData.length === 0" description="暂无数据" :image-size="80" />
        </div>
      </div>

      <!-- 右侧详情栏 -->
      <div class="right-panel">
        <div v-if="!currentCase" class="empty-state">
          <el-empty description="请选择一个用例查看详情" :image-size="120">
            <template #image>
              <el-icon :size="120" color="#909399"><Document /></el-icon>
            </template>
          </el-empty>
        </div>
        
        <div v-else class="case-detail-panel">
          <div class="detail-header">
            <div class="detail-title">
              <div class="title-tags">
                <el-tag :type="getPriorityType(currentCase.priority)" size="large">
                  {{ currentCase.priority }}
                </el-tag>
                <el-tag size="large">
                  {{ currentCase.case_type }}
                </el-tag>
                <el-tag :type="getStatusType(currentCase.case_status)" size="large">
                  {{ currentCase.case_status }}
                </el-tag>
              </div>
              <h3>{{ currentCase.title }}</h3>
            </div>
            <div class="detail-actions">
              <el-button size="small" @click="editCurrentCase">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteCurrentCase">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>

          <el-scrollbar class="detail-content">
            <div class="detail-section">
              <div class="section-label">基本信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="用例编号">
                  <el-text type="primary">{{ currentCase.case_no }}</el-text>
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="getStatusType(currentCase.case_status)" size="small">
                    {{ currentCase.case_status }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="优先级">
                  <el-tag :type="getPriorityType(currentCase.priority)" size="small">
                    {{ currentCase.priority }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="用例类型">
                  {{ currentCase.case_type }}
                </el-descriptions-item>
                <el-descriptions-item label="所属目录" :span="2">
                  {{ getFolderName(currentCase.folder_id) }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间" :span="2">
                  {{ currentCase.created_at }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="detail-section">
              <div class="section-label">用例描述</div>
              <div class="content-box">
                {{ currentCase.description || '暂无描述' }}
              </div>
            </div>

            <div class="detail-section" v-if="currentCase.precondition">
              <div class="section-label">前置条件</div>
              <div class="content-box">
                {{ currentCase.precondition }}
              </div>
            </div>

            <div class="detail-section" v-if="currentCase.steps">
              <div class="section-label">测试步骤</div>
              <div class="content-box steps-box">
                <pre>{{ currentCase.steps }}</pre>
              </div>
            </div>

            <div class="detail-section" v-if="currentCase.expected_result">
              <div class="section-label">预期结果</div>
              <div class="content-box expected-box">
                {{ currentCase.expected_result }}
              </div>
            </div>

            <div class="detail-section" v-if="currentCase.api_ids && currentCase.api_ids.length > 0">
              <div class="section-label">绑定API</div>
              <div class="content-box">
                <el-tag v-for="apiId in currentCase.api_ids" :key="apiId" size="small" style="margin-right: 5px;">
                  API-{{ apiId }}
                </el-tag>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </div>
      <!-- 目录对话框 -->
      <el-dialog
        v-model="folderDialogVisible"
        :title="folderDialogTitle"
        width="500px"
        destroy-on-close
      >
        <el-form
          ref="folderFormRef"
          :model="folderForm"
          :rules="folderRules"
          label-width="100px"
        >
          <el-form-item label="目录名称" prop="name">
            <el-input v-model="folderForm.name" placeholder="请输入目录名称" />
          </el-form-item>
          <el-form-item label="目录描述">
            <el-input
              v-model="folderForm.description"
              type="textarea"
              :rows="3"
              placeholder="请输入目录描述"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="folderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitFolder" :loading="submitting">确定</el-button>
        </template>
      </el-dialog>

      <!-- 移动目录对话框 -->
      <el-dialog
        v-model="moveFolderDialogVisible"
        title="移动目录"
        width="500px"
        destroy-on-close
      >
        <p style="margin-bottom: 12px;">将「{{ movingFolder?.name }}」移动到：</p>
        <el-tree-select
          v-model="moveTargetParentId"
          :data="moveFolderOptions"
          :props="{ children: 'children', label: 'name', value: 'id' }"
          placeholder="选择目标父目录（不选则移到根级）"
          check-strictly
          clearable
          :render-after-expand="false"
          style="width: 100%;"
        />
        <template #footer>
          <el-button @click="moveFolderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitMoveFolder" :loading="submitting">确定</el-button>
        </template>
      </el-dialog>

      <!-- 用例对话框 -->
      <el-dialog
        v-model="caseDialogVisible"
        :title="caseDialogTitle"
        width="800px"
        :close-on-click-modal="false"
      >
        <el-form
          ref="caseFormRef"
          :model="caseForm"
          :rules="caseRules"
          label-width="100px"
        >
          <el-form-item label="用例标题" prop="title">
            <el-input v-model="caseForm.title" placeholder="请输入用例标题" />
          </el-form-item>

          <el-form-item label="用例描述">
            <el-input
              v-model="caseForm.description"
              type="textarea"
              :rows="3"
              placeholder="请详细描述用例"
            />
          </el-form-item>

          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="优先级" prop="priority">
                <el-select v-model="caseForm.priority" style="width: 100%;">
                  <el-option label="P0" value="P0" />
                  <el-option label="P1" value="P1" />
                  <el-option label="P2" value="P2" />
                  <el-option label="P3" value="P3" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="用例类型" prop="case_type">
                <el-select v-model="caseForm.case_type" style="width: 100%;">
                  <el-option label="功能" value="功能" />
                  <el-option label="性能" value="性能" />
                  <el-option label="安全" value="安全" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="用例状态" prop="case_status">
                <el-select v-model="caseForm.case_status" style="width: 100%;">
                  <el-option label="草稿" value="草稿" />
                  <el-option label="已评审" value="已评审" />
                  <el-option label="已废弃" value="已废弃" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="所属目录" prop="folder_id">
            <el-tree-select
              v-model="caseForm.folder_id"
              :data="folderOptions"
              :props="folderTreeProps"
              placeholder="请选择目录"
              check-strictly
              :render-after-expand="false"
              style="width: 100%;"
            />
          </el-form-item>

          <el-form-item label="前置条件">
            <el-input
              v-model="caseForm.precondition"
              type="textarea"
              :rows="2"
              placeholder="请描述前置条件"
            />
          </el-form-item>

          <el-form-item label="测试步骤">
            <el-input
              v-model="caseForm.steps"
              type="textarea"
              :rows="4"
              placeholder="请详细描述测试步骤，每行一个步骤"
            />
          </el-form-item>

          <el-form-item label="预期结果">
            <el-input
              v-model="caseForm.expected_result"
              type="textarea"
              :rows="2"
              placeholder="请描述预期结果"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="caseDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitCase" :loading="submitting">确定</el-button>
        </template>
      </el-dialog>
    </div>
  </main-layout>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  FolderOpened,
  Folder,
  FolderAdd,
  Connection,
  VideoPlay,
  Document,
  DocumentAdd,
  Setting,
  Search,
  Plus,
  MoreFilled,
  Refresh,
  Edit,
  Delete,
  Warning,
  MagicStick,
  Rank
} from '@element-plus/icons-vue'
import { getTestCases, getTestCase, createTestCase, updateTestCase, deleteTestCase as deleteTestCaseApi } from '../api/testCase'
import {
  getFolders,
  createFolder,
  updateFolder,
  deleteFolder,
  initProjectFolders,
  getTestCaseFolderTree
} from '../api/folder'
import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => parseInt(route.params.projectId))
const projectName = computed(() => route.query.projectName || '项目详情')

const loading = ref(false)
const treeData = ref([])
const treeRef = ref(null)
const treeProps = {
  children: 'children',
  label: 'name',
  isLeaf: (data) => data.type === 'case'
}
const searchKeyword = ref('')
const currentCase = ref(null)
const currentFolder = ref(null)

// 目录选项
const folderOptions = ref([])
const folderTreeProps = {
  children: 'children',
  label: 'name',
  value: 'id'
}

// 对话框状态
const folderDialogVisible = ref(false)
const caseDialogVisible = ref(false)
const folderDialogTitle = ref('新建目录')
const caseDialogTitle = ref('新建用例')
const submitting = ref(false)
const folderFormRef = ref(null)
const caseFormRef = ref(null)

// 表单数据
const folderForm = ref({
  id: null,
  name: '',
  description: '',
  parent_id: null,
  type: 'test_case'
})

// 移动目录相关状态
const moveFolderDialogVisible = ref(false)
const movingFolder = ref(null)
const moveTargetParentId = ref(null)
const moveFolderOptions = ref([])

const caseForm = ref({
  id: null,
  title: '',
  description: '',
  priority: 'P2',
  case_type: '功能',
  case_status: '草稿',
  folder_id: null,
  precondition: '',
  steps: '',
  expected_result: ''
})

// 表单验证规则
const folderRules = {
  name: [{ required: true, message: '请输入目录名称', trigger: 'blur' }]
}

const caseRules = {
  title: [{ required: true, message: '请输入用例标题', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  case_type: [{ required: true, message: '请选择用例类型', trigger: 'change' }],
  case_status: [{ required: true, message: '请选择用例状态', trigger: 'change' }],
  folder_id: [{ required: true, message: '请选择所属目录', trigger: 'change' }]
}

onMounted(() => {
  loadTree()
  loadFolders()
})

// 加载目录列表
const loadFolders = async () => {
  try {
    const res = await getFolders(projectId.value)
    folderOptions.value = res.data || []
  } catch (error) {
    console.error('加载目录列表失败:', error)
    ElMessage.error('加载目录列表失败')
  }
}

// 加载目录树
const loadTree = async () => {
  loading.value = true
  try {
    const res = await getTestCaseFolderTree(projectId.value)
    treeData.value = res.data || []
  } catch (error) {
    console.error('加载目录树失败:', error)
    ElMessage.error('加载目录树失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  ElMessage.info('搜索功能开发中...')
}

// 树节点点击
const handleNodeClick = async (data) => {
  if (data.type === 'case') {
    try {
      const res = await getTestCase(data.raw_id)
      currentCase.value = res  // 直接使用 res，不是 res.data
      currentFolder.value = null
    } catch (error) {
      console.error('加载用例详情失败:', error)
      ElMessage.error('加载用例详情失败')
    }
  } else if (data.type === 'folder') {
    currentFolder.value = data
    currentCase.value = null
  }
}

// 获取节点统计信息
const getNodeStats = (node) => {
  if (!node.children || node.children.length === 0) return '0'
  
  let folderCount = 0
  let caseCount = 0
  
  const countChildren = (children) => {
    for (const child of children) {
      if (child.type === 'folder') {
        folderCount++
        if (child.children) {
          countChildren(child.children)
        }
      } else if (child.type === 'case') {
        caseCount++
      }
    }
  }
  
  countChildren(node.children)
  
  const parts = []
  if (folderCount > 0) parts.push(`${folderCount}目录`)
  if (caseCount > 0) parts.push(`${caseCount}用例`)
  
  return parts.join(', ') || '0'
}

// 添加操作
const handleAddAction = (command) => {
  if (command === 'folder') {
    showCreateFolderDialog()
  } else if (command === 'case') {
    showCreateCaseDialog()
  }
}

// 更多操作
const handleMoreAction = async (command) => {
  if (command === 'refresh') {
    loadTree()
    loadFolders()
  } else if (command === 'init') {
    try {
      await initProjectFolders(projectId.value)
      ElMessage.success('初始化成功')
      loadTree()
      loadFolders()
    } catch (error) {
      console.error('初始化失败:', error)
      ElMessage.error('初始化失败')
    }
  }
}

// 目录操作
const handleFolderAction = (command, folder) => {
  switch (command) {
    case 'addFolder':
      showCreateFolderDialog(folder.raw_id || folder.id)
      break
    case 'addCase':
      showCreateCaseDialog(folder.raw_id || folder.id)
      break
    case 'rename':
      editFolder(folder)
      break
    case 'move':
      showMoveFolderDialog(folder)
      break
    case 'delete':
      deleteFolderConfirm(folder)
      break
  }
}

// 用例操作
const handleCaseAction = (command, testCase) => {
  switch (command) {
    case 'edit':
      editCase(testCase)
      break
    case 'delete':
      deleteCaseConfirm(testCase)
      break
  }
}

// 显示创建目录对话框
const showCreateFolderDialog = (parentId = null) => {
  folderDialogTitle.value = '新建目录'
  folderForm.value = {
    id: null,
    name: '',
    description: '',
    parent_id: parentId,
    type: 'test_case'
  }
  folderDialogVisible.value = true
  nextTick(() => {
    folderFormRef.value?.clearValidate()
  })
}

// 编辑目录
const editFolder = (folder) => {
  folderDialogTitle.value = '编辑目录'
  folderForm.value = {
    id: folder.raw_id || folder.id,
    name: folder.name,
    description: folder.description,
    parent_id: folder.parent_id,
    type: 'test_case'
  }
  folderDialogVisible.value = true
}

// 移动目录
const showMoveFolderDialog = (folder) => {
  movingFolder.value = folder
  moveTargetParentId.value = folder.parent_id || null
  const folderId = folder.raw_id || folder.id
  const filterSelfAndChildren = (nodes) => {
    return nodes
      .filter(n => n.type === 'folder' && (n.raw_id || n.id) !== folderId)
      .map(n => ({
        id: n.raw_id || n.id,
        name: n.name,
        children: n.children ? filterSelfAndChildren(n.children) : []
      }))
  }
  moveFolderOptions.value = filterSelfAndChildren(treeData.value)
  moveFolderDialogVisible.value = true
}

const submitMoveFolder = async () => {
  if (!movingFolder.value) return
  const folderId = movingFolder.value.raw_id || movingFolder.value.id
  submitting.value = true
  try {
    await updateFolder(projectId.value, folderId, { parent_id: moveTargetParentId.value })
    ElMessage.success('移动成功')
    moveFolderDialogVisible.value = false
    loadTree()
    loadFolders()
  } catch (error) {
    console.error('移动失败:', error)
    ElMessage.error('移动失败')
  } finally {
    submitting.value = false
  }
}

// 提交目录表单
const submitFolder = async () => {
  if (!folderFormRef.value) return

  await folderFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (folderForm.value.id) {
        await updateFolder(projectId.value, folderForm.value.id, folderForm.value)
        ElMessage.success('更新成功')
      } else {
        await createFolder(projectId.value, folderForm.value)
        ElMessage.success('创建成功')
      }
      folderDialogVisible.value = false
      loadTree()
      loadFolders()
    } catch (error) {
      console.error('操作失败:', error)
      ElMessage.error(folderForm.value.id ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

// 删除目录确认
const deleteFolderConfirm = (folder) => {
  ElMessageBox.confirm(
    `确定要删除目录"${folder.name}"吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteFolder(projectId.value, folder.raw_id || folder.id)
      ElMessage.success('删除成功')
      loadTree()
      loadFolders()
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 显示创建用例对话框
const showCreateCaseDialog = (folderId = null) => {
  caseDialogTitle.value = '新建用例'
  caseForm.value = {
    id: null,
    title: '',
    description: '',
    priority: 'P2',
    case_type: '功能',
    case_status: '草稿',
    folder_id: folderId,
    precondition: '',
    steps: '',
    expected_result: '',
    project_id: projectId.value
  }
  caseDialogVisible.value = true
}

// 编辑用例
const editCase = (testCase) => {
  caseDialogTitle.value = '编辑用例'
  caseForm.value = {
    id: testCase.id || testCase.raw_id,
    title: testCase.title,
    description: testCase.description,
    priority: testCase.priority,
    case_type: testCase.case_type,
    case_status: testCase.case_status,
    folder_id: testCase.folder_id,
    precondition: testCase.precondition,
    steps: testCase.steps,
    expected_result: testCase.expected_result,
    project_id: projectId.value
  }
  caseDialogVisible.value = true
}

// 编辑当前用例
const editCurrentCase = () => {
  if (currentCase.value) {
    editCase(currentCase.value)
  }
}

// 提交用例表单
const submitCase = async () => {
  if (!caseFormRef.value) return

  await caseFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (caseForm.value.id) {
        await updateTestCase(caseForm.value.id, caseForm.value)
        ElMessage.success('更新成功')
      } else {
        await createTestCase(caseForm.value)
        ElMessage.success('创建成功')
      }
      caseDialogVisible.value = false
      loadTree()
      if (currentCase.value && caseForm.value.id === currentCase.value.id) {
        // 重新加载当前用例的最新数据
        const res = await getTestCase(caseForm.value.id)
        currentCase.value = res  // 直接使用 res，不是 res.data
      }
    } catch (error) {
      console.error('操作失败:', error)
      ElMessage.error(caseForm.value.id ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

// 删除用例确认
const deleteCaseConfirm = (testCase) => {
  const caseToDelete = testCase || currentCase.value
  if (!caseToDelete) return

  ElMessageBox.confirm(
    `确定要删除用例"${caseToDelete.title}"吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteTestCaseApi(caseToDelete.id || caseToDelete.raw_id)
      ElMessage.success('删除成功')
      loadTree()
      if (currentCase.value && currentCase.value.id === caseToDelete.id) {
        currentCase.value = null
      }
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 删除当前用例
const deleteCurrentCase = () => {
  deleteCaseConfirm(currentCase.value)
}

// 获取目录名称
const getFolderName = (folderId) => {
  const findFolder = (folders) => {
    for (const folder of folders) {
      if (folder.id === folderId || folder.raw_id === folderId) {
        return folder.name
      }
      if (folder.children) {
        const found = findFolder(folder.children)
        if (found) return found
      }
    }
    return null
  }
  return findFolder(folderOptions.value) || '-'
}

// 状态相关
const getStatusType = (status) => {
  const typeMap = {
    '草稿': 'info',
    '已评审': 'success',
    '已废弃': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusShort = (status) => {
  const textMap = {
    '草稿': '草稿',
    '已评审': '评审',
    '已废弃': '废弃'
  }
  return textMap[status] || status
}

// 优先级相关
const getPriorityType = (priority) => {
  const typeMap = {
    'P0': 'danger',
    'P1': 'warning',
    'P2': '',
    'P3': 'info'
  }
  return typeMap[priority] || 'info'
}
</script>

<style scoped>
.test-case-layout {
  display: flex;
  height: calc(100vh - 90px);
  background: var(--el-bg-color-page);
}

/* 中间面板 */
.middle-panel {
  width: 350px;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 15px;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  gap: 10px;
}

.header-actions {
  display: flex;
  gap: 5px;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 10px;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.node-icon {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.folder-icon {
  color: var(--el-color-warning);
}

.priority-tag {
  font-size: 10px;
  padding: 0 4px;
  flex-shrink: 0;
  font-weight: bold;
}

.status-tag {
  font-size: 10px;
  padding: 0 4px;
  flex-shrink: 0;
  margin-left: auto;
}

.node-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.node-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 5px;
  flex-shrink: 0;
}

.node-actions {
  opacity: 0;
  transition: opacity 0.3s;
  flex-shrink: 0;
}

.tree-node:hover .node-actions {
  opacity: 1;
}

.action-icon {
  cursor: pointer;
  color: var(--el-text-color-secondary);
  font-size: 16px;
  transition: color 0.3s;
}

.action-icon:hover {
  color: var(--el-color-primary);
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  background: var(--el-bg-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.case-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  padding: 20px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.detail-title {
  margin-bottom: 15px;
}

.title-tags {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.detail-title h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.detail-actions {
  display: flex;
  gap: 10px;
}

.detail-actions .el-button {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
}

.detail-actions .el-button:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.5);
}

.detail-content {
  flex: 1;
  padding: 20px;
}

.detail-section {
  margin-bottom: 25px;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
  padding-left: 10px;
  border-left: 3px solid var(--el-color-primary);
}

.content-box {
  padding: 15px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  border: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-regular);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.steps-box pre {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
}

.expected-box {
  border-left: 3px solid var(--el-color-success);
}

/* 树形组件样式 */
:deep(.el-tree-node__content) {
  height: 36px;
  border-radius: 4px;
  margin-bottom: 2px;
}

:deep(.el-tree-node__content:hover) {
  background-color: var(--el-fill-color-light);
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: #e6f7ff;
  color: var(--el-color-primary);
}

/* 描述列表样式 */
:deep(.el-descriptions__label) {
  font-weight: 500;
}

/* 滚动条样式 */
.tree-container::-webkit-scrollbar,
.detail-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.tree-container::-webkit-scrollbar-thumb,
.detail-content::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 3px;
}

.tree-container::-webkit-scrollbar-thumb:hover,
.detail-content::-webkit-scrollbar-thumb:hover {
  background: var(--el-text-color-placeholder);
}

/* 响应式 */
@media (max-width: 1200px) {
  .middle-panel {
    width: 300px;
  }
}
</style>
