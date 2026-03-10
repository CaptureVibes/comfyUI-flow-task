import http from './http'

/**
 * 获取 Open API 渠道列表（通过后端代理）
 * @param {string} platform - 平台类型: tiktok/youtube/instagram
 * @param {Object} options - 额外参数 { is_active }
 */
export async function fetchChannels(platform, options = {}) {
  const params = { platform }
  if (options.isActive !== undefined) {
    params.is_active = options.isActive
  }
  const { data } = await http.get('/open-api/channels', { params })
  return data
}

/**
 * 创建视频发布任务
 * @param {Object} payload - 发布任务参数
 */
export async function createPublication(payload) {
  const { data } = await http.post('/video-publications', payload)
  return data
}

/**
 * 获取发布任务详情
 * @param {string} publicationId - 发布任务 ID
 */
export async function fetchPublication(publicationId) {
  const { data } = await http.get(`/video-publications/${publicationId}`)
  return data
}

/**
 * 获取子任务的所有发布记录
 * @param {string} subTaskId - 子任务 ID
 */
export async function fetchSubTaskPublications(subTaskId) {
  const { data } = await http.get(`/video-sub-tasks/${subTaskId}/publications`)
  return data
}

/**
 * 同步发布任务状态（从 Open API）
 * @param {string} publicationId - 发布任务 ID
 */
export async function syncPublicationStatus(publicationId) {
  const { data } = await http.post(`/video-publications/${publicationId}/sync`)
  return data
}

/**
 * 检查 Open API 服务健康状态
 */
export async function healthCheck() {
  const { data } = await http.post('/open-api/health-check')
  return data
}
