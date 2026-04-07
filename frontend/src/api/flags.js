import http from './http'

export async function fetchFlags() {
  const { data } = await http.get('/flags')
  return data
}

export async function createFlag(payload) {
  const { data } = await http.post('/flags', payload)
  return data
}

export async function updateFlag(id, payload) {
  // payload: { name?, color?, is_pinned? }
  const { data } = await http.patch(`/flags/${id}`, payload)
  return data
}

export async function deleteFlag(id) {
  await http.delete(`/flags/${id}`)
}

export async function bulkBindFlags(accountIds, flagIds) {
  const { data } = await http.post('/flags/bulk-bind', {
    account_ids: accountIds,
    flag_ids: flagIds,
  })
  return data
}

export async function bulkUnbindFlags(accountIds, flagIds) {
  const { data } = await http.post('/flags/bulk-unbind', {
    account_ids: accountIds,
    flag_ids: flagIds,
  })
  return data
}
