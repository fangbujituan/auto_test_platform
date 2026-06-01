/**
 * 前端轻量意图识别（零 token）。
 *
 * 用关键词匹配判断用户消息是否要触发 Agent 工作流。**不做语义理解**——
 * 凡是命中关键词的都先尝试走 agent，命中失败再 fallback 到通用对话。
 *
 * 设计取舍
 * --------
 * - 关键词匹配是个糙活，但完全零 token、零延迟。后续可以把这里换成
 *   一个本地小模型（llama3.2-1b）做意图分类，外部接口保持不变。
 * - 不做 NER 抽取（如"项目 ID""模块"等），那是 IntentAgent 的活；前端
 *   只负责"分流"。
 */

/**
 * 测试用例生成相关关键词。命中其中任意一个就走 agent 工作流。
 *
 * 包括：
 * - 直接动词：生成 / 写 / 设计 / 创建 / 帮我做 / 来一组 …
 * - 测试名词：用例 / 测试用例 / 测试场景 / 测试点 / 测一下 / 测试一下 …
 * - 复合短语：自动化测试 / 跑测试 / 接口测试 / UI 测试 / 性能测试 …
 */
const TESTCASE_KEYWORDS = [
  // 动词
  '生成用例', '生成测试用例', '设计用例', '设计测试用例',
  '写用例', '写测试用例', '帮我写', '帮我设计', '帮我生成',
  '来一组用例', '来一组测试',
  // 名词 + 动作
  '测试场景', '测试点', '用例覆盖', '测试覆盖',
  // 直接的测试动词
  '测一下', '测试一下', '帮我测', '跑测试', '跑用例', '执行用例', '执行测试',
  // 自动化复合短语
  '自动化测试', '接口测试', 'API 测试', 'API测试',
  'UI 测试', 'UI测试', '性能测试', '压力测试',
]

/**
 * 强信号短语：用户清晰要求"立即生成 + 落库 + 执行"，命中后默认 skip_result=false。
 */
const RUN_NOW_KEYWORDS = [
  '跑一下', '跑测试', '跑用例', '执行用例', '执行测试',
  '直接执行', '立刻执行',
]

/**
 * 命中的意图类型。
 */
export const IntentKind = Object.freeze({
  TESTCASE_GENERATION: 'testcase_generation',
  GENERAL_CHAT: 'general_chat',
})

/**
 * 检测一条用户消息的意图。
 *
 * @param {string} text
 * @returns {{ kind: string, runNow: boolean }}
 *   kind:    IntentKind 枚举值
 *   runNow:  仅在 kind === TESTCASE_GENERATION 时有意义；
 *            true 表示用户希望"生成 + 落库 + 执行"一条龙，
 *            false 表示"只生成不执行"
 */
export function detectIntent(text) {
  if (!text) {
    return { kind: IntentKind.GENERAL_CHAT, runNow: false }
  }
  const lower = text.toLowerCase()
  const hit = TESTCASE_KEYWORDS.some((kw) => lower.includes(kw.toLowerCase()))
  if (!hit) {
    return { kind: IntentKind.GENERAL_CHAT, runNow: false }
  }
  const runNow = RUN_NOW_KEYWORDS.some((kw) => lower.includes(kw.toLowerCase()))
  return { kind: IntentKind.TESTCASE_GENERATION, runNow }
}

/**
 * 把工作流响应渲染成对用户友好的 markdown 文本。
 *
 * 注：assistant 消息不需要把 5 个 Agent 的细节都倒出来，只显示对话场景下
 * 真正有用的信息：状态 + 用例数量 + 简短列表 + 跳转/查看入口。
 *
 * @param {Object} workflowData  /api/agent/workflow/testcase-generation 的 data 字段
 * @returns {string}
 */
export function formatWorkflowResult(workflowData) {
  if (!workflowData) {
    return '工作流执行完成，但未返回任何数据。'
  }

  const { workflow_status, output = {}, history = [], invocation_logs = [] } = workflowData
  const lines = []

  // 1) 状态
  if (workflow_status === 'completed') {
    lines.push('✅ **测试用例生成完成**')
  } else if (workflow_status === 'failed') {
    lines.push(`❌ **工作流失败**`)
  } else {
    lines.push(`⏸️ **工作流状态：${workflow_status || '未知'}**`)
  }

  // 2) 意图分类（IntentAgent 产出）
  if (output.test_type) {
    const typeMap = { ui: 'UI 测试', api: 'API 测试', performance: '性能测试' }
    lines.push(`- 测试类型：${typeMap[output.test_type] || output.test_type}`)
  }

  // 3) 用例（TestcaseAgent 产出）
  if (output.case_count) {
    lines.push(`- 生成用例：**${output.case_count} 条**`)
    if (Array.isArray(output.cases)) {
      const titles = output.cases
        .slice(0, 5)
        .map((c, idx) => `  ${idx + 1}. ${c.title || '(未命名)'}`)
      lines.push(...titles)
      if (output.cases.length > 5) {
        lines.push(`  ……还有 ${output.cases.length - 5} 条`)
      }
    }
  }

  // 4) 审核结果
  if (output.review_decision) {
    const map = { approved: '通过', rejected: '驳回', timeout: '超时未审核' }
    lines.push(`- 审核：${map[output.review_decision] || output.review_decision}`)
  }

  // 5) 落库（PersistenceAgent 产出）
  if (Array.isArray(output.case_ids) && output.case_ids.length) {
    lines.push(`- 已落库用例 ID：${output.case_ids.join(', ')}`)
  }

  // 6) 执行结果（ResultAgent 产出）
  if (typeof output.passed === 'number') {
    lines.push(
      `- 执行：通过 ${output.passed} / 失败 ${output.failed || 0} / 总 ${output.total || 0}`
    )
    if (Array.isArray(output.bug_ids) && output.bug_ids.length) {
      lines.push(`- 自动建 Bug：${output.bug_ids.length} 条（id: ${output.bug_ids.join(', ')}）`)
    }
  }

  // 7) Agent 调用日志（折叠，便于排查）
  if (invocation_logs.length) {
    const totalTokens = invocation_logs.reduce(
      (sum, log) => sum + (log.token_count?.input || 0) + (log.token_count?.output || 0),
      0
    )
    if (totalTokens > 0) {
      lines.push(`- 总 Token 消耗：${totalTokens}`)
    }
    const agents = history.map((h) => h.agent_name).join(' → ')
    if (agents) {
      lines.push(`- 链路：${agents}`)
    }
  }

  return lines.join('\n')
}
