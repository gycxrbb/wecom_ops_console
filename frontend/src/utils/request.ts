import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getPreloaded } from './preloadCache'

const service = axios.create({
  baseURL: '/api',
  timeout: 50000,
  withCredentials: true
})

// ── Token refresh helpers ──
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function doLoginRedirect() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

async function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    throw new Error('no refresh_token')
  }
  const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
  const newToken = res?.data?.data?.access_token
  if (!newToken) {
    throw new Error('refresh failed')
  }
  localStorage.setItem('access_token', newToken)
  return newToken
}

// ── Request interceptor ──
service.interceptors.request.use(
  (config) => {
    // Return preloaded data if available (transparent cache hit)
    const url = config.url || ''
    const cached = getPreloaded(url)
    if (cached !== null) {
      const adapter = config.adapter
      config.adapter = () => Promise.resolve({
        data: cached,
        status: 200,
        statusText: 'OK (preloaded)',
        headers: {},
        config,
      })
    }

    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = 'Bearer ' + token
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Response interceptor ──
service.interceptors.response.use(
  (response) => {
    const res = response.data
    // Backend V2 format compatibility
    if (res.code !== undefined) {
      if (res.code !== 0 && res.code !== 200) {
        if (!window.location.pathname.startsWith('/login')) {
          ElMessage.error(res.message || '系统错误')
        }
        if ((res.code === 40100 || res.code === 401) && !window.location.pathname.startsWith('/login')) {
          doLoginRedirect()
        }
        const err: any = new Error(res.message || '系统错误')
        err.serverCode = res.code
        err.serverData = res.data
        return Promise.reject(err)
      }
      return res.data
    }
    return res
  },
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status

    // Skip if not 401 or the request itself is auth-related
    if (status !== 401 || !originalRequest) {
      const msg = error.response?.data?.detail || error.message || '请求失败'
      ElMessage({ message: msg, type: 'error', duration: 5 * 1000 })
      return Promise.reject(error)
    }

    const url = originalRequest.url || ''
    if (url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/public-key')) {
      doLoginRedirect()
      return Promise.reject(error)
    }

    if (!isRefreshing) {
      isRefreshing = true
      try {
        const newToken = await refreshAccessToken()
        isRefreshing = false
        onRefreshed(newToken)
      } catch (refreshErr) {
        isRefreshing = false
        refreshSubscribers = []
        doLoginRedirect()
        return Promise.reject(refreshErr)
      }
    }

    // Wait for refresh then retry original request
    return new Promise((resolve, reject) => {
      addRefreshSubscriber((token: string) => {
        originalRequest.headers['Authorization'] = 'Bearer ' + token
        service(originalRequest)
          .then((res) => resolve(res))
          .catch((err) => reject(err))
      })
    })
  }
)

export default service
