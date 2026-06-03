import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'http://localhost:54321'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'placeholder'

if (!import.meta.env.VITE_SUPABASE_URL) {
  console.warn('[Supabase] VITE_SUPABASE_URL 未配置，Auth 功能将不可用。请在 frontend/.env 中设置。')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
