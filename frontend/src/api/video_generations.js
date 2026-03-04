import http from './http'

export async function createVideoGeneration(payload) {
  const { data } = await http.post('/video-generations', payload)
  return data
}
