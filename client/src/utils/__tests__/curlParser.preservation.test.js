/**
 * Preservation 属性测试 — 前端 parseCurl
 *
 * 验证非 bug 条件输入（不涉及"双引号包裹 + 内部含 \" 转义引号"）的行为保持不变。
 * 这些测试在未修复的代码上应当全部通过，确认基线行为。
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
 */
import { describe, it, expect } from 'vitest'
import { parseCurl } from '../curlParser.js'

describe('Preservation: 单引号包裹 JSON body 正确解析 (Req 3.1)', () => {
  it("--data-raw '{}' 单引号 JSON 应解析为 json 类型", () => {
    const curl = `curl -X POST 'https://example.com/api' --data-raw '{"key":"value"}'`
    const result = parseCurl(curl)

    expect(result.body).toEqual({ key: 'value' })
    expect(result.body_type).toBe('json')
  })
})

describe('Preservation: form-urlencoded 正确解析 (Req 3.2)', () => {
  it('-d "key1=value1&key2=value2" 应解析为 form 类型', () => {
    const curl = `curl -X POST https://example.com/api -d "key1=value1&key2=value2"`
    const result = parseCurl(curl)

    expect(result.body_type).toBe('form')
    expect(result.body).toEqual({ key1: 'value1', key2: 'value2' })
  })
})

describe('Preservation: -F/--form multipart 正确解析 (Req 3.3)', () => {
  it('-F "file=@test.txt" 应解析为 form 类型', () => {
    const curl = `curl -X POST https://example.com/api -F "file=@test.txt"`
    const result = parseCurl(curl)

    expect(result.body_type).toBe('form')
    expect(result.body).toEqual({ file: '@test.txt' })
  })
})

describe('Preservation: 纯 GET 请求 body 为空 (Req 3.4)', () => {
  it('无 body 的 GET 请求应返回空对象和 GET 方法', () => {
    const curl = `curl https://example.com/api`
    const result = parseCurl(curl)

    expect(result.body).toEqual({})
    expect(result.method).toBe('GET')
  })
})

describe('Preservation: 不带引号的简单数据回退匹配 (Req 3.5)', () => {
  it('--data-raw 不带引号的简单字符串应通过回退匹配提取', () => {
    const curl = `curl -X POST https://example.com/api --data-raw simpledata`
    const result = parseCurl(curl)

    expect(result.method).toBe('POST')
    expect(result.body).toEqual({ raw: 'simpledata' })
    expect(result.body_type).toBe('raw')
  })
})
