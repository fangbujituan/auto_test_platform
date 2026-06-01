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

    <!-- 测试执行趋势图（V0.1）-->
    <el-card shadow="never" class="trend-card">
      <template #header>
        <div class="card-header">
          <span>测试执行趋势（最近 30 天）</span>
          <el-radio-group v-model="trendRange" size="small" @change="loadTrend">
            <el-radio-button :value="7">近 7 天</el-radio-button>
            <el-radio-button :value="30">近 30 天</el-radio-button>
            <el-radio-button :value="90">近 90 天</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div ref="trendChartRef" class="trend-chart" v-loading="trendLoading"></div>
      <el-empty
        v-if="!trendLoading && trendIsEmpty"
        description="该时间范围内暂无执行数据"
        :image-size="80"
      />
    </el-card>

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
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
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
import { getDashboardStats, getExecutionTrend } from '../api/dashboard'
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

// ===== 测试执行趋势图 =====
const trendChartRef = ref(null)
const trendLoading = ref(false)
const trendRange = ref(30)        // 默认近 30 天
const trendData = ref([])         // 来自 /api/dashboard/quality/execution/trend
let trendChart = null             // ECharts 实例

// 趋势数据是否为空（所有日期 total 都是 0）
const trendIsEmpty = computed(() =>
  trendData.value.length === 0 ||
  trendData.value.every(d => d.total === 0)
)

const buildTrendOption = () => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['通过率(%)', '失败率(%)', '执行总数'], top: 0 },
  grid: { left: 50, right: 60, top: 40, bottom: 30 },
  xAxis: {
    type: 'category',
    data: trendData.value.map(d => d.date.slice(5)),  // 只保留 MM-DD
    boundaryGap: false,
  },
  yAxis: [
    {
      type: 'value',
      name: '比率(%)',
      max: 100,
      min: 0,
      axisLabel: { formatter: '{value}%' },
    },
    {
      type: 'value',
      name: '执行数',
      min: 0,
      axisLabel: { formatter: '{value}' },
    },
  ],
  series: [
    {
      name: '通过率(%)',
      type: 'line',
      smooth: true,
      data: trendData.value.map(d => d.pass_rate),  // null 时折线断开
      itemStyle: { color: '#67c23a' },
      connectNulls: false,
    },
    {
      name: '失败率(%)',
      type: 'line',
      smooth: true,
      data: trendData.value.map(d => d.fail_rate),
      itemStyle: { color: '#f56c6c' },
      connectNulls: false,
    },
    {
      name: '执行总数',
      type: 'bar',
      yAxisIndex: 1,
      data: trendData.value.map(d => d.total),
      itemStyle: { color: 'rgba(64, 158, 255, 0.5)' },
      barWidth: '40%',
    },
  ],
})

// 拉取趋势数据 + 渲染
const loadTrend = async () => {
  trendLoading.value = true
  try {
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - trendRange.value + 1)
    const fmt = d => d.toISOString().slice(0, 10)

    const res = await getExecutionTrend({
      start_date: fmt(start),
      end_date: fmt(end),
    })
    if (res.code === 0 && res.data) {
      trendData.value = res.data.items || []
      await nextTick()
      if (!trendChart && trendChartRef.value) {
        trendChart = echarts.init(trendChartRef.value)
      }
      if (trendChart) {
        trendChart.setOption(buildTrendOption(), true)
        trendChart.resize()
      }
    } else {
      ElMessage.warning(res.message || '加载趋势数据失败')
    }
  } catch (e) {
    ElMessage.error('加载趋势数据失败：' + (e.message || '网络错误'))
  } finally {
    trendLoading.value = false
  }
}

// 窗口尺寸变化时重绘图表
const onWindowResize = () => {
  if (trendChart) trendChart.resize()
}

// 初始化
onMounted(() => {
  username.value = localStorage.getItem('username') || '用户'
  updateTime()
  setInterval(updateTime, 1000)
  loadDashboardData()
  loadTrend()
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
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

/* 趋势图卡片 */
.trend-card {
  margin-bottom: 20px;
}

.trend-chart {
  width: 100%;
  height: 320px;
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
