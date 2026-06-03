import http from './http'

export async function fetchBloggerTaggingProgress(bloggerId) {
  const { data } = await http.get(`/persona-tagging/bloggers/${bloggerId}/progress`)
  return data
}

export async function submitBloggerTagging(bloggerId, minVideoCount = 15) {
  const { data } = await http.post(`/persona-tagging/bloggers/${bloggerId}/tag`, null, {
    params: { min_video_count: minVideoCount },
  })
  return data
}
