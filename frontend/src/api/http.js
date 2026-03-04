import axios from 'axios'
import { DUPLICATE_REQUEST_GAP_MS, TOKEN_KEY, USERNAME_KEY } from '../utils/constants.js'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 20000
})

const pendingRequests = new Map()
const recentRequests = new Map()
const DUPLICATE_GAP_MS = DUPLICATE_REQUEST_GAP_MS

function stableStringify(value) {
  if (value === null || value === undefined) {
    return ''
  }
  if (value instanceof FormData) {
    const entries = []
    value.forEach((item, key) => {
      if (item instanceof File) {
        entries.push([key, `${item.name}:${item.size}:${item.type}`])
      } else {
        entries.push([key, String(item)])
      }
    })
    return JSON.stringify(entries)
  }
  const normalize = (input) => {
    if (input === null || input === undefined) return null
    if (typeof input === 'string' || typeof input === 'number' || typeof input === 'boolean') {
      return input
    }
    if (input instanceof Date) return input.toISOString()
    if (input instanceof File) return `${input.name}:${input.size}:${input.type}`
    if (Array.isArray(input)) return input.map((item) => normalize(item))
    if (typeof input === 'object') {
      const output = {}
      Object.keys(input)
        .sort()
        .forEach((key) => {
          output[key] = normalize(input[key])
        })
      return output
    }
    return String(input)
  }

  return JSON.stringify(normalize(value))
}

function buildRequestKey(config) {
  const method = String(config?.method || 'get').toLowerCase()
  const baseURL = String(config?.baseURL || '')
  const url = String(config?.url || '')
  const params = stableStringify(config?.params)
  const data = stableStringify(config?.data)
  return `${method}|${baseURL}|${url}|${params}|${data}`
}

function createDuplicateRequestError(config) {
  const error = new Error('Duplicate request blocked')
  error.name = 'DuplicateRequestError'
  error.isDuplicateRequest = true
  error.config = config
  return error
}

function releaseRequest(config) {
  const key = config?.__requestKey
  if (!key) return
  pendingRequests.delete(key)
  recentRequests.set(key, Date.now())
}

export function isDuplicateRequestError(error) {
  return Boolean(error?.isDuplicateRequest || error?.name === 'DuplicateRequestError')
}

// iframe 模式下的 token 管理
let iframeToken = null

export function setIframeToken(token) {
  iframeToken = token
}

export function getIframeToken() {
  return iframeToken
}

export function clearIframeToken() {
  iframeToken = null
}

http.interceptors.request.use((config) => {
  const requestKey = buildRequestKey(config)
  const now = Date.now()
  const recentAt = recentRequests.get(requestKey)

  if (pendingRequests.has(requestKey)) {
    return Promise.reject(createDuplicateRequestError(config))
  }
  if (recentAt && now - recentAt < DUPLICATE_GAP_MS) {
    return Promise.reject(createDuplicateRequestError(config))
  }

  config.__requestKey = requestKey
  pendingRequests.set(requestKey, now)

  // 优先使用 iframe token，其次使用 localStorage
  const token = iframeToken || localStorage.getItem(TOKEN_KEY) || ''
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    releaseRequest(response.config)
    return response
  },
  (error) => {
    releaseRequest(error?.config)
    if (isDuplicateRequestError(error)) {
      return Promise.reject(error)
    }
    if (error?.response?.status === 401) {
      // 只有在已登录状态下收到 401（token 过期/失效）才自动跳登录页
      // 登录接口本身的 401（密码错误）由调用方自行处理，不触发跳转
      const isLoginRequest = String(error?.config?.url || '').includes('/auth/login')
      if (!isLoginRequest) {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USERNAME_KEY)
        localStorage.removeItem('task_manager_is_admin')
        const base = import.meta.env.BASE_URL || '/'
        const loginPath = base.replace(/\/$/, '') + '/login'
        if (window.location.pathname !== loginPath) {
          window.location.href = loginPath
        }
      }
    }
    return Promise.reject(error)
  }
)

export default http
