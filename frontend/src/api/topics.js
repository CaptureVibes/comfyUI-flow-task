import http from './http'

// ── Topics ──────────────────────────────────────────────────────────────────

export async function fetchTopics(params = {}) {
  const { data } = await http.get('/topics', { params })
  return data
}

export async function fetchTopic(id) {
  const { data } = await http.get(`/topics/${id}`)
  return data
}

export async function createTopic(payload) {
  const { data } = await http.post('/topics', payload)
  return data
}

export async function patchTopic(id, payload) {
  const { data } = await http.patch(`/topics/${id}`, payload)
  return data
}

export async function deleteTopic(id) {
  await http.delete(`/topics/${id}`)
}

// ── Mother Keywords ─────────────────────────────────────────────────────────

export async function fetchMotherKeywords(topicId, params = {}) {
  const { data } = await http.get(`/topics/${topicId}/mother-keywords`, { params })
  return data
}

export async function fetchGenStatus(topicId) {
  const { data } = await http.get(`/topics/${topicId}/gen-status`)
  return data
}

export async function createMotherKeyword(topicId, payload) {
  const { data } = await http.post(`/topics/${topicId}/mother-keywords`, payload)
  return data
}

export async function patchMotherKeyword(mkId, payload) {
  const { data } = await http.patch(`/topics/mother-keywords/${mkId}`, payload)
  return data
}

export async function deleteMotherKeyword(mkId) {
  await http.delete(`/topics/mother-keywords/${mkId}`)
}

// ── Keywords ────────────────────────────────────────────────────────────────

export async function createKeyword(mkId, payload) {
  const { data } = await http.post(`/topics/mother-keywords/${mkId}/keywords`, payload)
  return data
}

export async function deleteKeyword(kwId) {
  await http.delete(`/topics/keywords/${kwId}`)
}

// ── AI Generation ───────────────────────────────────────────────────────────

export async function generateKeywords(mkId) {
  const { data } = await http.post(`/topics/mother-keywords/${mkId}/generate-keywords`)
  return data
}

export async function batchGenerateKeywords(topicId) {
  const { data } = await http.post(`/topics/${topicId}/batch-generate-keywords`)
  return data
}

// ── Keyword Gen Config ──────────────────────────────────────────────────────

export async function fetchKeywordGenConfig() {
  const { data } = await http.get('/settings/keyword-gen-config')
  return data
}

export async function updateKeywordGenConfig(payload) {
  const { data } = await http.put('/settings/keyword-gen-config', payload)
  return data
}
