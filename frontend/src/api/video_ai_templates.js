import http from './http'

export async function createVideoAITemplate(payload) {
  const { data } = await http.post('/video-ai-templates', payload)
  return data
}

export async function fetchVideoAITemplates(params = {}) {
  const { data } = await http.get('/video-ai-templates', { params })
  return data
}

// 查询某批 video_source_id 各自是否已有模板，返回 Map<videoSourceId, templateId>
export async function fetchTemplatesByVideoSourceIds(videoSourceIds) {
  const map = {}
  await Promise.all(
    videoSourceIds.map(async (vsId) => {
      try {
        const data = await fetchVideoAITemplates({ video_source_id: vsId, page: 1, page_size: 1 })
        if (data.items && data.items.length > 0) {
          map[vsId] = data.items[0].id
        }
      } catch { /* ignore */ }
    })
  )
  return map
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

export async function restartVideoAITemplate(id) {
  const { data } = await http.post(`/video-ai-templates/${id}/restart`)
  return data
}

export async function fetchVideoAITemplateState(id) {
  const { data } = await http.get(`/video-ai-templates/${id}/state`)
  return data
}

export async function uploadShotImage(templateId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post(`/video-ai-templates/${templateId}/upload-shot`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
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
