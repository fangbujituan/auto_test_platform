/**
 * 前端校验工具函数
 */

/**
 * 校验邮箱格式
 * @param {string} email - 邮箱地址
 * @returns {boolean} 是否为有效邮箱格式
 */
export function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

/**
 * 校验密码最小长度
 * @param {string} password - 密码
 * @param {number} minLen - 最小长度，默认 6
 * @returns {boolean} 是否满足最小长度要求
 */
export function validatePasswordLength(password, minLen = 6) {
  return typeof password === 'string' && password.length >= minLen
}

/**
 * 校验两次密码是否一致
 * @param {string} password - 密码
 * @param {string} confirmPassword - 确认密码
 * @returns {boolean} 两次密码是否一致
 */
export function validatePasswordMatch(password, confirmPassword) {
  return password === confirmPassword
}
