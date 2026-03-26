import http from './http'

export async function fetchTagsWithFaces() {
  const res = await http.get('/face-library')
  return res.data
}

export async function triggerFaceSelection(tagId) {
  const res = await http.post(`/face-library/tags/${tagId}/select-face`)
  return res.data
}
