import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Session, User } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'

export const useAuthStore = defineStore('auth', () => {
  const session = ref<Session | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  const user = computed<User | null>(() => session.value?.user ?? null)
  const displayName = computed(() => user.value?.user_metadata?.username || user.value?.email?.split('@')[0] || '')
  const isLoggedIn = computed(() => !!session.value)
  const accessToken = computed(() => session.value?.access_token ?? '')

  // 监听 Supabase auth 状态变化（容错）
  try {
    supabase.auth.onAuthStateChange((_event, newSession) => {
      session.value = newSession
      initialized.value = true
    })
  } catch {
    initialized.value = true
  }

  // 初始化：恢复已有 session
  async function init() {
    loading.value = true
    try {
      const { data } = await supabase.auth.getSession()
      session.value = data.session
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function login(email: string, password: string) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    session.value = data.session
    return data.user
  }

  async function register(username: string, email: string, password: string) {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { username } }
    })
    if (error) throw error
    return data.user
  }

  async function logout() {
    await supabase.auth.signOut()
    session.value = null
  }

  // 启动时恢复 session（Supabase 不可用时容错）
  try {
    init()
  } catch {
    initialized.value = true
  }

  return {
    session,
    user,
    displayName,
    loading,
    initialized,
    isLoggedIn,
    accessToken,
    login,
    register,
    logout,
    init
  }
})
