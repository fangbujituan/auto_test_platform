import request from './request'

export function getDashboardStats() {
  return request({
    url: '/dashboard/stats',
    method: 'get'
  })
}
