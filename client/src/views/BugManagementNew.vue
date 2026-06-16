<template>
  <main-layout>
    <div class="bug-management-layout">
      <!-- 左侧功能模块栏 -->
      <project-sidebar
        active-module="bug"
        :project-id="projectId"
        :project-name="projectName"
        @stay="loadTree(); loadFolders()"
      />

      <!-- 中间Bug列表栏 -->
      <div class="middle-panel">
        <div class="panel-header">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索Bug"
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
                  <el-dropdown-item command="bug">
                    <el-icon><Warning /></el-icon>
                    新建Bug
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
            node-key="_node_key"
            :expand-on-click-node="true"
            :highlight-current="true"
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
                  
                  <!-- Bug优先级标签 -->
                  <el-tag
                    v-else-if="data.type === 'bug'"
                    :type="getPriorityType(data.priority)"
                    size="small"
                    class="priority-tag"
                  >
                    {{ getPriorityShort(data.priority) }}
                  </el-tag>
                  
                  <!-- 节点名称 -->
                  <span class="node-label" :title="data.description || data.name || data.title">
                    {{ data.name || data.title }}
                  </span>
                  
                  <!-- Bug状态标签 -->
                  <el-tag
                    v-if="data.type === 'bug'"
                    :type="getStatusType(data.status)"
                    size="small"
                    class="status-tag"
                  >
                    {{ getStatusShort(data.status) }}
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
                        <el-dropdown-item command="addBug">
                          <el-icon><DocumentAdd /></el-icon>
                          新建Bug
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
                  
                  <!-- Bug操作 -->
                  <el-dropdown
                    v-else-if="data.type === 'bug'"
                    @command="(cmd) => handleBugAction(cmd, data)"
                    trigger="click"
                  >
                    <el-icon class="action-icon"><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="edit">
                          <el-icon><Edit /></el-icon>
                          编辑
                        </el-dropdown-item>
                        <el-dropdown-item command="resolve" v-if="data.status !== 'resolved'">
                          <el-icon><CircleCheck /></el-icon>
                          解决
                        </el-dropdown-item>
                        <el-dropdown-item command="reopen" v-if="data.status === 'resolved'">
                          <el-icon><RefreshRight /></el-icon>
                          重新打开
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
        <div v-if="!currentBug" class="empty-state">
          <el-empty description="请选择一个Bug查看详情" :image-size="120">
            <template #image>
              <el-icon :size="120" color="#909399"><Warning /></el-icon>
            </template>
          </el-empty>
        </div>
        
        <div v-else class="bug-detail-panel">
          <div class="detail-header">
            <div class="detail-title">
              <div class="title-tags">
                <el-tag :type="getPriorityType(currentBug.priority)" size="large">
                  {{ getPriorityText(currentBug.priority) }}
                </el-tag>
                <el-tag :type="getSeverityType(currentBug.severity)" size="large">
                  {{ getSeverityText(currentBug.severity) }}
                </el-tag>
                <el-tag :type="getStatusType(currentBug.status)" size="large">
                  {{ getStatusText(currentBug.status) }}
                </el-tag>
              </div>
              <h3>{{ currentBug.title }}</h3>
            </div>
            <div class="detail-actions">
              <el-button size="small" v-if="currentBug.status !== 'resolved'" type="success" @click="showResolveDialog">
                <el-icon><CircleCheck /></el-icon>
                解决
              </el-button>
              <el-button size="small" v-if="currentBug.status === 'resolved'" type="warning" @click="reopenBugConfirm">
                <el-icon><RefreshRight /></el-icon>
                重新打开
              </el-button>
              <el-button size="small" @click="editCurrentBug">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteCurrentBug">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>

          <el-scrollbar class="detail-content">
            <div class="detail-section">
              <div class="section-label">基本信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="Bug ID">
                  <el-text type="primary">#{{ currentBug.id }}</el-text>
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="getStatusType(currentBug.status)" size="small">
                    {{ getStatusText(currentBug.status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="优先级">
                  <el-tag :type="getPriorityType(currentBug.priority)" size="small">
                    {{ getPriorityText(currentBug.priority) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="严重程度">
                  <el-tag :type="getSeverityType(currentBug.severity)" size="small">
                    {{ getSeverityText(currentBug.severity) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="分类">
                  {{ currentBug.category || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="模块">
                  {{ currentBug.module || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="测试环境">
                  {{ currentBug.environment || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="发现版本">
                  {{ currentBug.version || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间" :span="2">
                  {{ currentBug.created_at }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="detail-section">
              <div class="section-label">Bug描述</div>
              <div class="content-box">
                {{ currentBug.description || '暂无描述' }}
              </div>
            </div>

            <div class="detail-section" v-if="currentBug.steps_to_reproduce">
              <div class="section-label">复现步骤</div>
              <div class="content-box steps-box">
                <pre>{{ currentBug.steps_to_reproduce }}</pre>
              </div>
            </div>

            <div class="detail-section" v-if="currentBug.expected_result || currentBug.actual_result">
              <div class="section-label">预期与实际结果</div>
              <el-row :gutter="15">
                <el-col :span="12">
                  <div class="result-label">预期结果</div>
                  <div class="content-box expected-box">
                    {{ currentBug.expected_result || '-' }}
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="result-label">实际结果</div>
                  <div class="content-box actual-box">
                    {{ currentBug.actual_result || '-' }}
                  </div>
                </el-col>
              </el-row>
            </div>

            <div class="detail-section" v-if="currentBug.resolution">
              <div class="section-label">解决信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="解决方案">
                  <el-tag type="success" size="small">{{ getResolutionText(currentBug.resolution) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="解决时间">
                  {{ currentBug.resolved_at || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="解决说明" :span="2">
                  <div class="content-box">
                    {{ currentBug.resolution_note || '-' }}
                  </div>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-scrollbar>
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
          ref="folderFormRef"
          :model="folderForm"
          :rules="folderRules"
          label-width="80px"
        >
          <el-form-item label="目录名称" prop="name">
            <el-input v-model="folderForm.name" placeholder="请输入目录名称" />
          </el-form-item>
          <el-form-item label="描述">
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

      <!-- 创建/编辑Bug对话框 -->
      <el-dialog
        v-model="bugDialogVisible"
        :title="bugDialogTitle"
        width="800px"
        :close-on-click-modal="false"
      >
        <el-form
          ref="bugFormRef"
          :model="bugForm"
          :rules="bugRules"
          label-width="100px"
        >
          <el-form-item label="Bug标题" prop="title">
            <el-input v-model="bugForm.title" placeholder="请输入Bug标题" />
          </el-form-item>

          <el-form-item label="Bug描述">
            <el-input
              v-model="bugForm.description"
              type="textarea"
              :rows="3"
              placeholder="请详细描述Bug"
            />
          </el-form-item>

          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="状态" prop="status">
                <el-select v-model="bugForm.status" style="width: 100%;">
                  <el-option label="待处理" value="open" />
                  <el-option label="处理中" value="in_progress" />
                  <el-option label="已解决" value="resolved" />
                  <el-option label="已关闭" value="closed" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="优先级" prop="priority">
                <el-select v-model="bugForm.priority" style="width: 100%;">
                  <el-option label="低" value="low" />
                  <el-option label="中" value="medium" />
                  <el-option label="高" value="high" />
                  <el-option label="紧急" value="critical" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="严重程度" prop="severity">
                <el-select v-model="bugForm.severity" style="width: 100%;">
                  <el-option label="轻微" value="trivial" />
                  <el-option label="次要" value="minor" />
                  <el-option label="一般" value="normal" />
                  <el-option label="严重" value="major" />
                  <el-option label="致命" value="critical" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="分类">
                <el-input v-model="bugForm.category" placeholder="如：UI、后端、性能" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="模块">
                <el-input v-model="bugForm.module" placeholder="如：用户管理、登录" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="所属目录" prop="folder_id">
            <el-tree-select
              v-model="bugForm.folder_id"
              :data="folderOptions"
              :props="folderTreeProps"
              placeholder="请选择目录"
              check-strictly
              :render-after-expand="false"
              style="width: 100%;"
            />
          </el-form-item>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="测试环境">
                <el-input v-model="bugForm.environment" placeholder="如：Chrome 120, Windows 11" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="发现版本">
                <el-input v-model="bugForm.version" placeholder="如：v1.0.0" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="复现步骤">
            <el-input
              v-model="bugForm.steps_to_reproduce"
              type="textarea"
              :rows="4"
              placeholder="请详细描述复现步骤，每行一个步骤"
            />
          </el-form-item>

          <el-form-item label="预期结果">
            <el-input
              v-model="bugForm.expected_result"
              type="textarea"
              :rows="2"
              placeholder="请描述预期的正确结果"
            />
          </el-form-item>

          <el-form-item label="实际结果">
            <el-input
              v-model="bugForm.actual_result"
              type="textarea"
              :rows="2"
              placeholder="请描述实际出现的错误结果"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="bugDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitBug" :loading="submitting">确定</el-button>
        </template>
      </el-dialog>

      <!-- 解决Bug对话框 -->
      <el-dialog
        v-model="resolveDialogVisible"
        title="解决Bug"
        width="600px"
      >
        <el-form
          ref="resolveFormRef"
          :model="resolveForm"
          :rules="resolveRules"
          label-width="100px"
        >
          <el-form-item label="解决方案" prop="resolution">
            <el-select v-model="resolveForm.resolution" style="width: 100%;">
              <el-option label="已修复" value="fixed" />
              <el-option label="不修复" value="wont_fix" />
              <el-option label="重复" value="duplicate" />
              <el-option label="无法复现" value="cannot_reproduce" />
              <el-option label="按设计" value="by_design" />
            </el-select>
          </el-form-item>

          <el-form-item label="解决说明">
            <el-input
              v-model="resolveForm.resolution_note"
              type="textarea"
              :rows="4"
              placeholder="请描述解决方案的详细信息"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="resolveDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitResolve" :loading="submitting">确定</el-button>
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
  MagicStick,
  Warning,
  CircleCheck,
  RefreshRight,
  Rank
} from '@element-plus/icons-vue'
import {
  getBugs,
  getBug,
  createBug,
  updateBug,
  deleteBug,
  resolveBug,
  reopenBug,
  getBugTree
} from '../api/bug'
import {
  getFolders,
  createFolder,
  updateFolder,
  deleteFolder,
  initProjectFolders
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
  isLeaf: (data) => data.type === 'bug'
}
const searchKeyword = ref('')
const currentBug = ref(null)
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
const bugDialogVisible = ref(false)
const resolveDialogVisible = ref(false)
const folderDialogTitle = ref('新建目录')
const bugDialogTitle = ref('新建Bug')
const submitting = ref(false)
const folderFormRef = ref(null)
const bugFormRef = ref(null)
const resolveFormRef = ref(null)

// 表单数据
const folderForm = ref({
  id: null,
  name: '',
  description: '',
  parent_id: null,
  type: 'bug'
})

// 移动目录相关状态
const moveFolderDialogVisible = ref(false)
const movingFolder = ref(null)
const moveTargetParentId = ref(null)
const moveFolderOptions = ref([])

const bugForm = ref({
  id: null,
  title: '',
  description: '',
  status: 'open',
  priority: 'medium',
  severity: 'normal',
  category: '',
  module: '',
  environment: '',
  version: '',
  folder_id: null,
  steps_to_reproduce: '',
  expected_result: '',
  actual_result: ''
})

const resolveForm = ref({
  resolution: 'fixed',
  resolution_note: ''
})

// 表单验证规则
const folderRules = {
  name: [{ required: true, message: '请输入目录名称', trigger: 'blur' }]
}

const bugRules = {
  title: [{ required: true, message: '请输入Bug标题', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }],
  folder_id: [{ required: true, message: '请选择所属目录', trigger: 'change' }]
}

const resolveRules = {
  resolution: [{ required: true, message: '请选择解决方案', trigger: 'change' }]
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
    const res = await getBugTree(projectId.value)
    treeData.value = injectNodeKeys(res.data || [])
  } catch (error) {
    console.error('加载目录树失败:', error)
    ElMessage.error('加载目录树失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  // TODO: 实现搜索功能
  ElMessage.info('搜索功能开发中...')
}

// 树节点点击
const handleNodeClick = async (data) => {
  if (data.type === 'bug') {
    try {
      const res = await getBug(projectId.value, data.raw_id)
      currentBug.value = res.data
      currentFolder.value = null
    } catch (error) {
      console.error('加载Bug详情失败:', error)
      ElMessage.error('加载Bug详情失败')
    }
  } else if (data.type === 'folder') {
    currentFolder.value = data
    currentBug.value = null
  }
}

// 点击整行时由 el-tree 自动 toggle 展开（expand-on-click-node="true"），
// 这里不再手动处理展开逻辑，仅保留业务点击。

// 给树上每个节点注入跨类型唯一的 key（type_rawId）
// 因为 folder/bug 各自的 raw_id 来自不同表，仅用 raw_id 会撞 → setCurrentKey 等会跳错节点
const injectNodeKeys = (nodes) => {
  for (const n of nodes) {
    n._node_key = `${n.type}_${n.raw_id ?? n.id}`
    if (n.children && n.children.length) injectNodeKeys(n.children)
  }
  return nodes
}

// 获取节点统计信息
const getNodeStats = (node) => {
  if (!node.children || node.children.length === 0) return '0'
  
  let folderCount = 0
  let bugCount = 0
  
  const countChildren = (children) => {
    for (const child of children) {
      if (child.type === 'folder') {
        folderCount++
        if (child.children) {
          countChildren(child.children)
        }
      } else if (child.type === 'bug') {
        bugCount++
      }
    }
  }
  
  countChildren(node.children)
  
  const parts = []
  if (folderCount > 0) parts.push(`${folderCount}目录`)
  if (bugCount > 0) parts.push(`${bugCount}Bug`)
  
  return parts.join(', ') || '0'
}

// 添加操作
const handleAddAction = (command) => {
  if (command === 'folder') {
    showCreateFolderDialog()
  } else if (command === 'bug') {
    showCreateBugDialog()
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
    case 'addBug':
      showCreateBugDialog(folder.raw_id || folder.id)
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

// Bug操作
const handleBugAction = (command, bug) => {
  switch (command) {
    case 'edit':
      editBug(bug)
      break
    case 'resolve':
      currentBug.value = bug
      showResolveDialog()
      break
    case 'reopen':
      reopenBugConfirm(bug)
      break
    case 'delete':
      deleteBugConfirm(bug)
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
    type: 'bug'
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
    type: 'bug'
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
      loadFolders() // 刷新目录列表
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
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 显示创建Bug对话框
const showCreateBugDialog = (folderId = null) => {
  bugDialogTitle.value = '新建Bug'
  bugForm.value = {
    id: null,
    title: '',
    description: '',
    status: 'open',
    priority: 'medium',
    severity: 'normal',
    category: '',
    module: '',
    environment: '',
    version: '',
    folder_id: folderId,
    steps_to_reproduce: '',
    expected_result: '',
    actual_result: ''
  }
  bugDialogVisible.value = true
}

// 编辑Bug
const editBug = (bug) => {
  bugDialogTitle.value = '编辑Bug'
  bugForm.value = {
    id: bug.raw_id || bug.id,
    title: bug.title,
    description: bug.description,
    status: bug.status,
    priority: bug.priority,
    severity: bug.severity,
    category: bug.category,
    module: bug.module,
    environment: bug.environment,
    version: bug.version,
    folder_id: bug.folder_id,
    steps_to_reproduce: bug.steps_to_reproduce,
    expected_result: bug.expected_result,
    actual_result: bug.actual_result
  }
  bugDialogVisible.value = true
}

// 编辑当前Bug
const editCurrentBug = () => {
  if (currentBug.value) {
    editBug(currentBug.value)
  }
}

// 提交Bug表单
const submitBug = async () => {
  if (!bugFormRef.value) return

  await bugFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (bugForm.value.id) {
        await updateBug(projectId.value, bugForm.value.id, bugForm.value)
        ElMessage.success('更新成功')
      } else {
        await createBug(projectId.value, bugForm.value)
        ElMessage.success('创建成功')
      }
      bugDialogVisible.value = false
      loadTree()
      if (currentBug.value && bugForm.value.id === currentBug.value.id) {
        const res = await getBug(projectId.value, bugForm.value.id)
        currentBug.value = res.data
      }
    } catch (error) {
      console.error('操作失败:', error)
      ElMessage.error(bugForm.value.id ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

// 删除Bug确认
const deleteBugConfirm = (bug) => {
  const bugToDelete = bug || currentBug.value
  if (!bugToDelete) return

  ElMessageBox.confirm(
    `确定要删除Bug"${bugToDelete.title || bugToDelete.name}"吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteBug(projectId.value, bugToDelete.raw_id || bugToDelete.id)
      ElMessage.success('删除成功')
      loadTree()
      if (currentBug.value && (currentBug.value.id === bugToDelete.id || currentBug.value.id === bugToDelete.raw_id)) {
        currentBug.value = null
      }
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 删除当前Bug
const deleteCurrentBug = () => {
  deleteBugConfirm(currentBug.value)
}

// 显示解决对话框
const showResolveDialog = () => {
  resolveForm.value = {
    resolution: 'fixed',
    resolution_note: ''
  }
  resolveDialogVisible.value = true
}

// 提交解决
const submitResolve = async () => {
  if (!resolveFormRef.value) return

  await resolveFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      await resolveBug(projectId.value, currentBug.value.id, resolveForm.value)
      ElMessage.success('Bug已解决')
      resolveDialogVisible.value = false
      loadTree()
      const res = await getBug(projectId.value, currentBug.value.id)
      currentBug.value = res.data
    } catch (error) {
      console.error('解决失败:', error)
      ElMessage.error('解决失败')
    } finally {
      submitting.value = false
    }
  })
}

// 重新打开Bug确认
const reopenBugConfirm = (bug) => {
  const bugToReopen = bug || currentBug.value
  if (!bugToReopen) return

  ElMessageBox.confirm(
    '确定要重新打开这个Bug吗？',
    '确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await reopenBug(projectId.value, bugToReopen.raw_id || bugToReopen.id)
      ElMessage.success('Bug已重新打开')
      loadTree()
      if (currentBug.value && (currentBug.value.id === bugToReopen.id || currentBug.value.id === bugToReopen.raw_id)) {
        const res = await getBug(projectId.value, bugToReopen.raw_id || bugToReopen.id)
        currentBug.value = res.data
      }
    } catch (error) {
      console.error('重新打开失败:', error)
      ElMessage.error('重新打开失败')
    }
  }).catch(() => {})
}

// 状态相关
const getStatusType = (status) => {
  const typeMap = {
    open: 'warning',
    in_progress: 'primary',
    resolved: 'success',
    closed: 'info',
    reopened: 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    open: '待处理',
    in_progress: '处理中',
    resolved: '已解决',
    closed: '已关闭',
    reopened: '重新打开'
  }
  return textMap[status] || status
}

const getStatusShort = (status) => {
  const textMap = {
    open: '待处理',
    in_progress: '处理中',
    resolved: '已解决',
    closed: '已关闭',
    reopened: '重开'
  }
  return textMap[status] || status
}

// 优先级相关
const getPriorityType = (priority) => {
  const typeMap = {
    low: 'info',
    medium: '',
    high: 'warning',
    critical: 'danger'
  }
  return typeMap[priority] || 'info'
}

const getPriorityText = (priority) => {
  const textMap = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '紧急'
  }
  return textMap[priority] || priority
}

const getPriorityShort = (priority) => {
  const textMap = {
    low: 'P3',
    medium: 'P2',
    high: 'P1',
    critical: 'P0'
  }
  return textMap[priority] || priority
}

// 严重程度相关
const getSeverityType = (severity) => {
  const typeMap = {
    trivial: 'info',
    minor: '',
    normal: 'primary',
    major: 'warning',
    critical: 'danger'
  }
  return typeMap[severity] || 'info'
}

const getSeverityText = (severity) => {
  const textMap = {
    trivial: '轻微',
    minor: '次要',
    normal: '一般',
    major: '严重',
    critical: '致命'
  }
  return textMap[severity] || severity
}

// 解决方案相关
const getResolutionText = (resolution) => {
  const textMap = {
    fixed: '已修复',
    wont_fix: '不修复',
    duplicate: '重复',
    cannot_reproduce: '无法复现',
    by_design: '按设计'
  }
  return textMap[resolution] || resolution
}
</script>

<style scoped>
.bug-management-layout {
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

.bug-detail-panel {
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

.result-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.expected-box {
  border-left: 3px solid var(--el-color-success);
}

.actual-box {
  border-left: 3px solid var(--el-color-danger);
}

/* 树形组件样式 */
:deep(.el-tree-node__content) {
  height: 30px;
  border-radius: 4px;
}

/* 让所有层级的整行都满宽，hover/选中阴影在 1 级、2 级、3 级看起来等宽 */
:deep(.el-tree-node__children) {
  padding-left: 0;
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
