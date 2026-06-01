import request from './request'

export function getDashboardStats() {
  return request({
    url: '/dashboard/stats',
    method: 'get'
  })
}

/**
 * 测试执行趋势（V0.1）。
 * GET /api/dashboard/quality/execution/trend
 *
 * @param {Object}  params
 * @param {number=} params.project_id  项目 ID（不传统计全平台）
 * @param {string=} params.start_date  YYYY-MM-DD（不传默认 end_date - 30 天）
 * @param {string=} params.end_date    YYYY-MM-DD（不传默认今天）
 */
export function getExecutionTrend(params = {}) {
  return request({
    url: '/dashboard/quality/execution/trend',
    method: 'get',
    params,
  })
}
