<template>
  <div class="ai-chat-widget">
    <!-- 悬浮按钮 -->
    <div class="ai-fab" @click="toggleChat" :class="{ active: visible }">
      <el-icon :size="26"><ChatDotRound /></el-icon>
    </div>

    <!-- 对话窗口 -->
    <transition name="chat-slide">
      <div v-show="visible" class="ai-chat-panel">
        <div class="chat-header">
          <span class="chat-title">AI 助手</span>
          <div class="chat-header-actions">
            <el-button text size="small" @click="clearMessages" title="清空对话">
              <el-icon><Delete /></el-icon>
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
            <p class="chat-empty-hint">有什么可以帮你的？</p>
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
import { ref, nextTick } from 'vue'
import { ChatDotRound, Close, Delete, MagicStick, UserFilled, Promotion } from '@element-plus/icons-vue'
import { chat } from '../api/ai'

const visible = ref(false)
const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const messagesRef = ref(null)

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

  const apiMessages = messages.value.map(m => ({
    role: m.role,
    content: m.content
  }))

  loading.value = true
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
        content: `抱歉，出错了：${res.message || '未知错误'}`
      })
    }
  } catch (err) {
    messages.value.push({
      role: 'assistant',
      content: `请求失败：${err.message || '网络错误'}`
    })
  } finally {
    loading.value = false
    scrollToBottom()
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
  // 简单的换行处理
  return text.replace(/\n/g, '<br>')
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
