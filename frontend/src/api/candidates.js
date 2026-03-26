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

export async function batchAIReview(ids) {
  const res = await http.post('/candidates/ai-review', { ids })
  return res.data
}

export async function bulkAIReviewAll(templateType) {
  const params = templateType ? { template_type: templateType } : {}
  const res = await http.post('/candidates/ai-review-all', null, { params })
  return res.data
}

export async function batchImportCandidates(ids) {
  const res = await http.post('/candidates/import', { ids })
  return res.data
}
