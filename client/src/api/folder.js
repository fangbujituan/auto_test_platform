import request from './request'

// 获取目录列表（默认 type=api，可传 type=automation 等）
export function getFolders(projectId, params = {}) {
  return request({
    url: `/projects/${projectId}/folders`,
    method: 'get',
    params
  })
}

// 获取目录树（包含接口）
export function getFolderTree(projectId, params = {}) {
  return request({
    url: `/projects/${projectId}/folders/tree`,
    method: 'get',
    params
  })
}

// 获取自动化目录树（包含自动化任务节点）
export function getAutomationFolderTree(projectId) {
  return request({
    url: `/projects/${projectId}/folders/tree`,
    method: 'get',
    params: { type: 'automation' }
  })
}

// 获取Bug目录树（包含Bug）
export function getBugFolderTree(projectId) {
  return request({
    url: `/projects/${projectId}/bugs/tree`,
    method: 'get'
  })
}

// 获取测试用例目录树（包含测试用例）
export function getTestCaseFolderTree(projectId) {
  return request({
    url: `/test-cases/tree/${projectId}`,
    method: 'get'
  })
}

// 初始化项目目录
export function initProjectFolders(projectId) {
  return request({
    url: `/projects/${projectId}/folders/init`,
    method: 'post'
  })
}

// 创建目录（可指定 type，默认 'api'）
export function createFolder(projectId, data) {
  return request({
    url: `/projects/${projectId}/folders`,
    method: 'post',
    data
  })
}

// 更新目录
export function updateFolder(projectId, folderId, data) {
  return request({
    url: `/projects/${projectId}/folders/${folderId}`,
    method: 'put',
    data
  })
}

// 删除目录
export function deleteFolder(projectId, folderId) {
  return request({
    url: `/projects/${projectId}/folders/${folderId}`,
    method: 'delete'
  })
}
