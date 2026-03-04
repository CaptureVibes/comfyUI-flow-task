import http from './http'

export async function login(payload) {
  const { data } = await http.post('/auth/login', payload)
  return data
}

export async function fetchMe() {
  const { data } = await http.get('/auth/me')
  return data
}

// ── User management ──────────────────────────────────────────────────────────

export async function listUsers() {
  const { data } = await http.get('/auth/users')
  return data
}

export async function createUser(payload) {
  const { data } = await http.post('/auth/users', payload)
  return data
}

export async function deleteUser(userId) {
  const { data } = await http.delete(`/auth/users/${userId}`)
  return data
}

export async function changePassword(payload) {
  const { data } = await http.post('/auth/change-password', payload)
  return data
}

// ── User profile ─────────────────────────────────────────────────────────────

export async function getProfile() {
  const { data } = await http.get('/auth/profile')
  return data
}

export async function updateProfile(payload) {
  const { data } = await http.patch('/auth/profile', payload)
  return data
}
