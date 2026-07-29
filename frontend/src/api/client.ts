import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request: adjuntar token JWT; no forzar JSON en FormData (rompe el boundary)
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (config.headers && typeof config.headers.set === 'function') {
      config.headers.set('Content-Type', false as unknown as string)
    } else if (config.headers) {
      delete (config.headers as Record<string, unknown>)['Content-Type']
      delete (config.headers as Record<string, unknown>)['content-type']
    }
  }
  return config
})

// Response: auto-refresh en 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const refreshToken = useAuthStore.getState().refreshToken
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_URL || '/api/v1'}/auth/refresh`,
          { refresh_token: refreshToken }
        )
        useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export function formatApiError(err: unknown, fallback: string): string {
  const e = err as {
    code?: string
    message?: string
    response?: { status?: number; data?: { detail?: unknown } }
  }
  if (e?.code === 'ECONNABORTED') {
    return 'Tiempo de espera agotado al procesar el Excel. Reintentá (puede tardar varios minutos).'
  }
  if (!e?.response) {
    return `Sin respuesta del servidor (${e?.message || 'conexión interrumpida'}).`
  }
  const detail = e.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === 'string'
          ? item
          : (item as { msg?: string })?.msg || JSON.stringify(item),
      )
      .join('; ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return `${fallback} (HTTP ${e.response.status || '?'})`
}

export default api
