import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    const username = localStorage.getItem('username')
    
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    if (username) {
      config.headers['X-Username'] = username
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果响应中有error字段，说明是错误响应
    if (res.error) {
      ElMessage.error(res.error || '请求失败')
      return Promise.reject(new Error(res.error || '请求失败'))
    }
    
    // 如果响应有code字段且不为0，说明是错误
    if (res.code !== undefined && res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    
    // 直接返回响应数据
    return res
  },
  error => {
    const res = error.response?.data
    const message = res?.message || res?.error || error.message || '网络错误'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default service
