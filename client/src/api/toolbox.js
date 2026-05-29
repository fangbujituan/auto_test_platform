import request from './request'

/**
 * 生成测试用例
 * @param {Object} data - 生成参数
 * @returns {Promise}
 */
export function generateTestCases(data) {
  return request({
    url: '/toolbox/generate-test-cases',
    method: 'post',
    data
  })
}

/**
 * Excel与数据库数据比对
 * @param {FormData} formData - 包含file, sql, mappings, sheet_name(可选)
 * @returns {Promise}
 */
export function compareExcelDB(formData) {
  return request({
    url: '/toolbox/compare-excel-db',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 哈希转明文（字典破解）
 * @param {Object} data - { hash, extra_passwords? }
 * @returns {Promise}
 */
export function crackHash(data) {
  return request({
    url: '/toolbox/crack-hash',
    method: 'post',
    data
  })
}
