<template>
  <div class="ai-chat-widget">
    <!-- 悬浮按钮 -->
    <div class="ai-fab" @click="toggleChat" :class="{ active: visible }">
      <el-icon :size="26"><ChatDotRound /></el-icon>
    </div>

    <!-- 对话窗口 -->
    <transition name="chat-slide">
      <div
        v-show="visible"
        class="ai-chat-panel"
        :class="{ 'is-fullscreen': fullscreen }"
        :style="fullscreen ? fullscreenStyle : null"
      >
        <div class="chat-header">
          <span class="chat-title">AI 助手</span>
          <div class="chat-header-actions">
            <el-button text size="small" @click="clearMessages" title="清空对话">
              <el-icon><Delete /></el-icon>
            </el-button>
            <el-button
              text
              size="small"
              @click="toggleFullscreen"
              :title="fullscreen ? '退出全屏' : '全屏'"
            >
              <el-icon>
                <component :is="fullscreen ? ScaleToOriginal : FullScreen" />
              </el-icon>
            </el-button>
            <el-button text size="small" @click="visible = false" title="关闭">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </div>

        <div class="chat-messages" ref="messagesRef">
          <div v-if="messages.length === 0" class="chat-empty">
            <el-icon :size="40" color="#c0c4cc"><ChatDotRound /></el-icon>
            <p>你好，我是 AI 助手</p>
            <p class="chat-empty-hint">日常问答 ✦ 测试用例生成 ✦ 都能帮你</p>
            <div class="chat-empty-tips">
              <span class="tip-tag">试试：</span>
              <span class="tip-example">"帮我生成登录功能的测试用例"</span>
            </div>
          </div>
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="chat-message"
            :class="msg.role"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'assistant'" :size="18"><MagicStick /></el-icon>
              <el-icon v-else :size="18"><UserFilled /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text" v-html="renderContent(msg.content)"></div>
            </div>
          </div>
          <!-- 加载中指示器 -->
          <div v-if="loading" class="chat-message assistant">
            <div class="message-avatar">
              <el-icon :size="18"><MagicStick /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text">
                <span class="typing-indicator">
                  <span></span><span></span><span></span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            resize="none"
            @keydown="handleKeydown"
            :disabled="loading"
          />
          <el-button
            type="primary"
            :icon="Promotion"
            circle
            size="small"
            class="send-btn"
            @click="sendMessage"
            :disabled="!inputText.trim() || loading"
            :loading="loading"
          />
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import {
  ChatDotRound, Close, Delete, MagicStick, UserFilled, Promotion,
  FullScreen, ScaleToOriginal,
} from '@element-plus/icons-vue'
import { chat, runTestcaseGenerationWorkflow } from '../api/ai'
import { detectIntent, IntentKind, formatWorkflowResult } from '../utils/agentIntent'

const visible = ref(false)
const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const messagesRef = ref(null)
const route = useRoute()

// 从当前路由动态读 projectId（项目详情类路由都形如 /project/:projectId/...）
// 没拿到就传 undefined，后端会自动走 mock 模式（避免空 project 报错）
const currentProjectId = computed(() => {
  const raw = route.params.projectId
  const num = parseInt(raw)
  return Number.isFinite(num) ? num : undefined
})

// 全屏状态：开启时面板用 fixed 定位铺满中间内容区，
// 但不覆盖 MainLayout 里的 .app-header 和 .footer
const fullscreen = ref(false)
const headerHeight = ref(60)  // .app-header 默认高
const footerHeight = ref(40)  // .footer 默认高（按需重测）

const fullscreenStyle = computed(() => ({
  top: `${headerHeight.value}px`,
  bottom: `${footerHeight.value}px`,
}))

const measureChrome = () => {
  // 实时测量页头页尾高度，避免响应式布局或主题改动后写死的数值失效
  const header = document.querySelector('.app-header')
  const footer = document.querySelector('.main-layout .footer')
  if (header) headerHeight.value = header.getBoundingClientRect().height
  if (footer) footerHeight.value = footer.getBoundingClientRect().height
}

const toggleFullscreen = () => {
  fullscreen.value = !fullscreen.value
  if (fullscreen.value) measureChrome()
  scrollToBottom()
}

const onWindowResize = () => {
  if (fullscreen.value) measureChrome()
}

onMounted(() => {
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
})

const toggleChat = () => {
  visible.value = !visible.value
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  scrollToBottom()

  loading.value = true
  try {
    // 第一步：本地零 token 意图分流
    const intent = detectIntent(text)

    if (intent.kind === IntentKind.TESTCASE_GENERATION) {
      await handleAgentWorkflow(text, intent)
    } else {
      await handleGeneralChat()
    }
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

/**
 * 通用对话路径：直接走 /api/ai/chat，把整段对话历史回传。
 *
 * 注意：只把 user 消息 + 真实成功的 assistant 回复传给 LLM，
 * 之前因网络/超时产生的"请求失败：xxx"占位消息要剔掉，
 * 否则 LLM 会把它们当成上下文从而"模仿"出重复对话的奇怪回复。
 */
const handleGeneralChat = async () => {
  const apiMessages = messages.value
    .filter(m => !(m.role === 'assistant' && m._isError))
    .map(m => ({ role: m.role, content: m.content }))
  try {
    const res = await chat({ messages: apiMessages })
    if (res.code === 0 && res.data) {
      messages.value.push({
        role: 'assistant',
        content: res.data.content || '(空回复)'
      })
    } else {
      messages.value.push({
        role: 'assistant',
        content: `抱歉，出错了：${res.message || '未知错误'}`,
        _isError: true,
      })
    }
  } catch (err) {
    messages.value.push({
      role: 'assistant',
      content: `请求失败：${err.message || '网络错误'}`,
      _isError: true,
    })
  }
}

/**
 * Agent 工作流路径：调 /api/agent/workflow/testcase-generation，
 * 拿到结构化结果后渲染成 markdown 提示。
 *
 * - 命中 RUN_NOW 关键词："跑测试 / 执行用例" 之类 → 执行链路全开
 * - 否则默认 skip_result=true，只生成 + 落库不执行（更安全，避免误触发）
 * - 没拿到 projectId 时只能跑 mock，会提示用户去项目详情页用
 */
const handleAgentWorkflow = async (requirement, intent) => {
  const projectId = currentProjectId.value
  const isMock = !projectId

  // 给用户一个提示性的"加载占位"消息，让他知道在跑工作流
  const placeholderIdx = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: isMock
      ? '🔍 检测到测试需求，但当前不在项目详情页面，将以演示模式（mock）跑一遍流程……'
      : `🔍 检测到测试需求，正在跑「测试用例生成」工作流（项目 ID = ${projectId}）……`
  })
  scrollToBottom()

  try {
    const res = await runTestcaseGenerationWorkflow({
      requirement,
      project_id: projectId,
      mock: isMock,
      mock_review: true,        // 审核闸暂走 mock，前端审核 UI 后续再接
      skip_result: !intent.runNow,  // 默认只生成不执行
    })

    if (res.code === 0 && res.data) {
      messages.value[placeholderIdx] = {
        role: 'assistant',
        content: formatWorkflowResult(res.data)
      }
    } else {
      messages.value[placeholderIdx] = {
        role: 'assistant',
        content: `❌ 工作流执行失败：${res.message || '未知错误'}`
      }
    }
  } catch (err) {
    messages.value[placeholderIdx] = {
      role: 'assistant',
      content: `❌ 请求失败：${err.message || '网络错误'}`
    }
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const clearMessages = () => {
  messages.value = []
  loading.value = false
}

const renderContent = (text) => {
  if (!text) return ''
  // 极简 markdown 渲染：加粗 + 行内代码 + 链接 + 换行
  // 不引入第三方 markdown 库，保持组件轻量
  let html = text
    // 转义 HTML 特殊字符
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // 加粗 **xxx**
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // 行内代码 `xxx`
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // 换行
    .replace(/\n/g, '<br>')
  return html
}
</script>

<style scoped>
.ai-chat-widget {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
}

/* 悬浮按钮 */
.ai-fab {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #6366f1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.4);
  transition: all 0.3s;
}

.ai-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.5);
}

.ai-fab.active {
  background: linear-gradient(135deg, #6366f1, #409eff);
}

/* 对话面板 */
.ai-chat-panel {
  position: absolute;
  bottom: 64px;
  right: 0;
  width: 380px;
  height: 520px;
  background: var(--el-bg-color);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 全屏：钉在视口里，但避开顶部 app-header 和底部 footer
   top / bottom 由组件根据真实 DOM 高度算出来注入到内联 style */
.ai-chat-panel.is-fullscreen {
  position: fixed;
  top: 60px;     /* 兜底值，会被内联 style 覆盖 */
  bottom: 40px;
  left: 0;
  right: 0;
  width: auto;
  height: auto;
  border-radius: 0;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.08);
  z-index: 9998;
}

/* 头部 */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, #409eff, #6366f1);
  color: #fff;
  flex-shrink: 0;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
}

.chat-header-actions {
  display: flex;
  gap: 4px;
}

.chat-header-actions .el-button {
  color: #fff !important;
}

/* 消息区域 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  gap: 8px;
}

.chat-empty p {
  margin: 0;
  font-size: 14px;
}

.chat-empty-hint {
  font-size: 12px !important;
  color: var(--el-text-color-placeholder);
}

.chat-empty-tips {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  max-width: 280px;
  text-align: left;
}

.chat-empty-tips .tip-tag {
  color: var(--el-color-primary);
  font-weight: 600;
  margin-right: 6px;
}

.chat-empty-tips .tip-example {
  font-style: italic;
}

/* 单条消息 */
.chat-message {
  display: flex;
  gap: 8px;
  max-width: 90%;
}

.chat-message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.chat-message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.chat-message.user .message-avatar {
  background: #409eff;
  color: #fff;
}

.chat-message.assistant .message-avatar {
  background: var(--el-fill-color-light);
  color: #6366f1;
}

.message-content {
  max-width: calc(100% - 38px);
}

.message-text {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-message.user .message-text {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-message.assistant .message-text {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  border-bottom-left-radius: 4px;
}

/* assistant 消息内的轻量 markdown 样式 */
.chat-message.assistant .message-text :deep(strong) {
  color: var(--el-color-primary);
  font-weight: 600;
}

.chat-message.assistant .message-text :deep(code) {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
}

/* 打字指示器 */
.typing-indicator {
  display: inline-flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-text-color-secondary);
  animation: typing 1.2s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* 输入区域 */
.chat-input-area {
  padding: 12px;
  border-top: 1px solid var(--el-border-color-light);
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-shrink: 0;
}

.chat-input-area :deep(.el-textarea__inner) {
  font-size: 13px;
  border-radius: 8px;
}

.send-btn {
  flex-shrink: 0;
}

/* 动画 */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.3s ease;
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}
</style>
