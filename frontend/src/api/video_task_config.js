import http from './http'

const BASE = '/video-task-config'

/**
 * @returns {Promise<{ round1_enabled: boolean, round1_prompt: string, round1_model: string,
 *   round1_threshold: number, round1_weight: number,
 *   round2_enabled: boolean, round2_prompt: string, round2_model: string,
 *   round2_threshold: number, round2_weight: number }>}
 */
export async function fetchTaskConfig() {
  const { data } = await http.get(BASE)
  return data
}

/**
 * @param {Object} payload
 * @param {boolean} [payload.round1_enabled]
 * @param {string} [payload.round1_prompt]
 * @param {string} [payload.round1_model]
 * @param {number} [payload.round1_threshold]
 * @param {number} [payload.round1_weight]
 * @param {boolean} [payload.round2_enabled]
 * @param {string} [payload.round2_prompt]
 * @param {string} [payload.round2_model]
 * @param {number} [payload.round2_threshold]
 * @param {number} [payload.round2_weight]
 */
export async function updateTaskConfig(payload) {
  const { data } = await http.put(BASE, payload)
  return data
}
