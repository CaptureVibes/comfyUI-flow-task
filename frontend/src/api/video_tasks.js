import http from './http'

// ── Parent task endpoints ──────────────────────────────────────────────────────

export async function createVideoTask(payload) {
  // payload: { account_id, template_id, final_prompt, duration, shots? }
  const { data } = await http.post('/video-tasks', payload)
  return data
}

export async function fetchVideoTasks(dateStr, { accountId, status, tiktokBloggerId, page = 1, pageSize = 20 } = {}) {
  const params = { page, page_size: pageSize }
  if (dateStr) params.target_date = dateStr
  if (accountId) params.account_id = accountId
  if (status) params.status = status
  if (tiktokBloggerId) params.tiktok_blogger_id = tiktokBloggerId
  const { data } = await http.get('/video-tasks', { params })
  return data  // { items, total, page, page_size }
}

export async function fetchAccountVideoTasks(accountId, { status, page = 1, pageSize = 100 } = {}) {
  const params = { account_id: accountId, page, page_size: pageSize }
  if (status) params.status = status
  const { data } = await http.get('/video-tasks', { params })
  return data.items ?? data
}

export async function fetchVideoTaskState(taskId) {
  const { data } = await http.get(`/video-tasks/${taskId}/state`)
  return data
}

export async function fetchTaskNavigation(taskId) {
  const { data } = await http.get(`/video-tasks/${taskId}/navigation`)
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

export async function downloadVideos(dateStr) {
  const response = await http.get(`/video-tasks/daily/${dateStr}/download-videos`, {
    responseType: 'blob',
    timeout: 300000,
  })
  return response.data  // Blob
}

export async function downloadLatestPublishedVideos() {
  const response = await http.get('/video-tasks/download-latest-published', {
    responseType: 'blob',
    timeout: 300000,
  })
  return response.data  // Blob
}

export async function resumeVideoTaskScoring(dateStr) {
  const { data } = await http.post(`/video-tasks/daily/${dateStr}/resume-scoring`, undefined, { timeout: 60000 })
  return data
}

export async function fetchVideoTaskStats(dateStr, { tiktokBloggerId } = {}) {
  const params = {}
  if (dateStr) params.target_date = dateStr
  if (tiktokBloggerId) params.tiktok_blogger_id = tiktokBloggerId
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

export async function enqueueSubTask(subTaskId) {
  const { data } = await http.post(`/video-tasks/subtasks/${subTaskId}/enqueue`)
  return data
}

export async function dequeueSubTask(subTaskId) {
  const { data } = await http.post(`/video-tasks/subtasks/${subTaskId}/dequeue`)
  return data
}

export async function deleteSubTask(subTaskId) {
  const { data } = await http.delete(`/video-tasks/subtasks/${subTaskId}`)
  return data
}

export async function saveSubTaskNote(subTaskId, payload) {
  const { data } = await http.patch(`/video-tasks/subtasks/${subTaskId}/note`, payload)
  return data
}
