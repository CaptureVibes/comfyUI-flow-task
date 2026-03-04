import http from './http'

export async function fetchComfyuiSettings() {
  const { data } = await http.get('/settings/comfyui')
  return data
}

export async function updateComfyuiSettings(payload) {
  const { data } = await http.put('/settings/comfyui', payload)
  return data
}

export async function fetchComfyuiPortStatus() {
  const { data } = await http.get('/settings/comfyui/ports/status')
  return data
}

export async function fetchSystemSettings() {
  const { data } = await http.get('/settings/system')
  return data
}

export async function updateSystemSettings(payload) {
  const { data } = await http.put('/settings/system', payload)
  return data
}

export async function fetchPipelineSettings() {
  const { data } = await http.get('/settings/pipeline')
  return data
}

export async function updatePipelineSettings(payload) {
  const { data } = await http.put('/settings/pipeline', payload)
  return data
}
