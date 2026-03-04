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

export async function fetchEvolinkSettings() {
  const { data } = await http.get('/settings/evolink')
  return data
}

export async function updateEvolinkSettings(payload) {
  const { data } = await http.put('/settings/evolink', payload)
  return data
}
