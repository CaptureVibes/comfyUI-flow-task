import http from './http'

const BASE = '/video-task-config'

/**
 * @returns {Promise<{ top_percent: number, discard_below: number, select_percent: number,
 *   auto_publish_enabled: boolean, auto_publish_model: string, auto_publish_prompt: string }>}
 */
export async function fetchTaskConfig() {
  const { data } = await http.get(BASE)
  return data
}

/**
 * @param {Object} payload
 * @param {number} [payload.top_percent]
 * @param {number} [payload.discard_below]
 * @param {number} [payload.select_percent]
 * @param {boolean} [payload.auto_publish_enabled]
 * @param {string} [payload.auto_publish_model]
 * @param {string} [payload.auto_publish_prompt]
 */
export async function updateTaskConfig(payload) {
  const { data } = await http.put(BASE, payload)
  return data
}
