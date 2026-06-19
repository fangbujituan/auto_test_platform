/**
 * ApiDetailPanel 的跨实例 tab 选择记忆。
 *
 * 父组件 ProjectDetail 里 <api-detail-panel :key="activeTabId" /> 会让面板
 * 在切换接口时被销毁重建——组件内部的 ref/let 都会丢失。
 *
 * 把"每个接口的请求/响应 tab 选择"放到独立 JS 模块里（真正的模块级），
 * 按 apiId 区分，让每个接口独立记忆自己的 tab，互不影响。
 *
 * 语义（用户原话："初始给你我的默认，给你以后全是你当家作主了"）：
 *  - 接口首次被打开 → 默认 'params' / 'body'
 *  - 用户在该接口切到任意 tab → 该接口自己记住
 *  - 切到别的接口 → 用别的接口自己的记忆（互不干扰）
 *  - 离开-回来 → 还是上次离开时的位置
 *  - 刷新页面 → JS 模块重新加载，所有记忆清空，回到默认
 *
 * 注：新建未保存的接口没有 id，本期不记忆它的 tab（每次重建走默认）。
 */

const requestTabByApi = new Map()
const responseTabByApi = new Map()

const DEFAULT_REQUEST_TAB = 'params'
const DEFAULT_RESPONSE_TAB = 'body'

export function getRequestTab(apiId) {
  if (apiId == null) return DEFAULT_REQUEST_TAB
  return requestTabByApi.get(apiId) ?? DEFAULT_REQUEST_TAB
}

export function setRequestTab(apiId, value) {
  if (apiId == null) return  // 未保存的接口不记忆
  requestTabByApi.set(apiId, value)
}

export function getResponseTab(apiId) {
  if (apiId == null) return DEFAULT_RESPONSE_TAB
  return responseTabByApi.get(apiId) ?? DEFAULT_RESPONSE_TAB
}

export function setResponseTab(apiId, value) {
  if (apiId == null) return
  responseTabByApi.set(apiId, value)
}

/** 接口被关闭/删除后清掉记忆，避免长期 session 内存累积 */
export function forgetApi(apiId) {
  if (apiId == null) return
  requestTabByApi.delete(apiId)
  responseTabByApi.delete(apiId)
}
