import request from './request'

export function login(data) {
  return request({
    url: '/auth/login',
    method: 'post',
    data
  })
}

export function logout() {
  return request({
    url: '/auth/logout',
    method: 'post'
  })
}

export function getCurrentUser() {
  return request({
    url: '/auth/current',
    method: 'get'
  })
}

export function updateProfile(data) {
  return request({
    url: '/auth/profile',
    method: 'put',
    data
  })
}

export function changePassword(data) {
  return request({
    url: '/auth/password',
    method: 'put',
    data
  })
}
