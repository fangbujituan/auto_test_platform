/**
 * 前端 cURL 解析工具
 * 将 cURL 命令解析为结构化的 HTTP 请求对象
 *
 * 支持：
 * - 多行命令（\ 换行、Windows ^ 换行）
 * - Windows CMD 格式（^ 转义）
 * - -X / --request 方法
 * - -H / --header 请求头（全量提取）
 * - -d / --data / --data-raw / --data-binary 请求体
 * - -F / --form 表单
 * - URL query 参数自动提取
 * - body_type 自动判断：json / form / raw
 */

/**
 * 将 Windows CMD 格式的 cURL 转换为标准 bash 格式
 * CMD 用 ^ 转义特殊字符，如 ^" ^{ ^} ^[ ^] ^\^" 等
 * 
 * 处理顺序很重要：
 * 1. 先处理 ^\^" → " （CMD 中嵌套在字符串内的双引号）
 * 2. 再处理 ^" → "  （CMD 中的普通双引号）
 * 3. 最后处理剩余的 ^X → X
 */
function normalizeCmdCurl(str) {
  // ^\^" → \"  (CMD 中 JSON 值里的引号: ^\^"pageIndex^\^")
  // 保留转义形式，使后续 doubleQuoteRegex 能正确匹配
  str = str.replace(/\^\\\^"/g, '\\"')
  // ^\" → "
  str = str.replace(/\^\\"/g, '"')
  // ^" → "
  str = str.replace(/\^"/g, '"')
  // ^[ ^] ^{ ^} ^& ^| ^< ^> ^^ ^- ^( ^) 等
  str = str.replace(/\^([{}\[\]&|<>^\-()!,;=])/g, '$1')
  return str
}

/**
 * 从 cURL 字符串中提取所有带引号的参数值
 * 支持单引号和双引号，处理转义
 */
function extractQuotedArgs(flag, str) {
  const results = []
  // 匹配 flag 后面跟着的带引号内容
  const regex = new RegExp(
    `(?:${flag})\\s+"((?:[^"\\\\]|\\\\.)*)"|(?:${flag})\\s+'((?:[^'\\\\]|\\\\.)*)'`,
    'g'
  )
  let m
  while ((m = regex.exec(str)) !== null) {
    results.push(m[1] !== undefined ? m[1] : m[2])
  }
  return results
}

/**
 * 解析 cURL 命令
 * @param {string} curlStr - cURL 命令字符串
 * @returns {object} 解析结果
 */
export function parseCurl(curlStr) {
  if (!curlStr || typeof curlStr !== 'string') {
    throw new Error('cURL 命令不能为空')
  }

  curlStr = curlStr.trim()
  if (!curlStr.toLowerCase().startsWith('curl')) {
    throw new Error('不是有效的 cURL 命令')
  }

  // 合并多行（反斜杠换行）
  curlStr = curlStr.replace(/\\\s*\r?\n/g, ' ')
  // Windows CMD 的 ^ 换行
  curlStr = curlStr.replace(/\^\s*\r?\n/g, ' ')

  // 处理 Windows CMD 格式（检测 ^" 或 ^\^" 特征）
  if (curlStr.includes('^"') || curlStr.includes('^\\"') || curlStr.includes('^\\^"')) {
    curlStr = normalizeCmdCurl(curlStr)
  }

  let method = ''
  let url = ''
  const headers = {}
  let body = {}
  let bodyType = 'json'
  let bodyRaw = ''

  // 提取 -X / --request 方法
  const methodMatch = curlStr.match(/(?:-X|--request)\s+['"]?(\w+)['"]?/)
  if (methodMatch) {
    method = methodMatch[1].toUpperCase()
  }

  // 提取 URL（支持带引号和不带引号）
  let urlMatch = curlStr.match(
    /curl\s+(?:.*?\s+)?"(https?:\/\/[^"]+)"/
  )
  if (!urlMatch) {
    urlMatch = curlStr.match(
      /curl\s+(?:.*?\s+)?'(https?:\/\/[^']+)'/
    )
  }
  if (!urlMatch) {
    urlMatch = curlStr.match(
      /curl\s+(?:.*?\s+)?(https?:\/\/[^\s'"]+)/
    )
  }
  if (!urlMatch) {
    urlMatch = curlStr.match(/--url\s+['"]?(https?:\/\/[^\s'"]+)['"]?/)
  }
  if (urlMatch) {
    url = urlMatch[1]
  }

  // 提取所有 -H / --header（全量，不遗漏）
  const headerValues = extractQuotedArgs('-H|--header', curlStr)
  for (const h of headerValues) {
    const colonIdx = h.indexOf(':')
    if (colonIdx > 0) {
      const key = h.substring(0, colonIdx).trim()
      const val = h.substring(colonIdx + 1).trim()
      headers[key] = val
    }
  }

  // 提取 -d / --data / --data-raw / --data-binary
  const dataFlags = '-d|--data|--data-raw|--data-binary'
  
  // 方式1：单引号包裹（bash 格式，最可靠）
  const singleQuoteRegex = new RegExp(`(?:${dataFlags})\\s+'((?:[^'\\\\]|\\\\.)*)'`)
  // 方式2：双引号包裹（内部无未转义引号）
  const doubleQuoteRegex = new RegExp(`(?:${dataFlags})\\s+"((?:[^"\\\\]|\\\\.)*)"`)
  // 方式3：双引号包裹 JSON 对象（CMD 归一化后，内部引号是裸的）
  const jsonObjectRegex = new RegExp(`(?:${dataFlags})\\s+"(\\{[\\s\\S]*?\\})"`)
  
  let dataMatch = curlStr.match(singleQuoteRegex)
  if (!dataMatch) dataMatch = curlStr.match(doubleQuoteRegex)
  if (!dataMatch) dataMatch = curlStr.match(jsonObjectRegex)
  
  if (dataMatch) {
    bodyRaw = dataMatch[1] || ''
    // 处理转义引号（bash 格式 \" → "）
    bodyRaw = bodyRaw.replace(/\\"/g, '"')
    if (!method) {
      method = 'POST'
    }
  } else {
    // 回退：不带引号的简单匹配
    const simpleDataMatch = curlStr.match(
      new RegExp(`(?:${dataFlags})\\s+(\\S+)`)
    )
    if (simpleDataMatch) {
      bodyRaw = simpleDataMatch[1]
      if (!method) {
        method = 'POST'
      }
    }
  }

  // 提取 -F / --form
  const formValues = extractQuotedArgs('-F|--form', curlStr)

  // 如果没有显式指定方法，默认 GET
  if (!method) {
    method = 'GET'
  }

  // URL 不拆分，完整赋值给 path，base_url 留空（后续单独管理）
  const queryParams = {}
  if (url) {
    try {
      const parsed = new URL(url)
      parsed.searchParams.forEach((v, k) => {
        queryParams[k] = v
      })
    } catch {
      // ignore
    }
  }

  // 解析 body
  if (formValues.length > 0) {
    bodyType = 'form'
    for (const item of formValues) {
      const eqIdx = item.indexOf('=')
      if (eqIdx > 0) {
        body[item.substring(0, eqIdx).trim()] = item.substring(eqIdx + 1).trim()
      }
    }
  } else if (bodyRaw) {
    // 尝试 JSON
    try {
      body = JSON.parse(bodyRaw)
      bodyType = 'json'
    } catch {
      // 尝试 form-urlencoded
      if (bodyRaw.includes('=')) {
        bodyType = 'form'
        body = {}
        for (const pair of bodyRaw.split('&')) {
          const eqIdx = pair.indexOf('=')
          if (eqIdx > 0) {
            body[decodeURIComponent(pair.substring(0, eqIdx))] =
              decodeURIComponent(pair.substring(eqIdx + 1))
          }
        }
      } else {
        bodyType = 'raw'
        body = { raw: bodyRaw }
      }
    }
  }

  // 根据 Content-Type 头辅助判断 body_type（如果 body 解析为 json 但 header 说是 form）
  const contentType = Object.keys(headers).find(
    (k) => k.toLowerCase() === 'content-type'
  )
  if (contentType && bodyRaw) {
    const ct = headers[contentType].toLowerCase()
    if (ct.includes('application/x-www-form-urlencoded') && bodyType === 'raw') {
      // 重新尝试 form 解析
      bodyType = 'form'
      body = {}
      for (const pair of bodyRaw.split('&')) {
        const eqIdx = pair.indexOf('=')
        if (eqIdx > 0) {
          body[decodeURIComponent(pair.substring(0, eqIdx))] =
            decodeURIComponent(pair.substring(eqIdx + 1))
        }
      }
    } else if (ct.includes('text/plain') || ct.includes('text/xml') || ct.includes('application/xml')) {
      if (bodyType !== 'json') {
        bodyType = 'raw'
        body = { raw: bodyRaw }
      }
    }
  }

  // 生成接口名称：取 URL 路径最后一段，如 /apiv2/api/billingpricelist/getListPage → getListPage
  let name = 'imported_api'
  if (url) {
    try {
      const pathname = new URL(url).pathname
      const segments = pathname.replace(/\/+$/g, '').split('/')
      name = segments[segments.length - 1] || 'imported_api'
    } catch {
      // fallback
    }
  }

  return {
    method,
    url,
    base_url: '',
    path: url,
    headers,
    params: queryParams,
    body,
    body_type: bodyType,
    name,
    description: `从 cURL 导入: ${method} ${url}`
  }
}
