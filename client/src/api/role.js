import request from './request'

// 获取角色列表
export function getRoles() {
  return request({
    url: '/roles',
    method: 'get'
  })
}

// 获取权限列表
export function getPermissions() {
  return request({
    url: '/roles/permissions',
    method: 'get'
  })
}

// 初始化角色和权限
export function initRoles() {
  return request({
    url: '/roles/init',
    method: 'post'
  })
}
