import request from './request'

// ==================== 需求接口 ====================

export function getRequirements(params) {
  return request({ url: '/requirements', method: 'get', params })
}

export function getRequirement(id) {
  return request({ url: `/requirements/${id}`, method: 'get' })
}

export function createRequirement(data) {
  return request({ url: '/requirements', method: 'post', data })
}

export function updateRequirement(id, data) {
  return request({ url: `/requirements/${id}`, method: 'put', data })
}

export function deleteRequirement(id) {
  return request({ url: `/requirements/${id}`, method: 'delete' })
}

export function getRequirementStatuses() {
  return request({ url: '/requirements/statuses', method: 'get' })
}

// ==================== 冲刺接口 ====================

export function getSprints(params) {
  return request({ url: '/sprints', method: 'get', params })
}

export function getSprint(id) {
  return request({ url: `/sprints/${id}`, method: 'get' })
}

export function createSprint(data) {
  return request({ url: '/sprints', method: 'post', data })
}

export function updateSprint(id, data) {
  return request({ url: `/sprints/${id}`, method: 'put', data })
}

export function deleteSprint(id) {
  return request({ url: `/sprints/${id}`, method: 'delete' })
}

// ==================== 标签接口 ====================

export function getTags() {
  return request({ url: '/tags', method: 'get' })
}

export function createTag(data) {
  return request({ url: '/tags', method: 'post', data })
}

export function deleteTag(id) {
  return request({ url: `/tags/${id}`, method: 'delete' })
}

// ==================== 操作日志接口 ====================

export function getOperationLogs(params) {
  return request({ url: '/operation-logs', method: 'get', params })
}
