import request from './request'

// ===== 自动化任务 CRUD =====

/** 获取项目自动化任务列表 */
export function getAutomations(projectId, params) {
  return request({
    url: `/projects/${projectId}/automations`,
    method: 'get',
    params
  })
}

/** 获取自动化任务详情 */
export function getAutomation(projectId, taskId) {
  return request({
    url: `/projects/${projectId}/automations/${taskId}`,
    method: 'get'
  })
}

/** 创建自动化任务 */
export function createAutomation(projectId, data) {
  return request({
    url: `/projects/${projectId}/automations`,
    method: 'post',
    data
  })
}

/** 更新自动化任务 */
export function updateAutomation(projectId, taskId, data) {
  return request({
    url: `/projects/${projectId}/automations/${taskId}`,
    method: 'put',
    data
  })
}

/** 删除自动化任务 */
export function deleteAutomation(projectId, taskId) {
  return request({
    url: `/projects/${projectId}/automations/${taskId}`,
    method: 'delete'
  })
}

// ===== 任务执行 =====

/** 手动触发执行 */
export function executeAutomation(taskId, data = {}) {
  return request({
    url: `/automations/${taskId}/execute`,
    method: 'post',
    data
  })
}

/** 取消执行 */
export function cancelAutomation(taskId) {
  return request({
    url: `/automations/${taskId}/cancel`,
    method: 'post'
  })
}

// ===== 执行历史 =====

/** 获取执行历史列表 */
export function getExecutions(taskId, params) {
  return request({
    url: `/automations/${taskId}/executions`,
    method: 'get',
    params
  })
}

/** 获取执行详情 */
export function getExecutionDetail(execId) {
  return request({
    url: `/executions/${execId}`,
    method: 'get'
  })
}

/** 获取执行统计 */
export function getExecutionStatistics(taskId) {
  return request({
    url: `/automations/${taskId}/statistics`,
    method: 'get'
  })
}
