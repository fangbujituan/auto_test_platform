import request from './request'

// 获取项目的所有Bug
export function getBugs(projectId, params) {
  return request({
    url: `/projects/${projectId}/bugs`,
    method: 'get',
    params
  })
}

// 获取单个Bug详情
export function getBug(projectId, bugId) {
  return request({
    url: `/projects/${projectId}/bugs/${bugId}`,
    method: 'get'
  })
}

// 创建Bug
export function createBug(projectId, data) {
  return request({
    url: `/projects/${projectId}/bugs`,
    method: 'post',
    data
  })
}

// 更新Bug
export function updateBug(projectId, bugId, data) {
  return request({
    url: `/projects/${projectId}/bugs/${bugId}`,
    method: 'put',
    data
  })
}

// 删除Bug
export function deleteBug(projectId, bugId) {
  return request({
    url: `/projects/${projectId}/bugs/${bugId}`,
    method: 'delete'
  })
}

// 解决Bug
export function resolveBug(projectId, bugId, data) {
  return request({
    url: `/projects/${projectId}/bugs/${bugId}/resolve`,
    method: 'post',
    data
  })
}

// 重新打开Bug
export function reopenBug(projectId, bugId) {
  return request({
    url: `/projects/${projectId}/bugs/${bugId}/reopen`,
    method: 'post'
  })
}

// 获取Bug统计信息
export function getBugStatistics(projectId) {
  return request({
    url: `/projects/${projectId}/bugs/statistics`,
    method: 'get'
  })
}

// 获取Bug目录树（包含Bug）
export function getBugTree(projectId) {
  return request({
    url: `/projects/${projectId}/bugs/tree`,
    method: 'get'
  })
}
