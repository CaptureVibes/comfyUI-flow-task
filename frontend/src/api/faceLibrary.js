import http from './http'

export async function fetchTagsWithFaces({ page = 1, pageSize = 20 } = {}) {
  const res = await http.get('/face-library', { params: { page, page_size: pageSize } })
  return res.data
}

export async function fetchPendingFaceCount() {
  const res = await http.get('/face-library/pending-count')
  return res.data.count
}

export async function triggerFaceSelection(tagId) {
  const res = await http.post(`/face-library/tags/${tagId}/select-face`)
  return res.data
}

export async function bulkSelectFaces() {
  const res = await http.post('/face-library/bulk-select')
  return res.data
}
