export type AgentMode = 'demo' | 'live'
export type AgentProvider = 'deepseek' | 'aliyun' | 'openai'
export type ReviewAction = 'clarify' | 'approve' | 'revise' | 'reject'

export interface AgentBrief {
  city: string
  date: string
  start_time: string
  end_time: string
  budget_max: number | null
  max_pois: number
  preferences: string[]
  transportation: 'walking' | 'transit' | 'driving'
  notes: string
}

export interface AgentInterrupt {
  id: string
  payload: {
    kind: 'clarify' | 'review'
    missing?: string[]
    brief?: AgentBrief
    draft?: Record<string, unknown>
    validation?: Record<string, unknown>
    [key: string]: unknown
  }
}

export interface AgentEvent {
  run_id: string
  seq: number
  type: 'node_start' | 'node_end' | 'interrupt' | 'complete' | 'error'
  node?: string
  message?: string
  data?: unknown
  [key: string]: unknown
}

export interface AgentSnapshot {
  run_id: string
  status: 'running' | 'interrupted' | 'completed' | 'failed' | 'rejected'
  brief: AgentBrief
  draft?: Record<string, unknown> | null
  validation?: Record<string, unknown> | null
  research_results?: unknown
  interrupt?: AgentInterrupt | null
  events: AgentEvent[]
  metrics: Record<string, unknown>
  mode?: AgentMode
  [key: string]: unknown
}

const baseUrl = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL?.trim() || '').replace(/\/$/, '')

async function headers(): Promise<Record<string, string>> {
  const result: Record<string, string> = { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' }
  try {
    const { supabase } = await import('@/lib/supabase')
    const { data } = await supabase.auth.getSession()
    if (data.session?.access_token) result.Authorization = `Bearer ${data.session.access_token}`
  } catch {
    // The server decides whether an unauthenticated local fixture run is allowed.
  }
  return result
}

async function assertResponse(response: Response): Promise<void> {
  if (response.ok) return
  let detail = ''
  try {
    const body = await response.json()
    detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body.message || body)
  } catch {
    // Keep the status even when a gateway returns a non-JSON response.
  }
  if (response.status === 401) throw new Error('请先登录再运行；免登录示例仅在服务端启用本地演示时可用。')
  throw new Error(detail || `请求失败（HTTP ${response.status}）`)
}

/** Handles split UTF-8 code points, split frames, CRLF, multiline data and the final unclosed frame. */
export async function consumeAgentEvents(response: Response, onEvent: (event: AgentEvent) => void): Promise<void> {
  await assertResponse(response)
  const reader = response.body?.getReader()
  if (!reader) throw new Error('服务器没有返回事件流，请尝试恢复记录。')
  const decoder = new TextDecoder()
  let buffer = ''
  function dispatch(frame: string) {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).replace(/^ /, '')).join('\n')
    if (!data || data === '[DONE]') return
    let event: AgentEvent
    try {
      event = JSON.parse(data) as AgentEvent
    } catch {
      throw new Error('收到无法解析的事件，请使用恢复记录获取已保存的进度。')
    }
    if (!event || typeof event !== 'object' || typeof event.run_id !== 'string' || typeof event.type !== 'string') {
      throw new Error('服务器返回了无效事件，请恢复记录。')
    }
    onEvent(event)
  }
  function drain() {
    let boundary = /\r?\n\r?\n/.exec(buffer)
    while (boundary) {
      dispatch(buffer.slice(0, boundary.index))
      buffer = buffer.slice(boundary.index + boundary[0].length)
      boundary = /\r?\n\r?\n/.exec(buffer)
    }
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      drain()
    }
    buffer += decoder.decode()
    drain()
    if (buffer.trim()) dispatch(buffer)
  } finally {
    reader.releaseLock()
  }
}

export async function startAgentRun(brief: AgentBrief, mode: AgentMode, provider: AgentProvider, onEvent: (event: AgentEvent) => void): Promise<void> {
  const response = await fetch(`${baseUrl}/api/agent/runs`, {
    method: 'POST', headers: await headers(), body: JSON.stringify({ brief, mode, provider })
  })
  await consumeAgentEvents(response, onEvent)
}

export async function resumeAgentRun(runId: string, interruptId: string, action: ReviewAction, brief: AgentBrief, onEvent: (event: AgentEvent) => void): Promise<void> {
  const response = await fetch(`${baseUrl}/api/agent/runs/${encodeURIComponent(runId)}/resume`, {
    method: 'POST', headers: await headers(), body: JSON.stringify({ interrupt_id: interruptId, action, brief })
  })
  await consumeAgentEvents(response, onEvent)
}

export async function getAgentRun(runId: string): Promise<AgentSnapshot> {
  const response = await fetch(`${baseUrl}/api/agent/runs/${encodeURIComponent(runId)}`, { headers: await headers(), cache: 'no-store' })
  await assertResponse(response)
  return response.json()
}
