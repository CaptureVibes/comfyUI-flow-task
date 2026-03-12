import http from './http'

export async function createAccount(payload) {
  const { data } = await http.post('/accounts', payload)
  return data
}

export async function fetchAccounts(params = {}) {
  const { data } = await http.get('/accounts', { params })
  return data
}

export async function fetchAccount(id) {
  const { data } = await http.get(`/accounts/${id}`)
  return data
}

export async function patchAccount(id, payload) {
  const { data } = await http.patch(`/accounts/${id}`, payload)
  return data
}

export async function deleteAccount(id) {
  await http.delete(`/accounts/${id}`)
}

// 账号-博主绑定
export async function fetchAccountBloggers(accountId) {
  const { data } = await http.get(`/accounts/${accountId}/bloggers`)
  return data
}

export async function bindBlogger(accountId, tiktokBloggerId) {
  const { data } = await http.post(`/accounts/${accountId}/bloggers`, { tiktok_blogger_id: tiktokBloggerId })
  return data
}

export async function unbindBlogger(accountId, bloggerId) {
  await http.delete(`/accounts/${accountId}/bloggers/${bloggerId}`)
}

export async function updateScheduledPublish(accountId, payload) {
  // payload: { publish_enabled, publish_cron, publish_window_minutes, publish_count }
  const { data } = await http.put(`/accounts/${accountId}/scheduled-publish`, payload)
  return data
}

// AI 生成
export async function triggerAIAccountGeneration(accountId, tagIds) {
  const { data } = await http.post(`/accounts/${accountId}/ai-generate`, { tag_ids: tagIds })
  return data
}

export async function fetchAIGenerationStatus(accountId) {
  const { data } = await http.get(`/accounts/${accountId}/ai-generate/status`)
  return data
}

export async function resumeAIAccountGeneration(accountId) {
  const res = await http.post(`/accounts/${accountId}/ai-generate/resume`)
  return res.data
}

export async function restartAIAccountGeneration(accountId) {
  const res = await http.post(`/accounts/${accountId}/ai-generate/restart`)
  return res.data
}

export async function bulkRestartAIAccountGeneration(accountIds) {
  const res = await http.post('/accounts/bulk-restart-ai-generation', { account_ids: accountIds })
  return res.data
}

// 账号-标签绑定
export async function fetchAccountTags(accountId) {
  const { data } = await http.get(`/accounts/${accountId}/tags`)
  return data
}

export async function bindTagToAccount(accountId, tagId) {
  const { data } = await http.post(`/accounts/${accountId}/tags`, { tag_id: tagId })
  return data
}

export async function unbindTagFromAccount(accountId, tagId) {
  await http.delete(`/accounts/${accountId}/tags/${tagId}`)
}
