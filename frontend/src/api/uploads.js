import http from './http'

export async function uploadImageByFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/uploads/image', formData)
  return data
}
