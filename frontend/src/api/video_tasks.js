import http from './http'

// ── Parent task endpoints ──────────────────────────────────────────────────────

export async function createVideoTask(payload) {
  // payload: { account_id, template_id, final_prompt, duration, shots? }
  const { data } = await http.post('/video-tasks', payload)
  return data
}

export async function fetchVideoTasks(dateStr, { accountId, status } = {}) {
  const params = { target_date: dateStr }
  if (accountId) params.account_id = accountId
  if (status) params.status = status
  const { data } = await http.get('/video-tasks', { params })
  return data
}

export async function fetchAccountVideoTasks(accountId, { status } = {}) {
  const params = { account_id: accountId }
  if (status) params.status = status
  const { data } = await http.get('/video-tasks', { params })
  return data
}

export async function fetchVideoTaskState(taskId) {
  const { data } = await http.get(`/video-tasks/${taskId}/state`)
  return data
}

export async function fetchVideoTask(taskId) {
  const { data } = await http.get(`/video-tasks/${taskId}`)
  return data
}

export async function deleteVideoTask(taskId) {
  const { data } = await http.delete(`/video-tasks/${taskId}`)
  return data
}

// ── Batch operations ───────────────────────────────────────────────────────────

export async function uploadVideoTasks(dateStr) {
  const { data } = await http.post(`/video-tasks/daily/${dateStr}/upload`, undefined, { timeout: 60000 })
  return data
}

export async function fetchVideoTaskResults(dateStr) {
  const { data } = await http.post(`/video-tasks/daily/${dateStr}/fetch-results`, undefined, { timeout: 300000 })
  return data
}

export async function fetchVideoTaskStats(dateStr) {
  const params = {}
  if (dateStr) params.target_date = dateStr
  const { data } = await http.get('/video-tasks/stats', { params })
  return data
}

// ── Sub-task endpoints ─────────────────────────────────────────────────────────

export async function patchSubTaskStatus(subTaskId, payload) {
  // payload: { status, result_video_url?, selected? }
  const { data } = await http.patch(`/video-tasks/subtasks/${subTaskId}/status`, payload)
  return data
}

export async function rollbackSubTaskStatus(subTaskId) {
  const { data } = await http.post(`/video-tasks/subtasks/${subTaskId}/rollback`)
  return data
}
