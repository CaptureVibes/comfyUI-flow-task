import http from './http'

export async function fetchTags() {
  const { data } = await http.get('/tags')
  return data
}

export async function createTag(payload) {
  const { data } = await http.post('/tags', payload)
  return data
}

export async function deleteTag(id) {
  await http.delete(`/tags/${id}`)
}

export async function fetchTagsVideoCount(tagIds) {
  const { data } = await http.post('/tags/video-count', { tag_ids: tagIds })
  return data
}
