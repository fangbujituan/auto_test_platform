<template>
  <div class="api-tabs" v-if="tabs.length > 0">
    <button class="scroll-btn scroll-btn-left" v-show="canScrollLeft" @click="scrollLeft">
      <el-icon><ArrowLeft /></el-icon>
    </button>
    <div class="tabs-scroll" ref="scrollRef" @scroll="updateScrollState">
      <div
        v-for="(tab, index) in tabs"
        :key="tab.id"
        class="tab-item"
        :class="{ active: tab.id === activeTabId }"
        @click="$emit('select', tab.id)"
        @contextmenu.prevent="showContextMenu($event, tab, index)"
      >
        <el-tag
          v-if="!tab.isNew"
          :type="getMethodType(tab.method)"
          size="small"
          class="tab-method"
        >
          {{ tab.method }}
        </el-tag>
        <el-icon v-else class="tab-new-icon"><Plus /></el-icon>
        <span class="tab-title" :title="tab.name">{{ tab.name }}</span>
        <span v-if="tab.modified" class="tab-dot"></span>
        <el-icon class="tab-close" @click.stop="confirmClose(tab.id)">
          <Close />
        </el-icon>
      </div>
    </div>
    <button class="scroll-btn scroll-btn-right" v-show="canScrollRight" @click="scrollRight">
      <el-icon><ArrowRight /></el-icon>
    </button>

    <!-- 环境选择器 -->
    <div class="env-selector-area">
      <el-dropdown trigger="click" @command="(id) => $emit('switch-env', id)">
        <div class="env-current" :title="currentEnvName || '未选择环境'">
          <span
            v-if="currentEnvName"
            class="env-logo-small"
            :style="{ backgroundColor: currentEnvColor }"
          >{{ currentEnvName.charAt(0) }}</span>
          <span class="env-current-name">{{ currentEnvName || '请选择环境' }}</span>
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="env in environments"
              :key="env.id"
              :command="env.id"
            >
              <span
                class="env-logo-small"
                :style="{ backgroundColor: getEnvColor(env.name) }"
              >{{ env.name.charAt(0) }}</span>
              <span style="margin-left: 6px;">{{ env.name }}</span>
            </el-dropdown-item>
            <el-dropdown-item v-if="environments.length === 0" disabled>
              暂无环境
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" class="env-manage-btn" title="环境管理" @click="$emit('open-env-manager')">
        <el-icon><Setting /></el-icon>
      </el-button>
    </div>

    <!-- 右键菜单 -->
    <teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="tab-context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      >
        <div class="menu-item" @click="handleContextAction('close')" :class="{ disabled: !contextMenu.tab }">关闭当前</div>
        <div class="menu-item" @click="handleContextAction('closeOthers')" :class="{ disabled: !contextMenu.tab }">关闭其他</div>
        <div class="menu-item" @click="handleContextAction('closeLeft')" :class="{ disabled: !contextMenu.tab }">关闭左侧</div>
        <div class="menu-item" @click="handleContextAction('closeRight')" :class="{ disabled: !contextMenu.tab }">关闭右侧</div>
        <div class="menu-divider"></div>
        <div class="menu-item" @click="handleContextAction('closeAll')">全部关闭</div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Close, Plus, ArrowLeft, ArrowRight, ArrowDown, Setting } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps({
  tabs: { type: Array, default: () => [] },
  activeTabId: { type: String, default: '' },
  environments: { type: Array, default: () => [] },
  currentEnvId: { type: [Number, String, null], default: null }
})

const emit = defineEmits(['select', 'close', 'closeOthers', 'closeLeft', 'closeRight', 'closeAll', 'switch-env', 'open-env-manager'])

// 环境颜色
const colorPool = [
  '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
  '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6', '#f97316'
]
const envColorMap = {}
function getEnvColor(name) {
  if (!envColorMap[name]) {
    const idx = Object.keys(envColorMap).length % colorPool.length
    envColorMap[name] = colorPool[idx]
  }
  return envColorMap[name]
}
const currentEnvName = computed(() => {
  const env = props.environments.find(e => e.id === props.currentEnvId)
  return env ? env.name : ''
})
const currentEnvColor = computed(() => {
  return currentEnvName.value ? getEnvColor(currentEnvName.value) : '#c0c4cc'
})

const scrollRef = ref(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)

const updateScrollState = () => {
  const el = scrollRef.value
  if (!el) return
  canScrollLeft.value = el.scrollLeft > 0
  canScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 1
}

const scrollLeft = () => {
  if (scrollRef.value) {
    scrollRef.value.scrollBy({ left: -200, behavior: 'smooth' })
  }
}

const scrollRight = () => {
  if (scrollRef.value) {
    scrollRef.value.scrollBy({ left: 200, behavior: 'smooth' })
  }
}

// 当 tabs 变化或 activeTab 变化时，滚动到激活的 tab 并更新箭头状态
watch(() => [props.tabs.length, props.activeTabId], () => {
  nextTick(() => {
    updateScrollState()
    // 滚动到激活的 tab
    const el = scrollRef.value
    if (!el) return
    const activeEl = el.querySelector('.tab-item.active')
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
    }
  })
})

const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  tab: null,
  index: -1
})

const getMethodType = (method) => {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return map[method] || 'info'
}

// 关闭页签：未修改直接关闭，已修改弹确认
const confirmClose = (tabId) => {
  const tab = props.tabs.find(t => t.id === tabId)
  if (tab && !tab.modified) {
    emit('close', tabId)
    return
  }
  ElMessageBox.confirm(
    '当前页签有未保存的修改，确认关闭吗？',
    '提示',
    {
      confirmButtonText: '确认关闭',
      cancelButtonText: '取消',
      type: 'warning',
      customClass: 'tab-close-confirm',
      roundButton: true
    }
  ).then(() => {
    emit('close', tabId)
  }).catch(() => {})
}

// 拦截 Ctrl+W 已移除（浏览器系统快捷键无法拦截）

const showContextMenu = (e, tab, index) => {
  contextMenu.value = { visible: true, x: e.clientX, y: e.clientY, tab, index }
}

const hideContextMenu = () => {
  contextMenu.value.visible = false
}

const handleContextAction = (action) => {
  const tab = contextMenu.value.tab
  const index = contextMenu.value.index
  hideContextMenu()

  switch (action) {
    case 'close':
      if (tab) emit('close', tab.id)
      break
    case 'closeOthers':
      if (tab) emit('closeOthers', tab.id)
      break
    case 'closeLeft':
      if (index >= 0) emit('closeLeft', index)
      break
    case 'closeRight':
      if (index >= 0) emit('closeRight', index)
      break
    case 'closeAll':
      emit('closeAll')
      break
  }
}

let resizeObserver = null

onMounted(() => {
  document.addEventListener('click', hideContextMenu)
  // 鼠标滚轮横向滚动
  scrollRef.value?.addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaY) > 0) {
      e.preventDefault()
      scrollRef.value.scrollLeft += e.deltaY
    }
  }, { passive: false })
  // 监听容器尺寸变化
  resizeObserver = new ResizeObserver(() => updateScrollState())
  if (scrollRef.value) resizeObserver.observe(scrollRef.value)
  updateScrollState()
})

onUnmounted(() => {
  document.removeEventListener('click', hideContextMenu)
  resizeObserver?.disconnect()
})
</script>

<style scoped>
.api-tabs {
  display: flex;
  align-items: center;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-light);
  min-height: 40px;
  flex-shrink: 0;
  padding: 4px 4px 0 4px;
  gap: 2px;
  overflow: hidden;
}

.scroll-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 28px;
  border: none;
  background: var(--el-fill-color);
  color: var(--el-text-color-regular);
  cursor: pointer;
  flex-shrink: 0;
  border-radius: 4px;
  padding: 0;
  transition: all 0.15s;
  font-size: 12px;
}

.scroll-btn:hover {
  background: var(--el-fill-color-dark);
  color: var(--el-color-primary);
}

.env-selector-area {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  margin-left: auto;
  margin-bottom: 4px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 2px 6px 2px 2px;
  background: var(--el-bg-color);
  position: relative;
}

.env-current {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: var(--el-text-color-regular);
  transition: background 0.15s;
  white-space: nowrap;
}

.env-current:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.env-current-name {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.env-logo-small {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.env-manage-btn {
  padding: 3px 4px;
  border: none !important;
  background: transparent;
  outline: none;
  box-shadow: none !important;
  border-radius: 4px;
}

.env-manage-btn:hover,
.env-manage-btn:focus,
.env-manage-btn:active {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.tabs-scroll {
  display: flex;
  overflow-x: auto;
  flex: 1;
  gap: 2px;
  scrollbar-width: none;
}

.tabs-scroll::-webkit-scrollbar {
  display: none;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  height: 34px;
  cursor: pointer;
  white-space: nowrap;
  background: var(--el-fill-color);
  border-radius: 8px 8px 0 0;
  transition: all 0.2s;
  font-size: 13px;
  color: var(--el-text-color-regular);
  flex-shrink: 0;
  max-width: 200px;
}

.tab-item:hover {
  background: var(--el-fill-color-dark);
}

.tab-item.active {
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-weight: 500;
  box-shadow: 0 -1px 3px rgba(0, 0, 0, 0.06);
}

.tab-method {
  flex-shrink: 0;
  transform: scale(0.85);
  border-radius: 4px;
}

.tab-new-icon {
  color: var(--el-color-primary);
  font-size: 14px;
  flex-shrink: 0;
}

.tab-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}

.tab-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-warning);
  flex-shrink: 0;
}

.tab-close {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
  border-radius: 50%;
  padding: 2px;
  transition: all 0.2s;
}

.tab-close:hover {
  background: var(--el-color-danger);
  color: #fff;
}

/* 右键菜单 */
.tab-context-menu {
  position: fixed;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  padding: 6px 0;
  z-index: 9999;
  min-width: 130px;
}

.menu-item {
  padding: 8px 18px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition: all 0.15s;
  border-radius: 0;
}

.menu-item:first-child {
  border-radius: 8px 8px 0 0;
}

.menu-item:last-child {
  border-radius: 0 0 8px 8px;
}

.menu-item:hover {
  background: #ecf5ff;
  color: var(--el-color-primary);
}

.menu-item.disabled {
  color: var(--el-text-color-placeholder);
  cursor: not-allowed;
}

.menu-item.disabled:hover {
  background: transparent;
  color: var(--el-text-color-placeholder);
}

.menu-divider {
  height: 1px;
  background: var(--el-border-color-light);
  margin: 4px 10px;
}


</style>

<!-- 关闭确认弹窗的全局样式 -->
<style>
.tab-close-confirm .el-message-box__header {
  padding-bottom: 8px;
}
.tab-close-confirm .el-message-box__content {
  font-size: 14px;
  color: var(--el-text-color-regular);
}
.tab-close-confirm {
  border-radius: 12px;
  width: 420px;
}
</style>
