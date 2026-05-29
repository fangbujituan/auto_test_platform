<template>
  <MainLayout>
    <div class="settings-container">
      <div class="settings-sidebar">
        <el-menu
          :default-active="activePanel"
          class="settings-menu"
          @select="handleMenuSelect"
        >
          <el-menu-item index="profile">
            <el-icon><User /></el-icon>
            <span>个人资料</span>
          </el-menu-item>
          <el-menu-item index="password">
            <el-icon><Lock /></el-icon>
            <span>修改密码</span>
          </el-menu-item>
          <el-menu-item index="ai">
            <el-icon><MagicStick /></el-icon>
            <span>AI 配置</span>
          </el-menu-item>
          <el-menu-item index="appearance">
            <el-icon><Brush /></el-icon>
            <span>外观设置</span>
          </el-menu-item>
        </el-menu>
      </div>
      <div class="settings-content">
        <ProfilePanel v-if="activePanel === 'profile'" />
        <PasswordPanel v-else-if="activePanel === 'password'" />
        <AIConfigPanel v-else-if="activePanel === 'ai'" />
        <AppearancePanel v-else-if="activePanel === 'appearance'" />
      </div>
    </div>
  </MainLayout>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { User, Lock, MagicStick, Brush } from '@element-plus/icons-vue'
import MainLayout from '../components/MainLayout.vue'
import ProfilePanel from '../components/settings/ProfilePanel.vue'
import PasswordPanel from '../components/settings/PasswordPanel.vue'
import AIConfigPanel from '../components/settings/AIConfigPanel.vue'
import AppearancePanel from '../components/settings/AppearancePanel.vue'

const VALID_PANELS = ['profile', 'password', 'ai', 'appearance']

const route = useRoute()
const router = useRouter()

const activePanel = computed(() => {
  const tab = route.query.tab
  return VALID_PANELS.includes(tab) ? tab : 'profile'
})

const handleMenuSelect = (index) => {
  router.replace({ path: '/settings', query: { tab: index } })
}
</script>

<style scoped>
.settings-container {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.settings-sidebar {
  width: 200px;
  flex-shrink: 0;
  background-color: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
}

.settings-menu {
  height: 100%;
  border-right: none;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: var(--el-bg-color);
}
</style>
