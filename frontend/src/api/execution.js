import http from './http'
import { TOKEN_KEY } from '../utils/constants.js'

export async function uploadWorkflow(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/uploads/workflow', formData)
  return data
}

export async function executeTask(taskId, payload) {
  const { data } = await http.post(`/execution/task/${taskId}`, payload)
  return data
}

export async function cancelExecutionTask(taskId) {
  const { data } = await http.post(`/execution/task/${taskId}/cancel`)
  return data
}

/**
 * 创建 WebSocket 连接
 * @param {string} taskId
 * @param {{ onError?: (event: Event) => void, onClose?: (event: CloseEvent) => void }} [options]
 * @returns {WebSocket}
 */
export function createExecutionWs(taskId, options = {}) {
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
  const wsBase = apiBase.replace(/^http/, 'ws')
  const token = localStorage.getItem(TOKEN_KEY) || ''
  const ws = new WebSocket(`${wsBase}/execution/ws/${taskId}?token=${encodeURIComponent(token)}`)
  if (options.onError) {
    ws.addEventListener('error', options.onError)
  }
  if (options.onClose) {
    ws.addEventListener('close', options.onClose)
  }
  return ws
}
