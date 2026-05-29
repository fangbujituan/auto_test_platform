<template>
  <div class="init-container">
    <el-card class="init-card" shadow="always">
      <template #header>
        <h2>系统初始化</h2>
      </template>

      <el-steps :active="currentStep" finish-status="success" align-center>
        <el-step title="初始化用户" />
        <el-step title="初始化权限" />
        <el-step title="完成" />
      </el-steps>

      <div class="init-content">
        <!-- 步骤1：初始化用户 -->
        <div v-if="currentStep === 0" class="step-content">
          <el-alert
            title="初始化默认用户"
            type="info"
            description="将创建两个测试用户：admin/admin123 和 test/test123"
            :closable="false"
            show-icon
          />
          <div class="action-area">
            <el-button
              type="primary"
              size="large"
              @click="initUsers"
              :loading="loading"
            >
              初始化用户
            </el-button>
          </div>
        </div>

        <!-- 步骤2：初始化权限 -->
        <div v-if="currentStep === 1" class="step-content">
          <el-alert
            title="初始化角色和权限"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <p>将创建以下角色：</p>
              <ul>
                <li><strong>admin</strong> - 平台管理员，拥有所有权限</li>
                <li><strong>owner</strong> - 项目负责人，可以管理项目和成员</li>
                <li><strong>member</strong> - 项目成员，可以创建和编辑用例</li>
                <li><strong>viewer</strong> - 只读用户，只能查看</li>
              </ul>
            </template>
          </el-alert>
          <div class="action-area">
            <el-button @click="currentStep = 0">上一步</el-button>
            <el-button
              type="primary"
              size="large"
              @click="initRoles"
              :loading="loading"
            >
              初始化权限
            </el-button>
          </div>
        </div>

        <!-- 步骤3：完成 -->
        <div v-if="currentStep === 2" class="step-content">
          <el-result
            icon="success"
            title="初始化完成"
            sub-title="系统已成功初始化，可以开始使用了"
          >
            <template #extra>
              <el-button type="primary" size="large" @click="goToLogin">
                前往登录
              </el-button>
            </template>
          </el-result>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { initUsers as initUsersApi } from '../api/user'
import { initRoles as initRolesApi } from '../api/role'

const router = useRouter()
const currentStep = ref(0)
const loading = ref(false)

// 初始化用户
const initUsers = async () => {
  loading.value = true
  try {
    await initUsersApi()
    ElMessage.success('用户初始化成功')
    currentStep.value = 1
  } catch (error) {
    console.error('初始化用户失败:', error)
  } finally {
    loading.value = false
  }
}

// 初始化权限
const initRoles = async () => {
  loading.value = true
  try {
    await initRolesApi()
    ElMessage.success('权限初始化成功')
    currentStep.value = 2
  } catch (error) {
    console.error('初始化权限失败:', error)
  } finally {
    loading.value = false
  }
}

// 前往登录
const goToLogin = () => {
  router.push('/login')
}
</script>

<style scoped>
.init-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.init-card {
  width: 100%;
  max-width: 800px;
}

.init-card h2 {
  margin: 0;
  text-align: center;
  color: #303133;
}

.init-content {
  margin-top: 40px;
}

.step-content {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.action-area {
  margin-top: 40px;
  text-align: center;
}

.action-area .el-button {
  margin: 0 10px;
}

:deep(.el-alert) {
  margin-bottom: 20px;
}

:deep(.el-alert ul) {
  margin: 10px 0;
  padding-left: 20px;
}

:deep(.el-alert li) {
  margin: 5px 0;
}
</style>
