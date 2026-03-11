import http from './http'

export function fetchBloggers(params = {}) {
  return http.get('/tiktok-bloggers', { params })
}

export function createBlogger(payload) {
  // payload: { profile_url: string }
  return http.post('/tiktok-bloggers', payload)
}

export function fetchBlogger(id) {
  return http.get(`/tiktok-bloggers/${id}`)
}

export function patchBlogger(id, payload) {
  return http.patch(`/tiktok-bloggers/${id}`, payload)
}

export function deleteBlogger(id) {
  return http.delete(`/tiktok-bloggers/${id}`)
}

export function fetchBloggerVideos(id, params = {}) {
  return http.get(`/tiktok-bloggers/${id}/videos`, { params })
}

export async function searchBloggers(q = '', limit = 20) {
  const { data } = await http.get('/tiktok-bloggers/search', { params: { q, limit } })
  return data
}

export function updateScheduledPublish(id, payload) {
  // payload: { publish_enabled, publish_cron, publish_window_minutes, publish_count }
  return http.put(`/tiktok-bloggers/${id}/scheduled-publish`, payload)
}
