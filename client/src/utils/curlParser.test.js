/**
 * Bug 条件探索性测试 — 前端 parseCurl
 *
 * 这些测试断言期望的正确行为。
 * 在未修复的代码上运行时，它们应当失败，从而证明 bug 存在。
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3
 */
import { describe, it, expect } from 'vitest'
import { parseCurl } from './curlParser.js'

describe('Bug Condition: 双引号包裹的转义 JSON Body 解析', () => {
  it('--data-raw 双引号包裹 + 转义引号的 JSON 应正确解析为 JSON 对象', () => {
    const curl = 'curl -X POST "https://example.com/api" --data-raw "{\\"ClientID\\":1005,\\"PageIndex\\":1}"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({ ClientID: 1005, PageIndex: 1 })
    expect(result.body_type).toBe('json')
  })

  it('--data-raw 包含空字符串值的转义 JSON 应正确解析', () => {
    const curl = 'curl -X POST "https://example.com/api" --data-raw "{\\"sortfield\\":\\"\\",\\"sorttype\\":\\"\\"}"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({ sortfield: '', sorttype: '' })
    expect(result.body_type).toBe('json')
  })

  it('-d 标志的双引号转义 JSON 应与 --data-raw 行为一致', () => {
    const curl = 'curl -X POST "https://example.com/api" -d "{\\"name\\":\\"test\\"}"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({ name: 'test' })
    expect(result.body_type).toBe('json')
  })
})
