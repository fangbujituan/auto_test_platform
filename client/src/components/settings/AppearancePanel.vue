<template>
  <div class="appearance-panel">
    <h3>外观设置</h3>
    <el-form
      :model="appearanceForm"
      label-width="140px"
      style="max-width: 500px"
    >
      <el-form-item label="主题模式">
        <el-radio-group v-model="appearanceForm.theme">
          <el-radio value="light">浅色模式</el-radio>
          <el-radio value="dark">深色模式</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="侧边栏默认折叠">
        <el-switch v-model="appearanceForm.sidebarCollapsed" />
      </el-form-item>

      <el-form-item label="每页默认显示条数">
        <el-select v-model="appearanceForm.pageSize">
          <el-option :value="10" label="10 条/页" />
          <el-option :value="20" label="20 条/页" />
          <el-option :value="50" label="50 条/页" />
        </el-select>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="handleSave">
          保存
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const STORAGE_KEY = 'atp_appearance_settings'

const defaultSettings = {
  theme: 'light',
  sidebarCollapsed: false,
  pageSize: 20
}

const appearanceForm = reactive({ ...defaultSettings })

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      if (parsed.theme === 'light' || parsed.theme === 'dark') {
        appearanceForm.theme = parsed.theme
      }
      if (typeof parsed.sidebarCollapsed === 'boolean') {
        appearanceForm.sidebarCollapsed = parsed.sidebarCollapsed
      }
      if ([10, 20, 50].includes(parsed.pageSize)) {
        appearanceForm.pageSize = parsed.pageSize
      }
    }
  } catch (e) {
    console.error('读取外观设置失败:', e)
  }
})

const applyTheme = (theme) => {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

const handleSave = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      theme: appearanceForm.theme,
      sidebarCollapsed: appearanceForm.sidebarCollapsed,
      pageSize: appearanceForm.pageSize
    }))
    applyTheme(appearanceForm.theme)
    ElMessage.success('外观设置已保存')
  } catch (e) {
    console.error('保存外观设置失败:', e)
    ElMessage.error('保存失败')
  }
}
</script>

<style scoped>
.appearance-panel h3 {
  margin-top: 0;
  margin-bottom: 24px;
  font-size: 18px;
  color: var(--el-text-color-primary);
}
</style>
