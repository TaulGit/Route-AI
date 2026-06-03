import axios from 'axios'
import type {
  ChatMessage,
  ChatResponse,
  LLMProvider,
  LocalRouteRequest,
  StreamingResponse,
  TripPlanResponse,
  TripRequest,
  UserFeedback
} from '@/types'

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim()
const API_BASE_URL = import.meta.env.DEV ? '' : (RAW_API_BASE_URL || '')

if (!import.meta.env.DEV && !RAW_API_BASE_URL) {
  console.warn('[API] VITE_API_BASE_URL 未配置，生产环境接口请求将不可用。请在部署平台中设置。')
}

console.log('API_BASE_URL:', API_BASE_URL || '使用代理')

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' }
})

/** 从 Supabase session 获取 token（延迟导入避免循环依赖） */
async function getSupabaseToken(): Promise<string> {
  try {
    const { supabase } = await import('@/lib/supabase')
    const { data } = await supabase.auth.getSession()
    return data.session?.access_token || ''
  } catch {
    return ''
  }
}

apiClient.interceptors.request.use(
  async (config) => {
    const token = await getSupabaseToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    console.log('API Request:', config.method?.toUpperCase(), config.baseURL + config.url, config.data)
    return config
  },
  (error) => {
    console.error('API Request Error:', error)
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.data)
    return response
  },
  (error) => {
    console.error('API Response Error:', error.response?.status, error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// ===========================================
// 旅行规划 API
// ===========================================

export async function createTripPlan(request: TripRequest): Promise<any> {
  const response = await apiClient.post('/api/trip/plan', request)
  return response.data
}

export async function createTripPlanStream(
  request: TripRequest,
  onMessage: (data: StreamingResponse) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): Promise<void> {
  const baseUrl = import.meta.env.DEV ? '' : API_BASE_URL
  const token = await getSupabaseToken()
  const response = await fetch(`${baseUrl}/api/trip/plan/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(request)
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as StreamingResponse
            onMessage(data)
          } catch (e) {
            console.error('Failed to parse SSE data:', e)
          }
        }
      }
    }
  } catch (error) {
    onError(error as Error)
  } finally {
    onComplete()
  }
}

export async function submitFeedback(feedback: UserFeedback): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.post('/api/trip/feedback', feedback)
  return response.data
}

export async function approveTripPlan(sessionId: string, comment?: string): Promise<{ success: boolean; message: string }> {
  return submitFeedback({ session_id: sessionId, action: 'approve', comment })
}

export async function rejectTripPlan(sessionId: string, comment?: string): Promise<{ success: boolean; message: string }> {
  return submitFeedback({ session_id: sessionId, action: 'reject', comment })
}

export async function getTripStatus(sessionId: string): Promise<{
  session_id: string; status: string; current_node: string; steps: unknown[]; errors: string[]
}> {
  const response = await apiClient.get(`/api/trip/status/${sessionId}`)
  return response.data
}

export async function getTripResult(sessionId: string): Promise<TripPlanResponse> {
  const response = await apiClient.get<TripPlanResponse>(`/api/trip/result/${sessionId}`)
  return response.data
}

// ===========================================
// 多轮对话 API
// ===========================================

export async function sendChatMessage(request: ChatMessage): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/api/chat/message', request)
  return response.data
}

export async function getChatHistory(sessionId: string): Promise<{
  session_id: string; history: Array<{ role: string; content: string }>
}> {
  const response = await apiClient.get(`/api/chat/history/${sessionId}`)
  return response.data
}

export async function clearChatHistory(sessionId: string): Promise<{ success: boolean }> {
  const response = await apiClient.delete(`/api/chat/history/${sessionId}`)
  return response.data
}

// ===========================================
// 地图服务 API
// ===========================================

export async function searchPOI(keywords: string, city: string): Promise<{ success: boolean; data: unknown[] }> {
  const response = await apiClient.get('/api/map/poi', { params: { keywords, city } })
  return response.data
}

export async function getWeather(city: string): Promise<{ success: boolean; data: unknown[] }> {
  const response = await apiClient.get('/api/map/weather', { params: { city } })
  return response.data
}

export function getStaticMapUrl(city: string, markers?: string): string {
  const baseUrl = import.meta.env.DEV ? '' : API_BASE_URL
  let url = `${baseUrl}/api/map/staticmap?city=${encodeURIComponent(city)}`
  if (markers) url += `&markers=${encodeURIComponent(markers)}`
  return url
}

// ===========================================
// 系统配置 API
// ===========================================

export async function getLLMProviders(): Promise<{
  current: string; available: LLMProvider[]
}> {
  const response = await apiClient.get('/api/config/llm-providers')
  return response.data
}

export async function healthCheck(): Promise<{ status: string }> {
  const response = await apiClient.get('/health')
  return response.data
}

// ===========================================
// 本地路线规划 API
// ===========================================

export async function createLocalRouteStream(
  request: LocalRouteRequest,
  onEvent: (event: StreamingResponse) => void,
  onError: (error: Error) => void,
  onComplete: (finalData?: Record<string, unknown>) => void,
  signal?: AbortSignal
): Promise<void> {
  const baseUrl = import.meta.env.DEV ? '' : API_BASE_URL
  const token = await getSupabaseToken()

  try {
    const response = await fetch(`${baseUrl}/api/trip/plan/local/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify(request),
      signal
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法获取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.substring(6)) as StreamingResponse
          onEvent(event)
          if (event.node === 'complete' && event.status === 'completed') {
            onComplete(event.data as Record<string, unknown> | undefined)
          }
          if (event.node === 'error') {
            onError(new Error(event.message || '未知错误'))
          }
        } catch { /* skip */ }
      }
    }

    if (buffer.startsWith('data: ')) {
      try { onEvent(JSON.parse(buffer.substring(6))) } catch { /* ignore */ }
    }
  } catch (err: any) {
    if (err.name !== 'AbortError') onError(err)
  }
}

export default apiClient
