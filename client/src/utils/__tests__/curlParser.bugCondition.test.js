/**
 * Bug 条件探索性测试 — 前端 parseCurl
 *
 * 模拟用户从浏览器 DevTools 粘贴 CMD/bash 格式 cURL 到文本框的真实场景。
 * 在未修复的代码上运行时，CMD 格式测试应当失败，从而证明 bug 存在。
 *
 * **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
 */
import { describe, it, expect } from 'vitest'
import { parseCurl } from '../curlParser.js'

describe('Bug Condition: CMD 格式 cURL 双引号转义 JSON Body 解析', () => {
  it('CMD 格式 --data-raw 应正确解析 JSON body', () => {
    // 模拟用户从 Chrome DevTools "Copy as cURL (cmd)" 粘贴的内容
    // CMD 格式中 ^" 是转义引号，^\^" 是 JSON 内部的引号
    const curl = 'curl ^"https://example.com/api^" ^-H ^"content-type: application/json;charset=UTF-8^" ^--data-raw ^"^{^\\^"ClientID^\\^":1005,^\\^"PageIndex^\\^":1^}^"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({ ClientID: 1005, PageIndex: 1 })
    expect(result.body_type).toBe('json')
  })

  it('CMD 格式 --data-raw 包含空字符串值应正确解析', () => {
    const curl = 'curl ^"https://example.com/api^" ^-H ^"content-type: application/json;charset=UTF-8^" ^--data-raw ^"^{^\\^"sortfield^\\^":^\\^"^\\^",^\\^"sorttype^\\^":^\\^"^\\^"^}^"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({ sortfield: '', sorttype: '' })
    expect(result.body_type).toBe('json')
  })

  it('CMD 格式完整 cURL（用户实际报告的命令）应正确解析', () => {
    // 简化版的用户实际报告的 CMD curl
    const curl = 'curl ^"https://bnp-test.example.com/api/Test^" ^-H ^"content-type: application/json;charset=UTF-8^" ^--data-raw ^"^{^\\^"ClientID^\\^":1005,^\\^"PageSize^\\^":20,^\\^"sortfield^\\^":^\\^"^\\^",^\\^"PaymentStatus^\\^":^\\^"2^\\^"^}^"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({
      ClientID: 1005,
      PageSize: 20,
      sortfield: '',
      PaymentStatus: '2'
    })
    expect(result.body_type).toBe('json')
    expect(result.method).toBe('POST')
  })
})

describe('Bug Condition: bash 双引号格式 cURL 转义 JSON Body 解析', () => {
  it('bash 双引号 --data-raw 转义 JSON 应正确解析', () => {
    // bash 格式中 \" 是转义引号
    const curl = 'curl -X POST "https://example.com/api" --data-raw "{\\"ClientID\\":1005,\\"PageIndex\\":1}"'
    const result = parseCurl(curl)

    expect(result.body).toEqual({ ClientID: 1005, PageIndex: 1 })
    expect(result.body_type).toBe('json')
  })

  it('bash 双引号 --data-raw 包含空字符串值应正确解析', () => {
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
