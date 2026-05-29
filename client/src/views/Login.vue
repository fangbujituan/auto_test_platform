<template>
  <div class="login-container">
    <div class="login-card">
      <div class="card-header">
        <div class="logo-area">
          <span class="logo-letter" style="color: #4285F4">A</span>
          <span class="logo-letter" style="color: #EA4335">T</span>
          <span class="logo-letter" style="color: #FBBC05">P</span>
        </div>
        <p class="subtitle">登录你的账号</p>
      </div>

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="rules"
        label-position="top"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            size="large"
            class="login-btn"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="tips">
        <p>测试账号：admin / admin123</p>
        <p>测试账号：test / test123</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/auth'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    loading.value = true
    try {
      const res = await login(loginForm)
      localStorage.setItem('token', res.data.token)
      localStorage.setItem('username', res.data.username)
      ElMessage.success('登录成功')
      router.push('/dashboard')
    } catch (error) {
      console.error('登录失败:', error)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--el-bg-color-page);
}

.login-card {
  width: 420px;
  padding: 48px 40px 36px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
}

.card-header {
  text-align: center;
  margin-bottom: 24px;
}

.logo-area {
  margin-bottom: 8px;
}

.logo-letter {
  font-size: 38px;
  font-weight: 600;
  font-family: 'Google Sans', Arial, sans-serif;
  letter-spacing: 2px;
}

.subtitle {
  margin: 8px 0 0;
  font-size: 16px;
  color: var(--el-text-color-primary);
  font-weight: 400;
}

.login-btn {
  width: 100%;
  background-color: #1a73e8;
  border-color: #1a73e8;
  border-radius: 4px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.login-btn:hover,
.login-btn:focus {
  background-color: #1765cc;
  border-color: #1765cc;
}

:deep(.el-form-item__label) {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  font-weight: 500;
}

:deep(.el-input__wrapper) {
  border-radius: 4px;
  box-shadow: none !important;
  border: 1px solid var(--el-border-color);
  background-color: var(--el-bg-color) !important;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: none !important;
  border-color: var(--el-text-color-primary);
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: none !important;
  border-color: #1a73e8;
  border-width: 2px;
}

:deep(.el-input__inner) {
  background-color: transparent !important;
}

/* 覆盖浏览器自动填充的背景色 */
:deep(.el-input__inner:-webkit-autofill),
:deep(.el-input__inner:-webkit-autofill:hover),
:deep(.el-input__inner:-webkit-autofill:focus) {
  -webkit-box-shadow: 0 0 0 1000px var(--el-bg-color) inset !important;
  box-shadow: 0 0 0 1000px var(--el-bg-color) inset !important;
  -webkit-text-fill-color: var(--el-text-color-primary) !important;
}

.tips {
  margin-top: 24px;
  padding: 12px 16px;
  background-color: var(--el-fill-color-light);
  border-radius: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.tips p {
  margin: 4px 0;
}
</style>
