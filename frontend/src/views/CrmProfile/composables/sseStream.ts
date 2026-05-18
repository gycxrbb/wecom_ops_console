/** SSE streaming utilities for AI coach. */
import type { StreamPayload } from './aiCoachTypes'

export async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return false
  try {
    const res = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const json = await res.json()
    const newToken = json?.data?.access_token
    if (!newToken) return false
    localStorage.setItem('access_token', newToken)
    return true
  } catch {
    return false
  }
}

export function buildAuthHeaders() {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = localStorage.getItem('access_token')
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

export async function streamSse(
  url: string,
  body: Record<string, any>,
  signal: AbortSignal,
  onEvent: (event: string, payload: StreamPayload) => void,
) {
  // Merge user signal with a 120s timeout for the initial connection
  const timeoutCtrl = new AbortController()
  const timeoutId = setTimeout(() => timeoutCtrl.abort(), 120_000)
  const onUserAbort = () => timeoutCtrl.abort()
  signal.addEventListener('abort', onUserAbort)

  let response: Response
  try {
    response = await fetch(`/api${url}`, {
      method: 'POST',
      headers: buildAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify(body),
      signal: timeoutCtrl.signal,
    })
  } catch (e: any) {
    clearTimeout(timeoutId)
    signal.removeEventListener('abort', onUserAbort)
    if (e?.name === 'AbortError') {
      if (signal.aborted) return  // user cancelled — silent
      throw new Error('连接超时，请检查网络后重试')
    }
    throw e
  } finally {
    clearTimeout(timeoutId)
    signal.removeEventListener('abort', onUserAbort)
  }

  if (!response.ok) {
    if (response.status === 401) {
      // Try token refresh once
      const refreshed = await tryRefreshToken()
      if (refreshed) {
        // Retry with new token
        try {
          response = await fetch(`/api${url}`, {
            method: 'POST',
            headers: buildAuthHeaders(),
            credentials: 'include',
            body: JSON.stringify(body),
            signal,
          })
        } catch (e: any) {
          if (e?.name === 'AbortError') return
          throw e
        }
        if (!response.ok) {
          throw new Error('登录已过期，请重新登录')
        }
      } else {
        throw new Error('登录已过期，请重新登录')
      }
    } else {
      const text = await response.text()
      throw new Error(text || `请求失败 (${response.status})`)
    }
  }
  if (!response.body) {
    throw new Error('流式响应不可用')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''

      for (const chunk of chunks) {
        let event = 'message'
        const dataLines: string[] = []

        for (const line of chunk.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed) continue
          if (trimmed.startsWith(':')) continue
          if (trimmed.startsWith('event:')) {
            event = trimmed.slice(6).trim()
          } else if (trimmed.startsWith('data:')) {
            dataLines.push(trimmed.slice(5).trim())
          }
        }

        if (!dataLines.length) continue
        const payload = JSON.parse(dataLines.join('\n'))
        onEvent(event, payload)
      }
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    throw e
  }

  if (buffer.trim()) {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of buffer.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      if (trimmed.startsWith(':')) continue
      if (trimmed.startsWith('event:')) {
        event = trimmed.slice(6).trim()
      } else if (trimmed.startsWith('data:')) {
        dataLines.push(trimmed.slice(5).trim())
      }
    }
    if (dataLines.length) {
      const payload = JSON.parse(dataLines.join('\n'))
      onEvent(event, payload)
    }
  }
}

export function createSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `crm-ai-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const normalizeHealthWindowDays = (value: unknown) => {
  const parsed = Number(value)
  return [7, 14, 30].includes(parsed) ? parsed : 7
}
