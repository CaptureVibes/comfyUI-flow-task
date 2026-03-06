import http from './http'

export async function createVideoGeneration(payload) {
  const { data } = await http.post('/video-generations', payload)
  return data
}

export async function fetchDailyGenerations(dateStr) {
  const { data } = await http.get(`/video-generations/daily/${dateStr}`)
  return data
}

export async function uploadDailyGenerations(dateStr) {
  const { data } = await http.post(`/video-generations/daily/${dateStr}/upload`)
  return data
}

export async function fetchAccountGenerations(accountId, status = null, config = {}) {
  const params = status ? { status } : {}
  const { data } = await http.get(`/video-generations/accounts/${accountId}`, { params, ...config })
  return data
}

export async function patchGenerationStatus(jobId, payload) {
  // payload: { status, video_url?, thumbnail_url? }
  const { data } = await http.patch(`/video-generations/${jobId}/status`, payload)
  return data
}

export async function fetchDailyResults(dateStr) {
  const { data } = await http.post(`/video-generations/daily/${dateStr}/fetch-results`)
  return data
}

export async function rollbackGenerationStatus(jobId) {
  const { data } = await http.post(`/video-generations/${jobId}/rollback`)
  return data
}

export async function deleteDailyGeneration(jobId) {
  const { data } = await http.delete(`/video-generations/${jobId}`)
  return data
}
