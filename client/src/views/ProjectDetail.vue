<template>
  <main-layout>
    <div class="project-detail-layout">
      <!-- 左侧功能模块栏 -->
      <project-sidebar
        active-module="api"
        :project-id="projectId"
        :project-name="projectName"
        @stay="loadTree(); loadCategories()"
      />

      <!-- 中间接口列表栏 -->
      <div class="middle-panel">
        <div class="panel-header">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索接口"
            clearable
            size="small"
            spellcheck="false"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          
          <div class="header-actions">
            <el-dropdown @command="handleAddAction" trigger="click">
              <el-button type="primary" size="small" class="add-btn">
                <el-icon><Plus /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="folder">
                    <el-icon><Folder /></el-icon>
                    新建目录
                  </el-dropdown-item>
                  <el-dropdown-item command="api">
                    <el-icon><Connection /></el-icon>
                    新建接口
                  </el-dropdown-item>
                  <el-dropdown-item command="importCurl" divided>
                    <el-icon><Upload /></el-icon>
                    导入cURL
                  </el-dropdown-item>
                  <el-dropdown-item command="batchImport">
                    <el-icon><Upload /></el-icon>
                    批量导入
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
            node-key="raw_id"
            :expand-on-click-node="false"
            :highlight-current="true"
            :indent="0"
            @node-click="handleNodeClick"
            @node-contextmenu="handleNodeContextMenu"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <div class="node-content">
                  <!-- 目录图标 -->
                  <el-icon v-if="data.type === 'folder'" class="node-icon folder-icon">
                    <Folder v-if="!node.expanded" />
                    <FolderOpened v-else />
                  </el-icon>
                  
                  <!-- 接口标签 -->
                  <el-tag
                    v-else-if="data.type === 'api'"
                    :type="getMethodType(data.method)"
                    size="small"
                    class="method-tag"
                  >
                    {{ data.method }}
                  </el-tag>
                  
                  <!-- 用例图标（预留） -->
                  <el-icon v-else-if="data.type === 'case'" class="node-icon case-icon">
                    <Document />
                  </el-icon>
                  
                  <!-- 节点名称 -->
                  <span class="node-label" :title="data.description || data.name">
                    {{ data.name }}
                  </span>
                  
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
                        <el-dropdown-item command="addApi">
                          <el-icon><DocumentAdd /></el-icon>
                          新建接口
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
                  
                  <!-- 接口操作 -->
                  <el-dropdown
                    v-else-if="data.type === 'api'"
                    @command="(cmd) => handleApiAction(cmd, data)"
                    trigger="click"
                  >
                    <el-icon class="action-icon"><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="copy">
                          <el-icon><DocumentCopy /></el-icon>
                          复制
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
        <!-- Tab 栏 -->
        <api-tabs
          :tabs="openTabs"
          :active-tab-id="activeTabId"
          :environments="environmentList"
          :current-env-id="currentEnvId"
          @select="switchTab"
          @close="closeTab"
          @close-others="closeOtherTabs"
          @close-left="closeLeftTabs"
          @close-right="closeRightTabs"
          @close-all="closeAllTabs"
          @switch-env="handleSwitchEnv"
          @open-env-manager="envManagerVisible = true"
        />

        <div v-if="openTabs.length === 0" class="empty-state">
          <el-empty description="请选择一个接口查看详情" :image-size="120" />
        </div>

        <api-detail-panel
          v-else-if="activeTab"
          :key="activeTabId"
          ref="detailPanelRef"
          :editable-api="activeTab.editableApi"
          :response-data="activeTab.responseData"
          :testing="testingApi"
          :saving="savingApi"
          :folder-id="activeTab.folderId"
          :folder-options="folderTreeOptions"
          :api-data="activeTab.apiData"
          :prefix-urls="currentEnvPrefixUrls"
          @send="sendRequest"
          @save="saveApiChanges"
          @update:folder-id="(val) => { activeTab.folderId = val }"
        />
      </div>

      <!-- 测试结果对话框 -->
      <el-dialog
        v-model="testResultDialogVisible"
        title="测试结果"
        width="900px"
        :close-on-click-modal="false"
      >
        <div v-if="testResult" class="test-result">
          <!-- 基本信息 -->
          <div class="result-header">
            <el-tag :type="testResult.success ? 'success' : 'danger'" size="large">
              {{ testResult.success ? '成功' : '失败' }}
            </el-tag>
            <span class="duration">耗时: {{ testResult.duration }}s</span>
            <span class="timestamp">{{ testResult.timestamp }}</span>
          </div>

          <!-- 请求信息 -->
          <el-divider content-position="left">请求信息</el-divider>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="请求方法">
              <el-tag :type="getMethodType(testResult.request.method)" size="small">
                {{ testResult.request.method }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="请求URL">
              {{ testResult.request.url }}
            </el-descriptions-item>
          </el-descriptions>
          
          <el-tabs type="border-card" style="margin-top: 15px;">
            <el-tab-pane label="Headers">
              <pre class="json-view">{{ JSON.stringify(testResult.request.headers, null, 2) }}</pre>
            </el-tab-pane>
            <el-tab-pane label="Params">
              <pre class="json-view">{{ JSON.stringify(testResult.request.params, null, 2) }}</pre>
            </el-tab-pane>
            <el-tab-pane label="Body">
              <pre class="json-view">{{ JSON.stringify(testResult.request.body, null, 2) }}</pre>
            </el-tab-pane>
          </el-tabs>

          <!-- 响应信息 -->
          <el-divider content-position="left">响应信息</el-divider>
          <div v-if="testResult.response">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="状态码">
                <el-tag :type="getStatusCodeType(testResult.response.status_code)" size="small">
                  {{ testResult.response.status_code }} {{ testResult.response.status_text }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="响应大小">
                {{ formatSize(testResult.response.size) }}
              </el-descriptions-item>
              <el-descriptions-item label="编码">
                {{ testResult.response.encoding || '-' }}
              </el-descriptions-item>
            </el-descriptions>
            
            <el-tabs type="border-card" style="margin-top: 15px;">
              <el-tab-pane label="Response Body">
                <pre class="json-view">{{ formatResponseBody(testResult.response.body) }}</pre>
              </el-tab-pane>
              <el-tab-pane label="Response Headers">
                <pre class="json-view">{{ JSON.stringify(testResult.response.headers, null, 2) }}</pre>
              </el-tab-pane>
            </el-tabs>
          </div>

          <!-- 错误信息 -->
          <div v-if="testResult.error">
            <el-alert
              :title="testResult.error.type"
              type="error"
              :description="testResult.error.message"
              show-icon
              :closable="false"
            />
          </div>

          <!-- 验证结果 -->
          <div v-if="testResult.validation">
            <el-divider content-position="left">验证结果</el-divider>
            <el-alert
              :title="testResult.validation.passed ? '验证通过' : '验证失败'"
              :type="testResult.validation.passed ? 'success' : 'error'"
              show-icon
              :closable="false"
            >
              <ul v-if="testResult.validation.failures && testResult.validation.failures.length > 0">
                <li v-for="(failure, index) in testResult.validation.failures" :key="index">
                  {{ failure }}
                </li>
              </ul>
            </el-alert>
          </div>
        </div>
        
        <template #footer>
          <el-button @click="testResultDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="retestApi">重新测试</el-button>
        </template>
      </el-dialog>

      <!-- 导入接口对话框 -->
      <import-api-dialog
        v-model="importDialogVisible"
        :project-id="projectId"
        @parsed="handleCurlParsed"
      />

      <!-- 批量导入对话框 -->
      <BatchImportDialog
        v-model="batchImportVisible"
        :project-id="projectId"
        @success="loadTree"
      />

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
          :rules="{ name: [{ required: true, message: '请输入目录名称', trigger: 'blur' }] }"
          label-width="80px"
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
          <el-button type="primary" @click="submitFolderForm" :loading="submitting">
            确定
          </el-button>
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

      <!-- 创建/编辑接口对话框已移除，新建接口直接在右侧详情面板编辑 -->

      <!-- 新建接口保存时选择目录对话框 -->
      <el-dialog
        v-model="saveFolderDialogVisible"
        title="选择保存目录"
        width="500px"
      >
        <el-form label-width="80px">
          <el-form-item label="目录">
            <el-tree-select
              v-model="selectedSaveFolderId"
              :data="folderTreeOptions"
              :props="{ label: 'label', children: 'children', value: 'value' }"
              placeholder="选择目录（不选则保存到根目录）"
              clearable
              check-strictly
              :render-after-expand="false"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="saveFolderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmSaveFolder" :loading="savingApi">
            确认
          </el-button>
        </template>
      </el-dialog>
      <!-- 环境变量管理面板（旧组件保留兼容） -->
      <env-variable-panel
        v-model:visible="envPanelVisible"
        :project-id="projectId"
      />
      <!-- 环境管理弹窗（新组件） -->
      <environment-manager
        v-model:visible="envManagerVisible"
        :project-id="projectId"
        :current-env-id="currentEnvId"
        @env-changed="loadEnvironmentList"
      />
    </div>
  </main-layout>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
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
  DocumentCopy,
  Search,
  Plus,
  MoreFilled,
  Refresh,
  Upload,
  Download,
  Edit,
  Delete,
  MagicStick,
  Warning,
  Rank
} from '@element-plus/icons-vue'
import { getFolderTree, createFolder, updateFolder, deleteFolder, initProjectFolders } from '../api/folder'
import { getApis, createApi, updateApi, deleteApi as deleteApiRequest, getApiCategories, testApi as testApiRequest } from '../api/api'
import MainLayout from '../components/MainLayout.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import ImportApiDialog from '../components/ImportApiDialog.vue'
import BatchImportDialog from '../components/BatchImportDialog.vue'
import ApiTabs from '../components/ApiTabs.vue'
import ApiDetailPanel from '../components/ApiDetailPanel.vue'
import EnvVariablePanel from '../components/EnvVariablePanel.vue'
import EnvironmentManager from '../components/EnvironmentManager.vue'
import { getEnvironments, getPrefixUrls } from '../api/envVariable'

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
  isLeaf: (data) => data.type === 'api' || data.type === 'case'  // 接口和用例是叶子节点
}

const apis = ref([])
const categories = ref([])
const searchKeyword = ref('')
const filterCategory = ref('')
const filterStatus = ref(null)
const currentFolder = ref(null)
const folderDialogVisible = ref(false)
const folderDialogTitle = ref('新建目录')
const submitting = ref(false)
const folderFormRef = ref(null)
const detailPanelRef = ref(null)

const folderForm = ref({
  id: null,
  name: '',
  description: '',
  parent_id: null
})

// 移动目录相关状态
const moveFolderDialogVisible = ref(false)
const movingFolder = ref(null)
const moveTargetParentId = ref(null)
const moveFolderOptions = ref([])

// 测试结果相关状态
const testResultDialogVisible = ref(false)
const testResult = ref(null)
const testingApi = ref(false)
const savingApi = ref(false)

// ===== Tab 管理 =====
const openTabs = ref([])
const activeTabId = ref('')
let tabIdCounter = 0

const activeTab = computed(() => openTabs.value.find(t => t.id === activeTabId.value) || null)

// 创建空的 editableApi 数据
const createEmptyApi = () => ({
  name: '',
  method: 'GET',
  base_url: '',
  path: '',
  description: '',
  headers: {},
  params: {},
  body: {},
  body_type: 'json',
  prefix_url_id: null,
  status: 1
})

// 创建空的 responseData
const createEmptyResponse = () => ({
  statusCode: 200,
  body: null,
  headers: null,
  info: null,
  duration: null,
  size: null,
  timestamp: null,
  requestInfo: null
})

// 从 response_example 还原 responseData（仅还原响应 body）
const buildResponseFromExample = (example) => {
  if (!example || Object.keys(example).length === 0) return createEmptyResponse()
  return {
    ...createEmptyResponse(),
    body: example
  }
}

// 深比较两个对象是否相等（用于判断接口是否被修改）
const isDeepEqual = (a, b) => JSON.stringify(a) === JSON.stringify(b)

// 检查 tab 是否被修改
const checkTabModified = (tab) => {
  if (tab.isNew) return true
  if (!tab._snapshot) return false
  if (tab.folderId !== tab._snapshotFolderId) return true
  return !isDeepEqual(tab.editableApi, tab._snapshot)
}

// 打开一个已有接口的 tab
const openApiTab = (apiData) => {
  // 已有 tab 则切过去
  const existing = openTabs.value.find(t => !t.isNew && t.rawId === apiData.raw_id)
  if (existing) {
    activeTabId.value = existing.id
    return
  }
  const id = `tab_${++tabIdCounter}`
  const snapshot = {
    name: apiData.name || '',
    method: apiData.method || 'GET',
    base_url: apiData.base_url || '',
    path: apiData.path || '',
    description: apiData.description || '',
    headers: JSON.parse(JSON.stringify(apiData.headers || {})),
    params: JSON.parse(JSON.stringify(apiData.params || {})),
    body: JSON.parse(JSON.stringify(apiData.body || {})),
    body_type: apiData.body_type || 'json',
    prefix_url_id: apiData.prefix_url_id || null,
    status: apiData.status !== undefined ? apiData.status : 1
  }
  openTabs.value.push({
    id,
    rawId: apiData.raw_id,
    folderId: apiData.folder_id,
    name: apiData.name || '未命名接口',
    method: apiData.method || 'GET',
    isNew: false,
    modified: false,
    editableApi: JSON.parse(JSON.stringify(snapshot)),
    _snapshot: snapshot,
    _snapshotFolderId: apiData.folder_id,
    responseData: buildResponseFromExample(apiData.response_example),
    apiData // 保留原始数据引用
  })
  activeTabId.value = id
}

// 打开一个新建接口的 tab
const openNewTab = (folderId = null, editableOverride = null) => {
  const id = `tab_${++tabIdCounter}`
  openTabs.value.push({
    id,
    rawId: null,
    folderId,
    name: editableOverride?.name || '新建接口',
    method: editableOverride?.method || 'GET',
    isNew: true,
    modified: true,
    editableApi: editableOverride || createEmptyApi(),
    _snapshot: null,
    _snapshotFolderId: null,
    responseData: createEmptyResponse(),
    apiData: null
  })
  activeTabId.value = id
}

const switchTab = (tabId) => {
  activeTabId.value = tabId
  // 同步中间栏树选中状态
  const tab = openTabs.value.find(t => t.id === tabId)
  if (tab && tab.rawId && treeRef.value) {
    const node = findNodeById(treeData.value, tab.rawId)
    if (node) {
      treeRef.value.setCurrentKey(node.raw_id)
    }
  }
}

// 自动检测 editableApi 变化，更新 modified 标记
watch(
  () => openTabs.value.map(t => ({ editableApi: t.editableApi, folderId: t.folderId })),
  () => {
    for (const tab of openTabs.value) {
      tab.modified = checkTabModified(tab)
    }
  },
  { deep: true }
)

const closeTab = (tabId) => {
  const idx = openTabs.value.findIndex(t => t.id === tabId)
  if (idx === -1) return
  openTabs.value.splice(idx, 1)
  if (activeTabId.value === tabId) {
    // 激活相邻 tab
    if (openTabs.value.length > 0) {
      activeTabId.value = openTabs.value[Math.min(idx, openTabs.value.length - 1)].id
    } else {
      activeTabId.value = ''
    }
  }
}

const closeOtherTabs = (tabId) => {
  openTabs.value = openTabs.value.filter(t => t.id === tabId)
  activeTabId.value = tabId
}

const closeLeftTabs = (index) => {
  openTabs.value = openTabs.value.slice(index)
  if (!openTabs.value.find(t => t.id === activeTabId.value)) {
    activeTabId.value = openTabs.value[0]?.id || ''
  }
}

const closeRightTabs = (index) => {
  openTabs.value = openTabs.value.slice(0, index + 1)
  if (!openTabs.value.find(t => t.id === activeTabId.value)) {
    activeTabId.value = openTabs.value[openTabs.value.length - 1]?.id || ''
  }
}

const closeAllTabs = () => {
  openTabs.value = []
  activeTabId.value = ''
}

// 导入对话框
const importDialogVisible = ref(false)
const batchImportVisible = ref(false)

// 环境变量面板
const envPanelVisible = ref(false)

// 环境管理弹窗
const envManagerVisible = ref(false)
const environmentList = ref([])
const currentEnvId = ref(null)

async function loadEnvironmentList() {
  try {
    const res = await getEnvironments(projectId.value)
    environmentList.value = res.data || []
  } catch (e) {
    console.error('加载环境列表失败:', e)
  }
}

function handleSwitchEnv(envId) {
  currentEnvId.value = envId
  loadCurrentEnvPrefixUrls()
}

// 当前环境的前置 URL 列表（用于在接口详情页回显）
const currentEnvPrefixUrls = ref([])

async function loadCurrentEnvPrefixUrls() {
  if (!currentEnvId.value) {
    currentEnvPrefixUrls.value = []
    return
  }
  try {
    const res = await getPrefixUrls(projectId.value, currentEnvId.value)
    currentEnvPrefixUrls.value = res.data || []
  } catch (e) {
    currentEnvPrefixUrls.value = []
  }
}

// 页面关闭/刷新时，如果有未保存修改的页签则提醒
const handleBeforeUnload = (e) => {
  if (openTabs.value.some(t => t.modified)) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  loadTree()
  loadCategories()
  loadEnvironmentList()
  
  // 添加 Ctrl+S 快捷键保存
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('beforeunload', handleBeforeUnload)
})

// 快捷键处理
const handleKeyDown = (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault()
    if (activeTab.value) {
      saveApiChanges()
    }
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault()
    if (activeTab.value && !activeTab.value.isNew) {
      sendRequest()
    }
  }
}

// 组件卸载时清理事件监听
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// 加载目录树
const loadTree = async () => {
  loading.value = true
  try {
    const res = await getFolderTree(projectId.value)
    console.log('目录树数据:', res)
    treeData.value = res.data || []
    console.log('treeData:', treeData.value)
  } catch (error) {
    console.error('加载目录树失败:', error)
    ElMessage.error('加载目录树失败')
  } finally {
    loading.value = false
  }
}

// 加载接口列表
const loadApis = async () => {
  loading.value = true
  try {
    const params = {}
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterCategory.value) params.category = filterCategory.value
    if (filterStatus.value !== null) params.status = filterStatus.value
    
    const res = await getApis(projectId.value, params)
    apis.value = res.data || []
  } catch (error) {
    console.error('加载接口失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载分类列表
const loadCategories = async () => {
  try {
    const res = await getApiCategories(projectId.value)
    categories.value = res.data || []
  } catch (error) {
    console.error('加载分类失败:', error)
  }
}

// 搜索
const handleSearch = () => {
  loadApis()
}

// HTTP方法类型
const getMethodType = (method) => {
  const typeMap = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'info'
  }
  return typeMap[method] || 'info'
}

// 树节点点击
const handleNodeClick = (data) => {
  if (data.type === 'api') {
    openApiTab(data)
    currentFolder.value = null
  } else if (data.type === 'folder') {
    currentFolder.value = data
  }
}

// 获取节点统计信息
const getNodeStats = (node) => {
  if (!node.children || node.children.length === 0) return '0'
  
  let folderCount = 0
  let apiCount = 0
  let caseCount = 0
  
  const countChildren = (children) => {
    for (const child of children) {
      if (child.type === 'folder') {
        folderCount++
        if (child.children) {
          countChildren(child.children)
        }
      } else if (child.type === 'api') {
        apiCount++
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
  if (apiCount > 0) parts.push(`${apiCount}接口`)
  if (caseCount > 0) parts.push(`${caseCount}用例`)
  
  return parts.join(', ') || '0'
}

// 接口操作
const handleApiAction = (command, api) => {
  switch (command) {
    case 'copy':
      copyApi(api)
      break
    case 'delete':
      deleteApiConfirm(api)
      break
  }
}

// 复制接口：复制所有字段并打开新 tab
const copyApi = (api) => {
  const copiedApi = {
    name: (api.name || '') + ' copy',
    method: api.method || 'GET',
    base_url: api.base_url || '',
    path: api.path || '',
    description: api.description || '',
    headers: JSON.parse(JSON.stringify(api.headers || {})),
    params: JSON.parse(JSON.stringify(api.params || {})),
    body: JSON.parse(JSON.stringify(api.body || {})),
    body_type: api.body_type || 'json',
    status: api.status !== undefined ? api.status : 1
  }
  openNewTab(api.folder_id || null, copiedApi)
}

// 删除接口确认
const deleteApiConfirm = (api) => {
  ElMessageBox.confirm(
    `确定要删除接口"${api.name}"吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteApiRequest(projectId.value, api.raw_id)
      ElMessage.success('删除成功')
      // 关闭对应的 tab
      const tab = openTabs.value.find(t => t.rawId === api.raw_id)
      if (tab) closeTab(tab.id)
      loadTree()
    } catch (error) {
      console.error('删除失败:', error)
    }
  }).catch(() => {})
}

// 树节点右键菜单
const handleNodeContextMenu = (event, data) => {
  event.preventDefault()
  // 可以在这里实现右键菜单
}

// 添加操作
const handleAddAction = (command) => {
  if (command === 'folder') {
    showCreateFolderDialog()
  } else if (command === 'api') {
    showCreateDialog()
  } else if (command === 'importCurl') {
    importDialogVisible.value = true
  } else if (command === 'batchImport') {
    batchImportVisible.value = true
  }
}

// cURL解析成功后，在右侧面板打开编辑（不立即调用后端）
const handleCurlParsed = (parsed) => {
  const editableOverride = {
    name: parsed.name || '',
    method: parsed.method || 'GET',
    base_url: parsed.base_url || '',
    path: parsed.path || '',
    description: '',
    headers: parsed.headers || {},
    params: parsed.params || {},
    body: parsed.body || {},
    body_type: parsed.body_type || 'json',
    status: 1
  }
  openNewTab(null, editableOverride)
  ElMessage.success('cURL已解析，请编辑后点击保存')
}

// 目录操作
const handleFolderAction = (command, folder) => {
  switch (command) {
    case 'addFolder':
      showCreateFolderDialog(folder.raw_id)
      break
    case 'addApi':
      showCreateDialog(folder.raw_id)
      break
    case 'rename':
      renameFolderDialog(folder)
      break
    case 'move':
      showMoveFolderDialog(folder)
      break
    case 'delete':
      deleteFolderConfirm(folder)
      break
  }
}

// 初始化目录
const initFolders = async () => {
  try {
    await ElMessageBox.confirm(
      '这将为项目创建默认目录结构，并智能分配现有接口到相应目录。确定继续吗？',
      '初始化目录',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    loading.value = true
    const res = await initProjectFolders(projectId.value)
    ElMessage.success(res.message || '初始化成功')
    loadTree()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('初始化失败:', error)
    }
  } finally {
    loading.value = false
  }
}

// 显示创建目录对话框
const showCreateFolderDialog = (parentId = null) => {
  folderDialogTitle.value = parentId ? '新建子目录' : '新建目录'
  folderForm.value = {
    id: null,
    name: '',
    description: '',
    parent_id: parentId
  }
  folderDialogVisible.value = true
  nextTick(() => {
    folderFormRef.value?.clearValidate()
  })
}

// 重命名目录
const renameFolderDialog = (folder) => {
  folderDialogTitle.value = '重命名目录'
  folderForm.value = {
    id: folder.raw_id,
    name: folder.name,
    description: folder.description,
    parent_id: folder.parent_id
  }
  folderDialogVisible.value = true
}

// 移动目录
const showMoveFolderDialog = (folder) => {
  movingFolder.value = folder
  moveTargetParentId.value = folder.parent_id || null
  // 构建可选目录列表，排除自身及其子目录
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
  } catch (error) {
    console.error('移动失败:', error)
    ElMessage.error('移动失败')
  } finally {
    submitting.value = false
  }
}

// 提交目录表单
const submitFolderForm = async () => {
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
    } catch (error) {
      console.error('操作失败:', error)
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
      await deleteFolder(projectId.value, folder.raw_id)
      ElMessage.success('删除成功')
      loadTree()
    } catch (error) {
      console.error('删除失败:', error)
    }
  }).catch(() => {})
}

// 选择接口
const selectApi = (api) => {
  openApiTab(api)
}

// 标记当前是否为新建模式（未保存到后端的新接口）
const isNewApi = computed(() => activeTab.value?.isNew || false)

// 新建接口：打开新 tab
const showCreateDialog = (folderId = null) => {
  openNewTab(folderId)
}

// 提交表单（已移除弹窗，新建和编辑都在右侧面板通过 saveApiChanges 完成）

// 删除当前接口
const deleteCurrentApi = () => {
  if (!activeTab.value || activeTab.value.isNew) return
  
  ElMessageBox.confirm(
    `确定要删除接口"${activeTab.value.editableApi.name}"吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteApiRequest(projectId.value, activeTab.value.rawId)
      ElMessage.success('删除成功')
      closeTab(activeTab.value.id)
      loadTree()
      loadCategories()
    } catch (error) {
      console.error('删除失败:', error)
    }
  }).catch(() => {})
}

// 测试接口
const testApi = async () => {
  if (!activeTab.value || activeTab.value.isNew) {
    ElMessage.warning('请先保存接口')
    return
  }
  
  testingApi.value = true
  const tab = activeTab.value
  try {
    const res = await testApiRequest(projectId.value, tab.rawId, {
      method: tab.editableApi.method,
      base_url: tab.editableApi.base_url,
      path: tab.editableApi.path,
      headers: tab.editableApi.headers,
      params: tab.editableApi.params,
      body: tab.editableApi.body,
      body_type: tab.editableApi.body_type,
      prefix_url_id: tab.editableApi.prefix_url_id || undefined,
      environment_id: currentEnvId.value || undefined
    })
    
    testResult.value = res.data
    testResultDialogVisible.value = true
  } catch (error) {
    console.error('测试失败:', error)
    ElMessage.error('测试失败: ' + (error.message || '未知错误'))
  } finally {
    testingApi.value = false
  }
}

// 新增：发送请求（使用可编辑的数据）
const sendRequest = async () => {
  if (!activeTab.value) {
    ElMessage.warning('请先选择一个接口')
    return
  }
  
  if (activeTab.value.isNew) {
    ElMessage.warning('请先保存接口后再发送请求')
    return
  }
  
  testingApi.value = true
  const startTime = Date.now()
  const tab = activeTab.value
  
  try {
    const res = await testApiRequest(projectId.value, tab.rawId, {
      method: tab.editableApi.method,
      base_url: tab.editableApi.base_url || '',
      path: tab.editableApi.path || '',
      headers: tab.editableApi.headers,
      params: tab.editableApi.params,
      body: tab.editableApi.body,
      body_type: tab.editableApi.body_type,
      prefix_url_id: tab.editableApi.prefix_url_id || undefined,
      environment_id: currentEnvId.value || undefined
    })
    
    const duration = ((Date.now() - startTime) / 1000).toFixed(2) + 's'
    
    if (res.data && res.data.response) {
      tab.responseData = {
        statusCode: res.data.response.status_code || 200,
        body: res.data.response.body,
        bodyRaw: res.data.response.body_raw || null,
        headers: res.data.response.headers,
        info: res.data,
        duration,
        size: res.data.response.size,
        timestamp: new Date().toLocaleString(),
        requestInfo: res.data.request || {
          method: tab.editableApi.method,
          url: (tab.editableApi.base_url || '') + (tab.editableApi.path || ''),
          headers: tab.editableApi.headers || {},
          params: tab.editableApi.params || {},
          body: tab.editableApi.body || {}
        }
      }
      ElMessage.success('发送成功')
    } else if (res.data && res.data.error) {
      // 请求发出但连接失败等错误
      tab.responseData = {
        statusCode: 0,
        body: res.data.error.message || '请求失败',
        headers: null,
        info: res.data,
        duration: (res.data.duration || 0) + 's',
        size: 0,
        timestamp: new Date().toLocaleString(),
        requestInfo: res.data.request || null,
        error: res.data.error
      }
      ElMessage.error(res.data.error.type + ': ' + res.data.error.message)
    } else {
      throw new Error('响应数据格式错误')
    }
  } catch (error) {
    console.error('请求失败:', error)
    tab.responseData = {
      statusCode: error.response?.status || 500,
      body: error.message || '请求失败',
      headers: null,
      info: null,
      duration: ((Date.now() - startTime) / 1000).toFixed(2) + 's',
      size: null,
      timestamp: new Date().toLocaleString(),
      requestInfo: {
        method: tab.editableApi.method,
        url: (tab.editableApi.base_url || '') + (tab.editableApi.path || ''),
        headers: tab.editableApi.headers || {},
        params: tab.editableApi.params || {},
        body: tab.editableApi.body || {}
      }
    }
    ElMessage.error('请求失败: ' + (error.message || '未知错误'))
  } finally {
    testingApi.value = false
  }
}

// 新增：选择目录对话框（用于新建接口保存时选择目录）
const saveFolderDialogVisible = ref(false)
const selectedSaveFolderId = ref(null)

// 获取树形目录列表（用于 el-tree-select 层级展示）
const folderTreeOptions = computed(() => {
  const buildOptions = (nodes) => {
    const result = []
    for (const node of nodes) {
      if (node.type === 'folder') {
        const option = {
          value: node.raw_id,
          label: node.name,
          children: node.children ? buildOptions(node.children) : []
        }
        result.push(option)
      }
    }
    return result
  }
  return buildOptions(treeData.value)
})

// 新增：保存接口修改
const saveApiChanges = async () => {
  if (!activeTab.value) {
    ElMessage.warning('请先选择一个接口')
    return
  }
  
  const tab = activeTab.value
  if (!tab.editableApi.name || !tab.editableApi.name.trim()) {
    ElMessage.warning('请输入接口名称')
    return
  }
  
  if (tab.isNew) {
    if (tab.folderId) {
      selectedSaveFolderId.value = tab.folderId
      await doCreateApi()
    } else {
      selectedSaveFolderId.value = null
      saveFolderDialogVisible.value = true
    }
  } else {
    await doUpdateApi()
  }
}

// 确认选择目录后创建接口
const confirmSaveFolder = async () => {
  await doCreateApi()
  saveFolderDialogVisible.value = false
}

// 执行创建接口
const doCreateApi = async () => {
  savingApi.value = true
  const tab = activeTab.value
  try {
    const newApiData = {
      name: tab.editableApi.name,
      description: tab.editableApi.description,
      method: tab.editableApi.method,
      path: tab.editableApi.path || '',
      base_url: tab.editableApi.base_url || '',
      headers: tab.editableApi.headers,
      params: tab.editableApi.params,
      body: tab.editableApi.body,
      body_type: tab.editableApi.body_type,
      response_example: tab.responseData?.body || {},
      prefix_url_id: tab.editableApi.prefix_url_id || null,
      status: tab.editableApi.status,
      category: '',
      folder_id: selectedSaveFolderId.value
    }
    
    const res = await createApi(projectId.value, newApiData)
    ElMessage.success('保存成功')
    
    // 更新 tab 状态：从新建变为已有
    tab.isNew = false
    tab.rawId = res.data?.id
    tab.name = tab.editableApi.name
    tab.method = tab.editableApi.method
    
    await loadTree()
    
    // 更新 tab 的 apiData 引用
    if (tab.rawId) {
      const newNode = findNodeById(treeData.value, tab.rawId)
      if (newNode) {
        tab.apiData = newNode
        tab.folderId = newNode.folder_id
      }
    }
    
    // 等 DOM 更新完成后再拍快照
    await nextTick()
    tab._snapshot = JSON.parse(JSON.stringify(tab.editableApi))
    tab._snapshotFolderId = tab.folderId
    tab.modified = false
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    savingApi.value = false
  }
}

// 执行更新接口
const doUpdateApi = async () => {
  savingApi.value = true
  const tab = activeTab.value
  try {
    const updateData = {
      name: tab.editableApi.name,
      description: tab.editableApi.description,
      method: tab.editableApi.method,
      path: tab.editableApi.path || '',
      base_url: tab.editableApi.base_url || '',
      headers: tab.editableApi.headers,
      params: tab.editableApi.params,
      body: tab.editableApi.body,
      body_type: tab.editableApi.body_type,
      response_example: tab.responseData?.body || {},
      prefix_url_id: tab.editableApi.prefix_url_id || null,
      status: tab.editableApi.status,
      category: tab.apiData?.category || '',
      folder_id: tab.folderId
    }
    
    await updateApi(projectId.value, tab.rawId, updateData)
    ElMessage.success('保存成功')
    
    // 更新 tab 显示信息
    tab.name = tab.editableApi.name
    tab.method = tab.editableApi.method
    
    // 重置编辑器
    if (detailPanelRef.value) {
      detailPanelRef.value.resetEditors()
    }
    
    await loadTree()
    
    // 更新 apiData 引用
    if (tab.rawId) {
      const updatedNode = findNodeById(treeData.value, tab.rawId)
      if (updatedNode) {
        tab.apiData = updatedNode
      }
    }
    
    // 等 DOM 更新完成后再拍快照，避免 resetEditors 触发的数据变化导致 modified 误判
    await nextTick()
    tab._snapshot = JSON.parse(JSON.stringify(tab.editableApi))
    tab._snapshotFolderId = tab.folderId
    tab.modified = false
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    savingApi.value = false
  }
}

// 辅助函数：在树中查找节点
const findNodeById = (nodes, id) => {
  for (const node of nodes) {
    if (node.type === 'api' && node.raw_id === id) {
      return node
    }
    if (node.children) {
      const found = findNodeById(node.children, id)
      if (found) return found
    }
  }
  return null
}

// 重新测试
const retestApi = async () => {
  testResultDialogVisible.value = false
  await testApi()
}

// 获取状态码类型
const getStatusCodeType = (statusCode) => {
  if (statusCode >= 200 && statusCode < 300) {
    return 'success'
  } else if (statusCode >= 300 && statusCode < 400) {
    return 'info'
  } else if (statusCode >= 400 && statusCode < 500) {
    return 'warning'
  } else if (statusCode >= 500) {
    return 'danger'
  }
  return 'info'
}

// 格式化文件大小
const formatSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 格式化响应体
const formatResponseBody = (body) => {
  if (typeof body === 'string') {
    try {
      return JSON.stringify(JSON.parse(body), null, 2)
    } catch {
      return body
    }
  } else if (typeof body === 'object') {
    return JSON.stringify(body, null, 2)
  }
  return String(body)
}
</script>

<style scoped>
.project-detail-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--el-bg-color-page);
}

/* 中间栏 */
.middle-panel {
  width: 350px;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  gap: 8px;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.header-actions .add-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  font-weight: bold;
  font-size: 18px;
}

.filter-bar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  gap: 8px;
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-right: 8px;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  overflow: hidden;
}

.node-icon {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
}

.folder-icon {
  color: var(--el-color-primary);
}

.case-icon {
  color: var(--el-color-success);
}

.method-tag {
  flex-shrink: 0;
}

.node-label {
  font-size: 14px;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.node-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 8px;
  flex-shrink: 0;
}

.node-actions {
  opacity: 0;
  transition: opacity 0.3s;
}

.tree-node:hover .node-actions {
  opacity: 1;
}

.action-icon {
  cursor: pointer;
  color: var(--el-text-color-secondary);
  font-size: 16px;
}

.action-icon:hover {
  color: var(--el-color-primary);
}

:deep(.el-tree-node__content) {
  height: 36px;
  padding: 0 8px;
}

:deep(.el-tree-node__content:hover) {
  background-color: var(--el-fill-color-light);
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: #ecf5ff;
  color: var(--el-color-primary);
}

/* 树形缩进引导线：indent=0 后由 padding-left 控制缩进 */
:deep(.el-tree-node__children) {
  position: relative;
  padding-left: 18px;
}

:deep(.el-tree-node__children:not(:empty)::before) {
  content: '';
  position: absolute;
  left: 9px;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--el-border-color-light);
  pointer-events: none;
}

.api-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.api-item {
  padding: 12px;
  margin-bottom: 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid transparent;
}

.api-item:hover {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.api-item.active {
  background: #ecf5ff;
  border-color: var(--el-color-primary);
}

.api-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.method-tag {
  flex-shrink: 0;
}

.api-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-path {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.category {
  color: var(--el-text-color-regular);
  background: var(--el-border-color-light);
  padding: 2px 8px;
  border-radius: 3px;
}

/* 右侧栏 */
.right-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
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

/* 新的接口详情布局 - 已移至 ApiDetailPanel.vue */

.api-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-title h3 {
  margin: 0;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.detail-content {
  flex: 1;
  padding: 20px;
}

.detail-section {
  margin-bottom: 24px;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid var(--el-color-primary);
}

.body-type-info {
  margin-bottom: 10px;
}

/* 测试结果样式 */
.test-result {
  max-height: 70vh;
  overflow-y: auto;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.duration {
  font-size: 14px;
  color: var(--el-text-color-regular);
  font-weight: 500;
}

.timestamp {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
}

.json-view {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
  max-height: 400px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 创建对话框 URL 行样式 */
.url-form-item :deep(.el-form-item__content) {
  flex-wrap: nowrap;
}

.url-line {
  display: flex;
  gap: 6px;
  width: 100%;
  align-items: center;
}

.method-select-mini {
  width: 110px;
  flex-shrink: 0;
}

.base-url-mini {
  width: 180px;
  flex-shrink: 0;
}

.path-mini {
  flex: 1;
}

/* 响应式 */
@media (max-width: 1200px) {
  .middle-panel {
    width: 300px;
  }
}

</style>
