<template>
  <div class="password-panel">
    <h3>修改密码</h3>
    <el-form
      ref="formRef"
      :model="passwordForm"
      :rules="rules"
      label-width="120px"
      style="max-width: 500px"
    >
      <el-form-item label="当前密码" prop="currentPassword">
        <el-input
          v-model="passwordForm.currentPassword"
          type="password"
          placeholder="请输入当前密码"
          show-password
        />
      </el-form-item>

      <el-form-item label="新密码" prop="newPassword">
        <el-input
          v-model="passwordForm.newPassword"
          type="password"
          placeholder="请输入新密码（至少6位）"
          show-password
        />
      </el-form-item>

      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input
          v-model="passwordForm.confirmPassword"
          type="password"
          placeholder="请再次输入新密码"
          show-password
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="handleChangePassword">
          修改密码
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { changePassword } from '../../api/auth'
import { validatePasswordLength, validatePasswordMatch } from '../../utils/validators'

const formRef = ref(null)
const submitting = ref(false)

const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const validateNewPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入新密码'))
  } else if (!validatePasswordLength(value)) {
    callback(new Error('密码长度不能少于6位'))
  } else {
    if (passwordForm.confirmPassword) {
      formRef.value?.validateField('confirmPassword')
    }
    callback()
  }
}

const validateConfirmPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'))
  } else if (!validatePasswordMatch(passwordForm.newPassword, value)) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  currentPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { validator: validateNewPassword, trigger: 'blur' }
  ],
  confirmPassword: [
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleChangePassword = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await changePassword({
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword
    })
    ElMessage.success('密码修改成功')
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    formRef.value.resetFields()
  } catch (error) {
    if (error.response && error.response.status === 400) {
      ElMessage.error('当前密码错误')
    }
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.password-panel h3 {
  margin-top: 0;
  margin-bottom: 24px;
  font-size: 18px;
  color: var(--el-text-color-primary);
}
</style>
