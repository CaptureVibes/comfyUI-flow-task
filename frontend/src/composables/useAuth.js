/**
 * Auth composable - 集中管理 token 和认证状态
 */
import { TOKEN_KEY, USERNAME_KEY } from '../utils/constants.js'

const IS_ADMIN_KEY = 'task_manager_is_admin'

// Direct exports for convenience
export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token, username, isAdminFlag = false) {
  localStorage.setItem(TOKEN_KEY, token)
  if (username) {
    localStorage.setItem(USERNAME_KEY, username)
  }
  localStorage.setItem(IS_ADMIN_KEY, isAdminFlag ? '1' : '0')
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USERNAME_KEY)
  localStorage.removeItem(IS_ADMIN_KEY)
}

export function isLoggedIn() {
  return Boolean(getToken())
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY) || ''
}

export function isAdmin() {
  return localStorage.getItem(IS_ADMIN_KEY) === '1'
}

// Composable for Vue components
export function useAuth() {
  return { getToken, setToken, clearToken, isLoggedIn, getUsername, isAdmin }
}
