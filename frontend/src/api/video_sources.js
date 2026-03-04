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
  const { data } = await http.post('/video-sources', payload)
  return data
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
