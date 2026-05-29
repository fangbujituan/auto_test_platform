import request from './request'

// ============================================================
// 环境变量（旧接口，保持兼容）
// ============================================================
export function getEnvVariables(projectId) {
  return request.get(`/projects/${projectId}/env-variables`)
}

export function createEnvVariable(projectId, data) {
  return request.post(`/projects/${projectId}/env-variables`, data)
}

export function updateEnvVariable(projectId, id, data) {
  return request.put(`/projects/${projectId}/env-variables/${id}`, data)
}

export function deleteEnvVariable(projectId, id) {
  return request.delete(`/projects/${projectId}/env-variables/${id}`)
}

// ============================================================
// 环境分组 CRUD
// ============================================================
export function getEnvironments(projectId) {
  return request.get(`/projects/${projectId}/environments`)
}

export function createEnvironment(projectId, data) {
  return request.post(`/projects/${projectId}/environments`, data)
}

export function updateEnvironment(projectId, envId, data) {
  return request.put(`/projects/${projectId}/environments/${envId}`, data)
}

export function deleteEnvironment(projectId, envId) {
  return request.delete(`/projects/${projectId}/environments/${envId}`)
}

// ============================================================
// 前置 URL CRUD
// ============================================================
export function getPrefixUrls(projectId, envId) {
  return request.get(`/projects/${projectId}/environments/${envId}/prefix-urls`)
}

export function createPrefixUrl(projectId, envId, data) {
  return request.post(`/projects/${projectId}/environments/${envId}/prefix-urls`, data)
}

export function updatePrefixUrl(projectId, envId, prefixId, data) {
  return request.put(`/projects/${projectId}/environments/${envId}/prefix-urls/${prefixId}`, data)
}

export function deletePrefixUrl(projectId, envId, prefixId) {
  return request.delete(`/projects/${projectId}/environments/${envId}/prefix-urls/${prefixId}`)
}

// ============================================================
// 全局变量 CRUD
// ============================================================
export function getGlobalVariables(projectId) {
  return request.get(`/projects/${projectId}/global-variables`)
}

export function createGlobalVariable(projectId, data) {
  return request.post(`/projects/${projectId}/global-variables`, data)
}

export function updateGlobalVariable(projectId, varId, data) {
  return request.put(`/projects/${projectId}/global-variables/${varId}`, data)
}

export function deleteGlobalVariable(projectId, varId) {
  return request.delete(`/projects/${projectId}/global-variables/${varId}`)
}

// ============================================================
// 全局参数 CRUD（仅 Header 类型）
// ============================================================
export function getGlobalParams(projectId) {
  return request.get(`/projects/${projectId}/global-params`)
}

export function createGlobalParam(projectId, data) {
  return request.post(`/projects/${projectId}/global-params`, data)
}

export function updateGlobalParam(projectId, paramId, data) {
  return request.put(`/projects/${projectId}/global-params/${paramId}`, data)
}

export function deleteGlobalParam(projectId, paramId) {
  return request.delete(`/projects/${projectId}/global-params/${paramId}`)
}

// ============================================================
// 环境变量（按环境分组）
// ============================================================
export function getEnvVariablesByEnv(projectId, envId) {
  return request.get(`/projects/${projectId}/environments/${envId}/variables`)
}

export function createEnvVariableByEnv(projectId, envId, data) {
  return request.post(`/projects/${projectId}/environments/${envId}/variables`, data)
}

export function updateEnvVariableByEnv(projectId, envId, varId, data) {
  return request.put(`/projects/${projectId}/environments/${envId}/variables/${varId}`, data)
}

export function deleteEnvVariableByEnv(projectId, envId, varId) {
  return request.delete(`/projects/${projectId}/environments/${envId}/variables/${varId}`)
}

// ============================================================
// 环境共享
// ============================================================
export function shareEnvironment(projectId, envId) {
  return request.post(`/projects/${projectId}/environments/${envId}/share`)
}

export function unshareEnvironment(projectId, envId) {
  return request.delete(`/projects/${projectId}/environments/${envId}/share`)
}
