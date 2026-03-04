import http from './http'

export async function createVideoAITemplate(payload) {
  const { data } = await http.post('/video-ai-templates', payload)
  return data
}

export async function fetchVideoAITemplates(params = {}) {
  const { data } = await http.get('/video-ai-templates', { params })
  return data
}

export async function fetchVideoAITemplate(id) {
  const { data } = await http.get(`/video-ai-templates/${id}`)
  return data
}

export async function patchVideoAITemplate(id, payload) {
  const { data } = await http.patch(`/video-ai-templates/${id}`, payload)
  return data
}

export async function deleteVideoAITemplate(id) {
  await http.delete(`/video-ai-templates/${id}`)
}

export async function startVideoAITemplate(id) {
  const { data } = await http.post(`/video-ai-templates/${id}/start`)
  return data
}

export async function pauseVideoAITemplate(id) {
  const { data } = await http.post(`/video-ai-templates/${id}/pause`)
  return data
}

export async function resumeVideoAITemplate(id) {
  const { data } = await http.post(`/video-ai-templates/${id}/resume`)
  return data
}

export async function fetchVideoAITemplateState(id) {
  const { data } = await http.get(`/video-ai-templates/${id}/state`)
  return data
}

export async function analyzeVideo(videoSourceId) {
  const { data } = await http.post('/video-ai-templates/analyze-video', null, {
    params: { video_source_id: videoSourceId }
  })
  return data
}

export async function generateImages(templateId) {
  const { data } = await http.post(`/video-ai-templates/generate-images`, null, {
    params: { template_id: templateId }
  })
  return data
}
