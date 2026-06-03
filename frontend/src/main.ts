import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/theme.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import Home from './views/Home.vue'
import Result from './views/Result.vue'
import Chat from './views/Chat.vue'
import History from './views/History.vue'
import { supabase } from './lib/supabase'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/result', name: 'Result', component: Result, meta: { requiresAuth: true } },
  { path: '/chat', name: 'Chat', component: Chat, meta: { requiresAuth: true } },
  { path: '/history', name: 'History', component: History, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
const pinia = createPinia()

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 路由守卫：未登录时跳回首页并弹出登录框
router.beforeEach(async (to) => {
  try {
    const { data } = await supabase.auth.getSession()
    const loggedIn = !!data.session

    if (to.meta.requiresAuth && !loggedIn) {
      return { name: 'Home', query: { auth: 'login', redirect: to.fullPath } }
    }
  } catch {
    // Supabase 未配置时跳过鉴权
    console.warn('[Router] Supabase 不可用，跳过鉴权')
  }

  return true
})

app.mount('#app')
