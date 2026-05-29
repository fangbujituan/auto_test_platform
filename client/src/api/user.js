import request from './request'

// 获取所有用户列表（用于添加成员时选择）
export function getUsers() {
  return request({
    url: '/auth/users',
    method: 'get'
  })
}

// 初始化用户
export function initUsers() {
  return request({
    url: '/auth/init',
    method: 'post'
  })
}
