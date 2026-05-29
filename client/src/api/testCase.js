import request from './request'

/**
 * 获取测试用例列表
 */
export function getTestCases(params = {}) {
  return request({
    url: '/test-cases',
    method: 'get',
    params
  })
}

/**
 * 获取测试用例详情
 */
export function getTestCase(caseId) {
  return request({
    url: `/test-cases/${caseId}`,
    method: 'get'
  })
}

/**
 * 创建测试用例
 */
export function createTestCase(data) {
  return request({
    url: '/test-cases',
    method: 'post',
    data
  })
}

/**
 * 更新测试用例
 */
export function updateTestCase(caseId, data) {
  return request({
    url: `/test-cases/${caseId}`,
    method: 'put',
    data
  })
}

/**
 * 删除测试用例
 */
export function deleteTestCase(caseId) {
  return request({
    url: `/test-cases/${caseId}`,
    method: 'delete'
  })
}

/**
 * 获取测试用例统计信息
 */
export function getTestCaseStatistics(projectId, moduleId = null) {
  return request({
    url: '/test-cases/statistics',
    method: 'get',
    params: {
      project_id: projectId,
      module_id: moduleId
    }
  })
}
