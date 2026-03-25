import http from './http'

export async function triggerCandidateSearch(data) {
  const res = await http.post('/candidates/search', data)
  return res.data
}

export async function fetchCandidateVideos(params = {}) {
  const res = await http.get('/candidates', { params })
  return res.data
}

export async function deleteCandidateVideo(id) {
  await http.delete(`/candidates/${id}`)
}
