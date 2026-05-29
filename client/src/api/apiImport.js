import request from './request'

// cURL预览（解析但不保存）
export function previewCurl(projectId, data) {
  return request({
    url: `/projects/${projectId}/apis/import/curl/preview`,
    method: 'post',
    data
  })
}

// cURL导入
export function importCurl(projectId, data) {
  return request({
    url: `/projects/${projectId}/apis/import/curl`,
    method: 'post',
    data
  })
}

// Swagger预览（解析但不保存）
export function previewSwagger(projectId, data) {
  return request({
    url: `/projects/${projectId}/apis/import/swagger/preview`,
    method: 'post',
    data
  })
}

// Swagger导入
export function importSwagger(projectId, data) {
  return request({
    url: `/projects/${projectId}/apis/import/swagger`,
    method: 'post',
    data
  })
}

// 通过 URL 获取 Swagger 文档
export function fetchSwaggerUrl(projectId, data) {
  return request({
    url: `/projects/${projectId}/apis/import/swagger/fetch-url`,
    method: 'post',
    data
  })
}
