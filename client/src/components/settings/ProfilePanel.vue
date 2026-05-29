<template>
  <div class="profile-panel" v-loading="loading">
    <h3>个人资料</h3>
    <el-form
      ref="formRef"
      :model="userForm"
      label-width="100px"
      style="max-width: 500px"
    >
      <el-form-item label="用户名">
        <el-input v-model="userForm.username" disabled />
      </el-form-item>

      <el-form-item label="邮箱" :error="emailError">
        <el-input v-model="userForm.email" placeholder="请输入邮箱" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="handleSave">
          保存
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCurrentUser, updateProfile } from '../../api/auth'
import { validateEmail } from '../../utils/validators'

const userForm = ref({
  username: '',
  email: ''
})
const loading = ref(false)
const submitting = ref(false)
const emailError = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const res = await getCurrentUser()
    userForm.value.username = res.data.username || ''
    userForm.value.email = res.data.email || ''
  } catch (error) {
    console.error('获取用户信息失败:', error)
  } finally {
    loading.value = false
  }
})

const handleSave = async () => {
  emailError.value = ''

  if (!userForm.value.email) {
    emailError.value = '请输入邮箱'
    return
  }

  if (!validateEmail(userForm.value.email)) {
    emailError.value = '邮箱格式不正确'
    return
  }

  submitting.value = true
  try {
    await updateProfile({ email: userForm.value.email })
    ElMessage.success('资料更新成功')
  } catch (error) {
    // 后端错误已由 request.js 拦截器通过 ElMessage.error 显示
    console.error('更新资料失败:', error)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.profile-panel h3 {
  margin-top: 0;
  margin-bottom: 24px;
  font-size: 18px;
  color: var(--el-text-color-primary);
}
</style>
