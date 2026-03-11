import http from './http'

export async function parseVideoUrl(source_url) {
  const { data } = await http.post('/video-sources/parse', { source_url })
  return data
}

export async function fetchVideoSourceStats() {
  const { data } = await http.get('/video-sources/stats')
  return data
}

export async function createVideoSource(payload) {
  const res = await http.post('/video-sources', payload)
  return { data: res.data, status: res.status }
}

export async function fetchVideoSources(params = {}) {
  const { data } = await http.get('/video-sources', { params })
  return data
}

export async function fetchVideoSource(id) {
  const { data } = await http.get(`/video-sources/${id}`)
  return data
}

export async function deleteVideoSource(id) {
  await http.delete(`/video-sources/${id}`)
}

export async function downloadVideoSource(id) {
  const { data } = await http.post(`/video-sources/${id}/download`)
  return data
}

export async function fetchVideoSourceStatsHistory(id) {
  const { data } = await http.get(`/video-sources/${id}/stats-history`)
  return data.items || []
}

export async function downloadAllVideosZip(token) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
  const resp = await fetch(`${baseUrl}/video-sources/download-all-zip`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) throw new Error(`下载失败: ${resp.status}`)
  return resp.blob()
}
