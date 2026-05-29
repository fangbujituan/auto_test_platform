import request from './request'

// 获取项目的所有API接口
export function getApis(projectId, params) {
  return request({
    url: `/projects/${projectId}/apis`,
    method: 'get',
    params
  })
}

// 获取单个API接口详情
export function getApi(projectId, apiId) {
  return request({
    url: `/projects/${projectId}/apis/${apiId}`,
    method: 'get'
  })
}

// 创建API接口
export function createApi(projectId, data) {
  return request({
    url: `/projects/${projectId}/apis`,
    method: 'post',
    data
  })
}

// 更新API接口
export function updateApi(projectId, apiId, data) {
  return request({
    url: `/projects/${projectId}/apis/${apiId}`,
    method: 'put',
    data
  })
}

// 删除API接口
export function deleteApi(projectId, apiId) {
  return request({
    url: `/projects/${projectId}/apis/${apiId}`,
    method: 'delete'
  })
}

// 获取API分类列表
export function getApiCategories(projectId) {
  return request({
    url: `/projects/${projectId}/apis/categories`,
    method: 'get'
  })
}

// 测试执行API接口
export function testApi(projectId, apiId, data) {
  return request({
    url: `/projects/${projectId}/apis/${apiId}/test`,
    method: 'post',
    data
  })
}
