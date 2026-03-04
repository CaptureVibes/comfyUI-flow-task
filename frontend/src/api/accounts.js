import http from './http'

export async function createAccount(payload) {
  const { data } = await http.post('/accounts', payload)
  return data
}

export async function fetchAccounts(params = {}) {
  const { data } = await http.get('/accounts', { params })
  return data
}

export async function fetchAccount(id) {
  const { data } = await http.get(`/accounts/${id}`)
  return data
}

export async function patchAccount(id, payload) {
  const { data } = await http.patch(`/accounts/${id}`, payload)
  return data
}

export async function deleteAccount(id) {
  await http.delete(`/accounts/${id}`)
}
