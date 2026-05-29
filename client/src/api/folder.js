import request from './request'

// 获取目录列表
export function getFolders(projectId) {
  return request({
    url: `/projects/${projectId}/folders`,
    method: 'get'
  })
}

// 获取目录树（包含接口）
export function getFolderTree(projectId) {
  return request({
    url: `/projects/${projectId}/folders/tree`,
    method: 'get'
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

// 创建目录
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
