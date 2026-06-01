import request from './request'

// ==================== 提供商配置 ====================

// 获取所有提供商配置列表
export function getProviders() {
  return request({
    url: '/ai/providers',
    method: 'get'
  })
}

// 创建提供商配置
export function createProvider(data) {
  return request({
    url: '/ai/providers',
    method: 'post',
    data
  })
}

// 获取单个提供商配置详情
export function getProvider(id) {
  return request({
    url: `/ai/providers/${id}`,
    method: 'get'
  })
}

// 更新提供商配置
export function updateProvider(id, data) {
  return request({
    url: `/ai/providers/${id}`,
    method: 'put',
    data
  })
}

// 删除提供商配置
export function deleteProvider(id) {
  return request({
    url: `/ai/providers/${id}`,
    method: 'delete'
  })
}

// 测试已保存的提供商连接
export function testProvider(id) {
  return request({
    url: `/ai/providers/${id}/test`,
    method: 'post'
  })
}

// 测试未保存的提供商连接（使用表单参数）
export function testProviderUnsaved(data) {
  return request({
    url: '/ai/providers/test',
    method: 'post',
    data
  })
}

// 设置默认提供商
export function setDefaultProvider(id) {
  return request({
    url: `/ai/providers/${id}/default`,
    method: 'put'
  })
}

// ==================== 对话接口 ====================

// LLM 类接口默认超时（毫秒）
// 全局 axios 是 10s，但 LLM 推理 + agent 工作流可能需要更久，单独放宽。
const LLM_CHAT_TIMEOUT_MS = 300_000        // 5 分钟（兜底，本地小模型慢时不卡死）
const AGENT_WORKFLOW_TIMEOUT_MS = 300_000  // 5 分钟

// 同步对话
export function chat(data) {
  return request({
    url: '/ai/chat',
    method: 'post',
    data,
    timeout: LLM_CHAT_TIMEOUT_MS,
  })
}

// 流式对话（SSE）
export function chatStream(data, onMessage, onError, onDone) {
  const token = localStorage.getItem('token')
  const username = localStorage.getItem('username')

  const headers = {
    'Content-Type': 'application/json'
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (username) {
    headers['X-Username'] = username
  }

  const controller = new AbortController()

  fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
    signal: controller.signal
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const message = errorData.message || errorData.error || '请求失败'
        if (onError) onError(new Error(message))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue

          const payload = trimmed.slice(6)
          if (payload === '[DONE]') {
            if (onDone) onDone()
            return
          }

          try {
            const parsed = JSON.parse(payload)
            if (onMessage) onMessage(parsed)
          } catch {
            if (onMessage) onMessage(payload)
          }
        }
      }

      if (onDone) onDone()
    })
    .catch((err) => {
      if (err.name !== 'AbortError' && onError) {
        onError(err)
      }
    })

  // 返回 abort 控制器，调用方可用于取消请求
  return controller
}

// ==================== 提示词模板 ====================

// 获取所有提示词模板
export function getPrompts() {
  return request({
    url: '/ai/prompts',
    method: 'get'
  })
}

// 创建提示词模板
export function createPrompt(data) {
  return request({
    url: '/ai/prompts',
    method: 'post',
    data
  })
}

// 获取单个提示词模板详情
export function getPrompt(id) {
  return request({
    url: `/ai/prompts/${id}`,
    method: 'get'
  })
}

// 更新提示词模板
export function updatePrompt(id, data) {
  return request({
    url: `/ai/prompts/${id}`,
    method: 'put',
    data
  })
}

// 删除提示词模板
export function deletePrompt(id) {
  return request({
    url: `/ai/prompts/${id}`,
    method: 'delete'
  })
}

// ==================== Agent 工作流 ====================

/**
 * 启动测试用例生成 Agent 工作流（intent → testcase → review → persist → result）。
 *
 * @param {Object}   data
 * @param {string}   data.requirement      需求描述（必填）
 * @param {number=}  data.project_id        项目 ID；不传时后端会强制 mock 模式
 * @param {boolean=} data.skip_result       True 表示只生成 + 落库，不触发执行
 * @param {boolean=} data.mock              True 时整条链路 mock，零 token + 不写 DB
 * @param {boolean=} data.mock_review       True 时审核闸自动通过
 * @param {string=}  data.review_decision   "approved" / "rejected"，强制注入决策
 * @param {string=}  data.model             覆盖默认 LLM 模型
 * @param {string=}  data.extra_context     附加上下文
 */
export function runTestcaseGenerationWorkflow(data) {
  return request({
    url: '/agent/workflow/testcase-generation',
    method: 'post',
    data,
    timeout: AGENT_WORKFLOW_TIMEOUT_MS,
  })
}
