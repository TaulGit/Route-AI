import { defineStore } from 'pinia'
import { ref } from 'vue'
import { supabase } from '@/lib/supabase'

export interface ChatSessionItem {
  id: number
  session_id: string
  title: string
  latest_message: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatHistoryDetail {
  session_id: string
  title: string
  history: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp?: string
  }>
}

export interface TripRecordItem {
  id: number
  session_id: string
  title: string
  city: string
  record_type: string
  created_at: string
  updated_at: string
}

export interface TripHistoryDetail {
  session_id: string
  title: string
  city: string
  record_type: string
  request_data: Record<string, unknown>
  result_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export const useHistoryStore = defineStore('history', () => {
  const chatItems = ref<ChatSessionItem[]>([])
  const tripItems = ref<TripRecordItem[]>([])
  const loading = ref(false)

  async function loadAll() {
    loading.value = true
    try {
      const [chatRes, tripRes] = await Promise.all([
        supabase.from('chat_sessions').select('id,session_id,title,created_at,updated_at').order('updated_at', { ascending: false }),
        supabase.from('trip_records').select('id,session_id,title,city,record_type,created_at,updated_at').order('updated_at', { ascending: false })
      ])

      if (!chatRes.error) {
        // 为每个会话补充最新消息摘要和消息数
        const sessions = await Promise.all(
          (chatRes.data || []).map(async (session: any) => {
            const { data: msgs } = await supabase
              .from('chat_messages')
              .select('content')
              .eq('chat_session_id', session.id)
              .order('created_at', { ascending: false })
              .limit(1)

            const { count } = await supabase
              .from('chat_messages')
              .select('*', { count: 'exact', head: true })
              .eq('chat_session_id', session.id)

            const latest = msgs?.[0]?.content || ''
            return {
              ...session,
              latest_message: latest.length > 50 ? latest.slice(0, 50) + '…' : latest,
              message_count: count || 0
            }
          })
        )
        chatItems.value = sessions as ChatSessionItem[]
      }

      if (!tripRes.error) {
        tripItems.value = (tripRes.data || []) as TripRecordItem[]
      }
    } finally {
      loading.value = false
    }
  }

  async function loadChatDetail(sessionId: string): Promise<ChatHistoryDetail> {
    const { data: session, error: sessionErr } = await supabase
      .from('chat_sessions')
      .select('*')
      .eq('session_id', sessionId)
      .single()

    if (sessionErr || !session) throw new Error('聊天记录不存在')

    const { data: messages, error: msgErr } = await supabase
      .from('chat_messages')
      .select('role,content,created_at')
      .eq('chat_session_id', session.id)
      .order('created_at', { ascending: true })

    if (msgErr) throw msgErr

    return {
      session_id: session.session_id,
      title: session.title,
      history: (messages || []).map((m: any) => ({
        role: m.role,
        content: m.content,
        timestamp: m.created_at
      }))
    }
  }

  async function loadTripDetail(sessionId: string): Promise<TripHistoryDetail> {
    const { data, error } = await supabase
      .from('trip_records')
      .select('*')
      .eq('session_id', sessionId)
      .single()

    if (error || !data) throw new Error('行程记录不存在')
    return data as TripHistoryDetail
  }

  async function renameChat(sessionId: string, title: string) {
    const { error } = await supabase
      .from('chat_sessions')
      .update({ title })
      .eq('session_id', sessionId)

    if (error) throw error
    const item = chatItems.value.find((c) => c.session_id === sessionId)
    if (item) item.title = title
    return { success: true, title }
  }

  async function renameTrip(sessionId: string, title: string) {
    const { error } = await supabase
      .from('trip_records')
      .update({ title })
      .eq('session_id', sessionId)

    if (error) throw error
    const item = tripItems.value.find((t) => t.session_id === sessionId)
    if (item) item.title = title
    return { success: true, title }
  }

  async function removeChat(sessionId: string) {
    const { error } = await supabase
      .from('chat_sessions')
      .delete()
      .eq('session_id', sessionId)

    if (error) throw error
    chatItems.value = chatItems.value.filter((c) => c.session_id !== sessionId)
  }

  async function removeTrip(sessionId: string) {
    const { error } = await supabase
      .from('trip_records')
      .delete()
      .eq('session_id', sessionId)

    if (error) throw error
    tripItems.value = tripItems.value.filter((t) => t.session_id !== sessionId)
  }

  function getUserId() {
    return supabase.auth.getSession().then(r => r.data.session?.user?.id || '')
  }

  /** 聊天时保存/更新会话和消息到 Supabase */
  async function upsertChatSession(sessionId: string, title: string) {
    const uid = await getUserId()
    if (!uid) return
    const { error } = await supabase.from('chat_sessions').upsert(
      { session_id: sessionId, user_id: uid, title, updated_at: new Date().toISOString() },
      { onConflict: 'session_id' }
    )
    if (error) console.warn('[history] upsertChatSession failed:', error)
  }

  async function insertChatMessage(sessionId: string, role: string, content: string) {
    const { data: session } = await supabase
      .from('chat_sessions')
      .select('id')
      .eq('session_id', sessionId)
      .single()

    if (!session) return

    const { error } = await supabase.from('chat_messages').insert({
      chat_session_id: session.id,
      role,
      content
    })
    if (error) console.warn('[history] insertChatMessage failed:', error)
  }

  /** 行程生成完成后保存到 Supabase */
  async function saveTripRecord(sessionId: string, title: string, city: string, requestData: any, resultData: any, recordType = 'trip') {
    const uid = await getUserId()
    if (!uid) return
    const { error } = await supabase.from('trip_records').upsert(
      { session_id: sessionId, user_id: uid, title, city, request_data: requestData, result_data: resultData, record_type: recordType, updated_at: new Date().toISOString() },
      { onConflict: 'session_id' }
    )
    if (error) console.warn('[history] saveTripRecord failed:', error)
  }

  return {
    chatItems,
    tripItems,
    loading,
    loadAll,
    loadChatDetail,
    loadTripDetail,
    renameChat,
    renameTrip,
    removeChat,
    removeTrip,
    upsertChatSession,
    insertChatMessage,
    saveTripRecord
  }
})
