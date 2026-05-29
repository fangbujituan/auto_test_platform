<template>
  <main-layout>
    <div class="dashboard-container">
    <!-- 头部欢迎区 -->
    <!-- <el-card class="welcome-card" shadow="never">
      <div class="welcome-content">
        <div class="welcome-text">
          <h2>欢迎回来，{{ username }}！</h2>
          <p>{{ currentTime }}</p>
        </div>
        <div class="welcome-actions">
          <el-button type="primary" @click="goToProjects">
            <el-icon><FolderOpened /></el-icon>
            项目管理
          </el-button>
          <el-button type="success" @click="goToCases">
            <el-icon><Document /></el-icon>
            用例管理
          </el-button>
          <el-button @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-button>
        </div>
      </div>
    </el-card> -->

    <!-- 统计卡片区 -->
    <div class="stats-row">
      <div class="stat-col" v-for="item in statCards" :key="item.key">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" :class="item.iconClass">
              <el-icon :size="36"><component :is="item.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats[item.key] }}</div>
              <div class="stat-label">{{ item.label }}</div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 图表和列表区 -->
    <el-row :gutter="20" class="content-row">
      <!-- 最近执行记录 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>最近执行记录</span>
              <el-button text @click="goToResults">查看更多</el-button>
            </div>
          </template>
          <el-table
            :data="recentResults"
            style="width: 100%"
            v-loading="loading"
          >
            <el-table-column prop="case_name" label="用例名称" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="getStatusType(row.status)"
                  size="small"
                >
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="duration" label="耗时" width="100">
              <template #default="{ row }">
                {{ row.duration ? row.duration.toFixed(2) + 's' : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="执行时间" width="160" />
          </el-table>
          <el-empty v-if="!loading && recentResults.length === 0" description="暂无执行记录" />
        </el-card>
      </el-col>

      <!-- 项目列表 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>项目列表</span>
              <el-button text @click="goToProjects">查看更多</el-button>
            </div>
          </template>
          <el-table
            :data="projects"
            style="width: 100%"
            v-loading="loading"
          >
            <el-table-column prop="name" label="项目名称" show-overflow-tooltip />
            <el-table-column prop="case_count" label="用例数" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small">{{ row.case_count || 0 }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 1 ? 'success' : 'info'"
                  size="small"
                >
                  {{ row.status === 1 ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="viewProject(row)">
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && projects.length === 0" description="暂无项目" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作区 -->
    <el-card shadow="never" class="quick-actions">
      <template #header>
        <span>快捷操作</span>
      </template>
      <div class="action-buttons">
        <el-button type="primary" plain @click="createProject">
          <el-icon><Plus /></el-icon>
          新建项目
        </el-button>
        <el-button type="success" plain @click="createCase">
          <el-icon><Plus /></el-icon>
          新建用例
        </el-button>
        <el-button type="warning" plain @click="executeAll">
          <el-icon><VideoPlay /></el-icon>
          批量执行
        </el-button>
        <el-button plain @click="exportData">
          <el-icon><Download /></el-icon>
          导出数据
        </el-button>
      </div>
    </el-card>
  </div>
  </main-layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Folder,
  FolderOpened,
  Document,
  VideoPlay,
  SwitchButton,
  Plus,
  Download,
  Connection,
  Warning
} from '@element-plus/icons-vue'
import { logout } from '../api/auth'
import { getDashboardStats } from '../api/dashboard'
import MainLayout from '../components/MainLayout.vue'

const router = useRouter()
const username = ref('')
const currentTime = ref('')
const loading = ref(false)

// 统计数据
const stats = ref({
  projectCount: 0,
  folderCount: 0,
  apiCount: 0,
  testCaseCount: 0,
  bugCount: 0
})

// 统计卡片配置
const statCards = [
  { key: 'projectCount', label: '项目总数', icon: Folder, iconClass: 'project-icon' },
  { key: 'folderCount', label: '目录总数', icon: FolderOpened, iconClass: 'folder-icon' },
  { key: 'apiCount', label: '接口总数', icon: Connection, iconClass: 'api-icon' },
  { key: 'testCaseCount', label: '用例总数', icon: Document, iconClass: 'case-icon' },
  { key: 'bugCount', label: 'Bug总数', icon: Warning, iconClass: 'bug-icon' },
]

// 最近执行记录
const recentResults = ref([])

// 项目列表
const projects = ref([])

// 初始化
onMounted(() => {
  username.value = localStorage.getItem('username') || '用户'
  updateTime()
  setInterval(updateTime, 1000)
  loadDashboardData()
})

// 更新时间
const updateTime = () => {
  const now = new Date()
  const options = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }
  currentTime.value = now.toLocaleDateString('zh-CN', options)
}

// 加载仪表盘数据
const loadDashboardData = async () => {
  loading.value = true
  try {
    // 加载统计数据
    const statsRes = await getDashboardStats()
    if (statsRes.code === 0) {
      const d = statsRes.data
      stats.value = {
        projectCount: d.project_count || 0,
        folderCount: d.folder_count || 0,
        apiCount: d.api_count || 0,
        testCaseCount: d.test_case_count || 0,
        bugCount: d.bug_count || 0
      }
    }

    recentResults.value = [
      {
        id: 1,
        case_name: '用户登录接口测试',
        status: 'passed',
        duration: 0.52,
        created_at: '2026-01-14 15:30:25'
      },
      {
        id: 2,
        case_name: '获取用户信息接口',
        status: 'passed',
        duration: 0.38,
        created_at: '2026-01-14 15:28:10'
      },
      {
        id: 3,
        case_name: '创建订单接口测试',
        status: 'failed',
        duration: 1.25,
        created_at: '2026-01-14 15:25:45'
      },
      {
        id: 4,
        case_name: '支付接口测试',
        status: 'passed',
        duration: 0.89,
        created_at: '2026-01-14 15:20:30'
      }
    ]

    projects.value = [
      {
        id: 1,
        name: '用户中心',
        case_count: 12,
        status: 1
      },
      {
        id: 2,
        name: '订单系统',
        case_count: 8,
        status: 1
      },
      {
        id: 3,
        name: '支付系统',
        case_count: 5,
        status: 1
      },
      {
        id: 4,
        name: '商品管理',
        case_count: 3,
        status: 0
      }
    ]
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取状态类型
const getStatusType = (status) => {
  const typeMap = {
    passed: 'success',
    failed: 'danger',
    error: 'warning',
    skipped: 'info'
  }
  return typeMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const textMap = {
    passed: '通过',
    failed: '失败',
    error: '错误',
    skipped: '跳过'
  }
  return textMap[status] || status
}

// 退出登录
const handleLogout = async () => {
  try {
    await logout()
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    ElMessage.success('退出成功')
    router.push('/login')
  } catch (error) {
    console.error('退出失败:', error)
  }
}

// 页面跳转
const goToProjects = () => {
  router.push('/projects')
}

const goToCases = () => {
  ElMessage.info('用例管理功能开发中...')
}

const goToResults = () => {
  ElMessage.info('执行记录功能开发中...')
}

const viewProject = (project) => {
  router.push({
    name: 'ProjectDetail',
    params: { projectId: project.id },
    query: { projectName: project.name }
  })
}

// 快捷操作
const createProject = () => {
  router.push('/projects')
}

const createCase = () => {
  ElMessage.info('新建用例功能开发中...')
}

const executeAll = () => {
  ElMessage.info('批量执行功能开发中...')
}

const exportData = () => {
  ElMessage.info('导出数据功能开发中...')
}
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}

/* 欢迎卡片 */
.welcome-card {
  margin-bottom: 20px;
}

.welcome-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
}

.welcome-text h2 {
  margin: 0 0 10px 0;
  color: #303133;
  font-size: 24px;
}

.welcome-text p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.welcome-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.stat-col {
  flex: 1;
  min-width: 180px;
}

.stat-card {
  margin-bottom: 0;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.project-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.folder-icon {
  background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
}

.api-icon {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.case-icon {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.bug-icon {
  background: linear-gradient(135deg, #ff6a6a 0%, #ee0979 100%);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

/* 内容区 */
.content-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 快捷操作 */
.quick-actions {
  margin-bottom: 20px;
}

.action-buttons {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

/* 响应式 */
@media (max-width: 768px) {
  .welcome-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .welcome-actions {
    width: 100%;
  }

  .welcome-actions .el-button {
    flex: 1;
  }

  .stat-content {
    gap: 12px;
  }

  .stat-icon {
    width: 48px;
    height: 48px;
  }

  .stat-value {
    font-size: 22px;
  }
}
</style>
