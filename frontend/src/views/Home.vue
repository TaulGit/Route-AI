<template>
  <div class="app">
    <div class="hero">
      <div class="grid-overlay"></div>
      <div class="hero-inner">
        <div class="hero-topbar">
          <div class="brand">
            <span class="brand-icon">◈</span>
            <span class="brand-text">RouteAI</span>
          </div>
          <div class="account-actions">
            <template v-if="authStore.isLoggedIn">
              <span class="welcome-user">你好，{{ authStore.displayName }}</span>
              <button class="ghost-btn" @click="$router.push('/history')">历史记录</button>
              <button class="ghost-btn" @click="handleLogout">退出登录</button>
            </template>
            <template v-else>
              <button class="ghost-btn" @click="openAuthDialog('login')">登录</button>
              <button class="ghost-btn primary" @click="openAuthDialog('register')">注册</button>
            </template>
          </div>
        </div>

        <div class="hero-copy">
          <h1>现在就出发</h1>
          <p>{{ isLocalMode ? '本地路线智能规划 · 串联 POI · 优化路线 · 个性推荐' : '多智能体旅行行程规划 · 多城市路线编排 · 住宿餐饮搭配 · 个性推荐' }}</p>
        </div>

        <div class="mode-tabs">
          <div class="mode-pill" :class="{ local: isLocalMode }"></div>
          <button class="tab" :class="{ active: !isLocalMode }" @click="isLocalMode = false; handleModeChange()">
            <span class="tab-dot"></span>旅行行程规划
          </button>
          <button class="tab" :class="{ active: isLocalMode }" @click="isLocalMode = true; handleModeChange()">
            <span class="tab-dot"></span>本地路线规划
          </button>
        </div>
      </div>
    </div>

    <div class="workspace" :class="{ 'with-panel': isLoading || steps.length > 0 }">
      <div class="form-card">
        <form @submit.prevent="handleSubmit">
          <div class="form-section">
            <div class="section-head">
              <span class="section-kicker">Step 01</span>
              <h3>基础信息</h3>
              <p class="section-copy">先确定城市与日期，让整条路线有清晰的出发边界。</p>
            </div>

            <div class="field-row travel-top-row">
              <div class="field travel-city-field">
                <label>{{ isLocalMode ? '本地城市' : '目的地城市' }}</label>
                <div class="input-wrap">
                  <svg class="input-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 2C7.24 2 5 4.24 5 7c0 3.75 5 11 5 11s5-7.25 5-11c0-2.76-2.24-5-5-5zm0 6.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3z"/></svg>
                  <input v-model="formData.city" type="text" :placeholder="isLocalMode ? '例如：武汉、北京、成都' : '例如：北京、上海、成都'" required />
                </div>
              </div>

              <div class="field travel-city-field" v-if="isLocalMode">
                <label>游玩日期</label>
                <el-date-picker v-model="formData.start_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" class="field-control date-field" />
              </div>

              <div class="field travel-date-row" v-else>
                <div class="travel-date-field">
                  <label>出发日期</label>
                  <el-date-picker v-model="formData.start_date" type="date" placeholder="出发日期" value-format="YYYY-MM-DD" class="field-control date-field" />
                </div>
                <div class="travel-date-field">
                  <label>返回日期</label>
                  <el-date-picker v-model="formData.end_date" type="date" placeholder="返回日期" value-format="YYYY-MM-DD" class="field-control date-field" />
                </div>
              </div>
            </div>

            <div class="field-row" v-if="!isLocalMode && travelDays > 0">
              <div class="days-badge">共 {{ travelDays }} 天行程</div>
            </div>

            <template v-if="isLocalMode">
              <div class="field-row">
                <div class="field form-block form-block-large-gap">
                  <label>出发地点 <span class="optional">选填</span></label>
                  <div class="input-wrap">
                    <svg class="input-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="3"/><path d="M10 1v3M10 16v3M1 10h3M16 10h3"/></svg>
                    <input v-model="localFormData.start_address" type="text" placeholder="例如：武汉火车站、光谷广场" />
                  </div>
                </div>
              </div>

              <div class="field form-block form-block-large-gap">
                <label>想去几个地方 <span class="count-badge">{{ localFormData.poi_count }} 个</span></label>
                <div class="slider-track">
                  <input
                    v-model.number="localFormData.poi_count"
                    type="range"
                    min="2"
                    max="10"
                    step="1"
                    class="range-input premium-range"
                    :style="{ background: `linear-gradient(to right, #215786 0%, #215786 ${((localFormData.poi_count - 2) / 8) * 100}%, rgba(181, 196, 211, 0.55) ${((localFormData.poi_count - 2) / 8) * 100}%, rgba(181, 196, 211, 0.55) 100%)` }"
                  />
                  <div class="range-marks">
                    <span v-for="n in [2,4,6,8,10]" :key="n">{{ n }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div class="form-section">
            <div class="section-head">
              <span class="section-kicker">Step 02</span>
              <h3>偏好与限制</h3>
              <p class="section-copy">偏好会影响推荐内容、路线顺序与一天里的节奏感。</p>
            </div>

            <div class="field form-block">
              <label>交通方式</label>
              <div class="transport-group">
                <button
                  v-for="t in transports"
                  :key="t.val"
                  type="button"
                  class="transport-btn"
                  :class="{ active: formData.transportation === t.val }"
                  @click="formData.transportation = t.val"
                >
                  <span>{{ t.icon }}</span>{{ t.label }}
                </button>
              </div>
            </div>

            <div class="field form-block" v-if="!isLocalMode">
              <label>住宿偏好</label>
              <div class="transport-group">
                <button
                  v-for="a in stays"
                  :key="a.val"
                  type="button"
                  class="transport-btn"
                  :class="{ active: formData.accommodation === a.val }"
                  @click="formData.accommodation = a.val"
                >
                  {{ a.label }}
                </button>
              </div>
            </div>

            <div class="field form-block">
              <label>{{ isLocalMode ? '游玩偏好' : '旅行偏好' }}</label>
              <div class="chips">
                <button
                  v-for="p in prefList"
                  :key="p.val"
                  type="button"
                  class="chip"
                  :class="{ active: formData.preferences.includes(p.val) }"
                  @click="togglePref(p.val)"
                >
                  {{ p.label }}
                </button>
              </div>
            </div>

            <div class="field form-block">
              <label>额外要求 <span class="optional">选填</span></label>
              <textarea v-model="formData.free_text_input" rows="2" placeholder="例如：想吃热干面不排队、需要无障碍设施…"></textarea>
            </div>
          </div>

          <div class="field form-block form-block-large-gap">
            <label>预算范围 <span class="budget-range">¥{{ (formData.budget as number[])?.[0] ?? 0 }} — ¥{{ (formData.budget as number[])?.[1] ?? 500 }} <em>{{ budgetLevel }}</em></span></label>
            <el-slider v-model="formData.budget" range :min="0" :max="10000" :step="50" class="budget-slider" />
          </div>

          <div class="field form-block form-block-large-gap">
            <label>AI 模型</label>
            <div class="transport-group">
              <button
                v-for="p in llmProviders"
                :key="p.name"
                type="button"
                class="transport-btn"
                :class="{ active: formData.llm_provider === p.name }"
                @click="formData.llm_provider = p.name"
              >
                {{ p.label }}
              </button>
            </div>
          </div>

          <button v-if="!isLoading" type="submit" class="submit-btn">
            <span>{{ isLocalMode ? '生成智能路线' : '开始规划行程' }}</span>
            <svg viewBox="0 0 20 20" fill="currentColor"><path d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"/></svg>
          </button>
          <button v-else type="button" class="stop-btn" @click="handleStop">
            <span>终止规划</span>
            <svg viewBox="0 0 20 20" fill="currentColor"><rect x="5" y="5" width="10" height="10" rx="1"/></svg>
          </button>
        </form>

        <div class="card-footer">
          <button class="text-link" @click="$router.push('/chat')">切换到对话模式 →</button>
        </div>
      </div>

      <div v-if="isLoading || steps.length > 0" class="panel">
        <div class="panel-header">
          <span class="panel-title">规划进度</span>
          <div v-if="isLoading" class="pulse-dot"></div>
        </div>

        <div class="steps">
          <div v-for="(step, i) in steps" :key="i" class="step" :class="step.status">
            <div class="step-icon">
              <svg v-if="step.status === 'completed'" viewBox="0 0 16 16" fill="currentColor"><path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"/></svg>
              <svg v-else-if="step.status === 'failed'" viewBox="0 0 16 16" fill="currentColor"><path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"/></svg>
              <div v-else class="spinning-dot"></div>
            </div>
            <div class="step-info">
              <div class="step-name">{{ getNodeName(step.node) }}</div>
              <div v-if="step.message" class="step-msg">{{ step.message }}</div>
            </div>
          </div>
        </div>

        <div v-if="isLoading" class="progress-bar-wrap">
          <div class="progress-bar" :style="{ width: progress + '%' }"></div>
        </div>

        <div v-if="isLoading && currentMessage" class="current-msg">{{ currentMessage }}</div>
      </div>
    </div>

    <!-- 登录/注册弹窗 -->
    <el-dialog v-model="authDialogVisible" :title="authTab === 'login' ? '登录' : '注册'" width="400px" :close-on-click-modal="false" destroy-on-close>
      <div class="auth-tab-switch">
        <button :class="{ active: authTab === 'login' }" @click="authTab = 'login'">登录</button>
        <button :class="{ active: authTab === 'register' }" @click="authTab = 'register'">注册</button>
      </div>

      <!-- 登录表单 -->
      <template v-if="authTab === 'login'">
        <el-form @submit.prevent="handleAuthLogin" style="margin-top:18px">
          <el-form-item>
            <el-input v-model="authForm.login.user" placeholder="邮箱" size="large" @keyup.enter="handleAuthLogin" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="authForm.login.pwd" type="password" show-password placeholder="密码" size="large" @keyup.enter="handleAuthLogin" />
          </el-form-item>
          <el-button type="primary" class="full-btn" size="large" :loading="authStore.loading" @click="handleAuthLogin">登录</el-button>
        </el-form>
      </template>

      <!-- 注册表单 -->
      <template v-else>
        <el-form @submit.prevent="handleAuthRegister" style="margin-top:18px">
          <el-form-item>
            <el-input v-model="authForm.register.user" placeholder="用户名" size="large" @keyup.enter="handleAuthRegister" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="authForm.register.email" placeholder="邮箱" size="large" @keyup.enter="handleAuthRegister" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="authForm.register.pwd" type="password" show-password placeholder="密码（6-72字节）" size="large" @keyup.enter="handleAuthRegister" />
          </el-form-item>
          <el-button type="primary" class="full-btn" size="large" :loading="authStore.loading" @click="handleAuthRegister">注册</el-button>
        </el-form>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { useTripStore } from '@/stores/trip'
import { useAuthStore } from '@/stores/auth'
import type { AgentStep, LocalRouteRequest, TripRequest } from '@/types'
import { createLocalRouteStream, getLLMProviders } from '@/services/api'
import { useHistoryStore } from '@/stores/history'

const router = useRouter()
const route = useRoute()
const tripStore = useTripStore()
const authStore = useAuthStore()
const historyStore = useHistoryStore()

const transports = [
  { val: '混合', icon: '🔀', label: '混合' },
  { val: '公共交通', icon: '🚇', label: '公共交通' },
  { val: '自驾', icon: '🚗', label: '自驾' },
  { val: '步行', icon: '🚶', label: '步行' }
]
const stays = [
  { val: '经济型酒店', label: '💰 经济型' },
  { val: '舒适型酒店', label: '🏨 舒适型' },
  { val: '豪华酒店', label: '⭐ 豪华' },
  { val: '民宿', label: '🏡 民宿' }
]
const prefList = [
  { val: '历史文化', label: '🏛️ 历史文化' },
  { val: '自然风光', label: '🏞️ 自然风光' },
  { val: '美食', label: '🍜 美食' },
  { val: '购物', label: '🛍️ 购物' },
  { val: '艺术展览', label: '🎨 艺术展览' },
  { val: '休闲放松', label: '☕ 休闲放松' },
  { val: '网红打卡', label: '📸 网红打卡' },
  { val: '亲子游玩', label: '👨‍👩‍👧 亲子游玩' },
  { val: '运动户外', label: '🏃 运动户外' },
  { val: '小众秘境', label: '🗿 小众秘境' },
  { val: '建筑城市漫步', label: '🏙️ 城市漫步' },
  { val: '博物馆巡礼', label: '🏺 博物馆巡礼' },
  { val: '古镇园林', label: '🏯 古镇园林' }
]

interface LLMInfo {
  name: string
  label: string
}

const LLM_LABELS: Record<string, string> = {
  deepseek: 'DeepSeek',
  aliyun: 'Qwen',
  openai: 'OpenAI'
}

const llmProviders = ref<LLMInfo[]>([])
const isLocalMode = ref(false)
const isLoading = ref(false)
const isStopped = ref(false)
const steps = ref<AgentStep[]>([])
const progress = ref(0)
const currentMessage = ref('')
const abortController = ref<AbortController | null>(null)

const formData = ref<TripRequest>({
  city: '',
  start_date: '',
  end_date: '',
  travel_days: 1,
  transportation: '混合',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: '',
  llm_provider: 'deepseek',
  budget: [0, 500] as [number, number]
})

const localFormData = ref<LocalRouteRequest>({
  city: '',
  date: '',
  start_time: '09:00',
  end_time: '18:00',
  start_address: '',
  transportation: '混合',
  preferences: [],
  free_text_input: '',
  budget: [200, 500],
  llm_provider: 'deepseek',
  poi_count: 5
})

const travelDays = computed(() => {
  if (!formData.value.start_date || !formData.value.end_date) return 0
  const start = dayjs(formData.value.start_date)
  const end = dayjs(formData.value.end_date)
  const days = end.diff(start, 'day') + 1
  return days > 0 ? days : 0
})

const budgetLevel = computed(() => {
  const max = (formData.value.budget as [number, number])?.[1] ?? 500
  if (max <= 200) return '学生党'
  if (max <= 500) return '经济出行'
  if (max <= 1500) return '舒适旅行'
  if (max <= 3000) return '品质游玩'
  if (max <= 5000) return '高端体验'
  return '奢华之旅'
})

watch(travelDays, (days) => {
  if (days > 0) {
    formData.value.travel_days = days
  }
})

watch(() => formData.value.city, (city) => {
  localFormData.value.city = city
})

watch(() => formData.value.start_date, (date) => {
  localFormData.value.date = date
})

function togglePref(val: string) {
  const idx = formData.value.preferences.indexOf(val)
  if (idx >= 0) formData.value.preferences.splice(idx, 1)
  else formData.value.preferences.push(val)
}

// ---------- 登录/注册弹窗 ----------
const authDialogVisible = ref(false)
const authTab = ref<'login' | 'register'>('login')
const authForm = ref({
  login: { user: '', pwd: '' },
  register: { user: '', email: '', pwd: '' },
})

function openAuthDialog(tab: 'login' | 'register') {
  authTab.value = tab
  authDialogVisible.value = true
}

function getPasswordBytes(text: string) {
  return new TextEncoder().encode(text).length
}

async function handleAuthLogin() {
  const { user, pwd } = authForm.value.login
  if (!user.trim() || !pwd.trim()) {
    ElMessage.warning('请输入邮箱和密码')
    return
  }

  try {
    await authStore.login(user, pwd)
    ElMessage.success('登录成功')
    authDialogVisible.value = false
    authForm.value.login = { user: '', pwd: '' }
  } catch (error: any) {
    ElMessage.error(error?.message || '登录失败')
  }
}

async function handleAuthRegister() {
  const { user, email, pwd } = authForm.value.register
  if (!user.trim() || !email.trim() || !pwd.trim()) {
    ElMessage.warning('请完整填写注册信息')
    return
  }

  if (getPasswordBytes(pwd) > 72) {
    ElMessage.warning('密码长度不能超过72字节，请缩短后重试')
    return
  }

  try {
    await authStore.register(user, email, pwd)
    ElMessage.success('注册成功，请检查邮箱确认或直接登录')
    authTab.value = 'login'
    authForm.value.register = { user: '', email: '', pwd: '' }
  } catch (error: any) {
    ElMessage.error(error?.message || '注册失败')
  }
}
// ----------------------------------------

async function loadProviders() {
  try {
    const { current, available } = await getLLMProviders()
    llmProviders.value = available.map(item => ({
      name: item.name,
      label: LLM_LABELS[item.name] || item.model || item.name
    }))
    if (available.some(item => item.name === current)) {
      formData.value.llm_provider = current
      localFormData.value.llm_provider = current
    }
  } catch {
    llmProviders.value = [
      { name: 'deepseek', label: 'DeepSeek' },
      { name: 'aliyun', label: 'Qwen' }
    ]
  }
}

function handleModeChange() {
  tripStore.reset()
  steps.value = []
  progress.value = 0
  currentMessage.value = ''
}

function getNodeName(node: string): string {
  const names: Record<string, string> = {
    init: '初始化',
    intent_analysis: '意图分析',
    poi_search: 'POI 搜索',
    review_enrich: '评价增强',
    weather: '天气查询',
    hotel: '酒店推荐',
    route_optimizer: '路线优化',
    planner: '行程生成',
    budget_validator: '预算校验',
    human_review: '等待审核',
    complete: '完成',
    stopped: '已终止',
    error: '错误'
  }
  return names[node] || node
}

async function handleSubmit() {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录后再生成行程')
    openAuthDialog('login')
    return
  }

  if (isLocalMode.value) await handleLocalSubmit()
  else await handleTripSubmit()
}

async function handleLocalSubmit() {
  const city = formData.value.city
  const date = formData.value.start_date
  if (!city || !date) {
    ElMessage.warning('请填写城市和日期')
    return
  }

  localFormData.value.city = city
  localFormData.value.date = date
  isLoading.value = true
  isStopped.value = false
  steps.value = []
  progress.value = 0
  currentMessage.value = '正在初始化...'

  const sessionId = `route_${Date.now()}`
  tripStore.setSessionId(sessionId)
  tripStore.setTitle(`${city} ${date} 路线`)
  abortController.value = new AbortController()

  const request: LocalRouteRequest = {
    ...localFormData.value,
    session_id: sessionId,
    city,
    date,
    preferences: formData.value.preferences,
    free_text_input: formData.value.free_text_input,
    budget: formData.value.budget,
    llm_provider: formData.value.llm_provider
  }

  try {
    await createLocalRouteStream(
      request,
      (event) => {
        currentMessage.value = event.message || currentMessage.value
        progress.value = Math.min(100, Math.round((event.step / 6) * 100))
        const index = steps.value.findIndex((s) => s.node === event.node)
        const step: AgentStep = {
          node: event.node,
          status: event.status,
          message: event.message,
          data: event.data
        }
        if (index >= 0) steps.value[index] = step
        else steps.value.push(step)
      },
      (error) => {
        ElMessage.error(error.message || '路线规划失败')
        tripStore.addError(error.message || '路线规划失败')
      },
      (finalData) => {
        if (finalData?.itinerary) {
          tripStore.loadTripHistory(sessionId, `${city} ${date} 路线`, finalData.itinerary as any, 'local_route')
          historyStore.saveTripRecord(sessionId, `${city} ${date} 路线`, city,
            { city, date, preferences: formData.value.preferences },
            finalData.itinerary, 'local_route')
        }
      },
      abortController.value.signal
    )
  } catch (error: any) {
    if (error.name !== 'AbortError') ElMessage.error(error.message || '请求失败')
  } finally {
    isLoading.value = false
    abortController.value = null
    if (!isStopped.value) router.push('/result')
  }
}

async function handleTripSubmit() {
  if (!formData.value.city || !formData.value.start_date || !formData.value.end_date) {
    ElMessage.warning('请填写完整信息')
    return
  }

  isLoading.value = true
  isStopped.value = false
  steps.value = []
  progress.value = 0
  currentMessage.value = '正在初始化...'

  const sessionId = `session_${Date.now()}`
  tripStore.setSessionId(sessionId)
  tripStore.setTitle(`${formData.value.city} ${formData.value.start_date} 行程`)
  abortController.value = new AbortController()

  try {
    const baseUrl = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
    const response = await fetch(`${baseUrl}/api/trip/plan/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authStore.accessToken}`
      },
      body: JSON.stringify({ ...formData.value, session_id: sessionId }),
      signal: abortController.value.signal
    })

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      if (isStopped.value) {
        await reader.cancel()
        break
      }
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          currentMessage.value = event.message || currentMessage.value
          progress.value = Math.min(100, Math.round((event.step / 6) * 100))
          const index = steps.value.findIndex((s) => s.node === event.node)
          const step: AgentStep = {
            node: event.node,
            status: event.status,
            message: event.message,
            data: event.data
          }
          if (index >= 0) steps.value[index] = step
          else steps.value.push(step)

          if (event.node === 'complete' && event.status === 'completed' && event.data?.itinerary) {
            tripStore.setTripPlan(event.data.itinerary)
            tripStore.setStatus('completed')
            historyStore.saveTripRecord(sessionId, `${formData.value.city} ${formData.value.start_date} 行程`,
              formData.value.city, { ...formData.value }, event.data.itinerary, 'trip')
          }
          if (event.node === 'error') {
            throw new Error(event.message || '生成失败')
          }
        } catch (e: any) {
          if (e instanceof Error) throw e
        }
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      ElMessage.info('已终止规划')
      steps.value.push({ node: 'stopped', status: 'failed', message: '用户终止' })
    } else {
      ElMessage.error(error.message || '请求失败')
      tripStore.addError(error.message || '请求失败')
    }
  } finally {
    isLoading.value = false
    abortController.value = null
    if (!isStopped.value) router.push('/result')
  }
}

function handleStop() {
  isStopped.value = true
  abortController.value?.abort()
  isLoading.value = false
  currentMessage.value = '已终止'
}

function handleLogout() {
  authStore.logout()
  ElMessage.success('已退出登录')
}

loadProviders()

// 如果路由带了 ?auth=login，自动弹出登录弹窗
onMounted(() => {
  const queryAuth = route.query.auth as string | undefined
  if (queryAuth === 'login' || queryAuth === 'register') {
    authDialogVisible.value = true
    authTab.value = queryAuth === 'register' ? 'register' : 'login'
  }
})
watch(() => route.query.auth, (val) => {
  if (val === 'login' || val === 'register') {
    authDialogVisible.value = true
    authTab.value = val === 'register' ? 'register' : 'login'
  }
})
</script>

<style scoped>
.app {
  min-height: 100vh;
}

.hero {
  position: relative;
  overflow: hidden;
  padding-bottom: 132px;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.18), transparent 20%),
    linear-gradient(135deg, rgba(16, 37, 67, 0.98), rgba(26, 53, 95, 0.96) 48%, rgba(79, 95, 170, 0.88));
  color: #fff;
}

.hero::after {
  content: "";
  position: absolute;
  inset: auto 0 0;
  height: 140px;
  background: linear-gradient(180deg, rgba(17, 35, 61, 0), rgba(17, 35, 61, 0.34));
  pointer-events: none;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 34px 34px;
  opacity: 0.32;
}

.hero-inner {
  position: relative;
  z-index: 1;
  max-width: 1080px;
  margin: 0 auto;
  padding: 30px 28px 0;
}

.hero-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 46px;
}

.account-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.welcome-user {
  color: rgba(240, 244, 255, 0.92);
  font-size: 14px;
}

.ghost-btn {
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  border-radius: 999px;
  padding: 9px 16px;
  cursor: pointer;
  backdrop-filter: blur(12px);
}

.ghost-btn.primary {
  background: rgba(255, 255, 255, 0.94);
  color: var(--ra-primary);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  font-size: 22px;
  color: rgba(226, 211, 189, 0.94);
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.hero-copy {
  max-width: 780px;
}

.hero-copy h1 {
  margin: 0 0 14px;
  font-size: clamp(42px, 7vw, 72px);
  line-height: 0.98;
  letter-spacing: -0.04em;
}

.hero-copy p {
  max-width: 660px;
  color: rgba(240, 244, 255, 0.82);
  line-height: 1.9;
  font-size: 15px;
}

.mode-tabs {
  margin-top: 38px;
  display: inline-flex;
  position: relative;
  padding: 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  gap: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.mode-pill {
  position: absolute;
  top: 7px;
  left: 7px;
  width: calc(50% - 11px);
  height: calc(100% - 14px);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.2);
  transition: transform 0.25s ease;
}

.mode-pill.local {
  transform: translateX(100%);
}

.tab {
  position: relative;
  z-index: 1;
  border: none;
  background: transparent;
  color: #fff;
  padding: 11px 20px;
  border-radius: 999px;
  cursor: pointer;
  font-family: var(--ra-font-sans);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.tab.active {
  color: #fff;
}

.tab-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  background: rgba(255, 255, 255, 0.85);
}

.workspace {
  position: relative;
  z-index: 2;
  max-width: 1080px;
  margin: -86px auto 0;
  padding: 0 28px 28px;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
}

.workspace.with-panel {
  grid-template-columns: minmax(0, 1fr) 360px;
}

.form-card,
.panel {
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.72);
  box-shadow: var(--ra-shadow-lg);
  backdrop-filter: blur(18px);
}

.form-card {
  padding: 28px;
}

.form-section + .form-section {
  margin-top: 24px;
}

.section-head {
  margin-bottom: 16px;
}

.section-kicker {
  font-size: 12px;
  color: var(--ra-accent);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 700;
}

.section-head h3 {
  margin-top: 8px;
  color: var(--ra-text);
  font-size: 24px;
}

.section-copy {
  margin-top: 8px;
  max-width: 560px;
  color: var(--ra-text-soft);
  font-family: var(--ra-font-sans);
  font-size: 13px;
  line-height: 1.8;
}

.field-row,
.travel-date-row,
.transport-group,
.chips {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.travel-top-row {
  align-items: flex-start;
}

.field {
  flex: 1;
  min-width: 180px;
}

.travel-city-field {
  flex: 1.6;
}

.travel-date-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  flex: 1.6;
  min-width: 0;
}

.travel-date-row .travel-date-field {
  min-width: 0;
}

.travel-date-row :deep(.el-date-editor),
.travel-city-field :deep(.el-date-editor) {
  width: 100%;
}

.form-block {
  margin-top: 22px;
}

.form-block-large-gap {
  margin-top: 28px;
}

.form-block .transport-group,
.form-block .chips,
.form-block textarea {
  margin-top: 12px;
}

label {
  display: block;
  margin-bottom: 8px;
  color: var(--ra-text-soft);
  font-family: var(--ra-font-sans);
  font-weight: 600;
  letter-spacing: 0.01em;
}


.optional {
  color: var(--ra-text-faint);
  font-size: 12px;
}

.input-wrap {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 13px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  color: var(--ra-text-faint);
}

input,
textarea {
  width: 100%;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 18px;
  padding: 13px 15px;
  font-size: 14px;
  color: var(--ra-text);
  background: rgba(255, 255, 255, 0.78);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
}

input:focus,
textarea:focus {
  outline: none;
  border-color: rgba(24, 59, 107, 0.28);
  box-shadow: 0 0 0 4px rgba(24, 59, 107, 0.08);
}

.input-wrap input {
  padding-left: 42px;
}

textarea {
  resize: vertical;
  min-height: 110px;
  line-height: 1.8;
}

.days-badge,
.count-badge,
.budget-range em {
  color: var(--ra-primary);
  font-style: normal;
  font-weight: 700;
}

.transport-btn,
.chip {
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.82);
  color: var(--ra-text-soft);
  border-radius: 999px;
  padding: 10px 14px;
  cursor: pointer;
  font-family: var(--ra-font-display);
  font-weight: 600;
  letter-spacing: 0;
  box-shadow: 0 8px 20px rgba(18, 31, 53, 0.04);
}

.transport-btn.active,
.chip.active {
  background: linear-gradient(135deg, var(--ra-primary), #36578d 68%, var(--ra-secondary));
  color: #fff;
  border-color: transparent;
  font-weight: 600;
  box-shadow: 0 14px 26px rgba(24, 59, 107, 0.16);
}

.slider-track {
  padding-top: 8px;
}

.range-input {
  width: 100%;
}

.range-marks {
  display: flex;
  justify-content: space-between;
  color: var(--ra-text-faint);
  font-size: 12px;
  margin-top: 8px;
}

.submit-btn,
.stop-btn,
.text-link {
  border: none;
  cursor: pointer;
}

.submit-btn,
.stop-btn {
  margin-top: 24px;
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 15px 18px;
  border-radius: 20px;
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.submit-btn {
  background: linear-gradient(135deg, var(--ra-primary), #36578d 52%, var(--ra-secondary));
  box-shadow: 0 18px 28px rgba(24, 59, 107, 0.18);
}

.stop-btn {
  background: linear-gradient(135deg, #b64c55, #db6c74);
}

.submit-btn svg,
.stop-btn svg {
  width: 18px;
  height: 18px;
}

.card-footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.text-link {
  background: transparent;
  color: var(--ra-primary);
  font-weight: 600;
}

.panel {
  padding: 22px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.panel-title {
  color: var(--ra-text);
  font-weight: 700;
}

.pulse-dot,
.spinning-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--ra-primary);
}

.pulse-dot {
  box-shadow: 0 0 0 8px rgba(24, 59, 107, 0.12);
}

.spinning-dot {
  animation: pulse 1s infinite ease-in-out;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.1); }
}

.steps {
  display: grid;
  gap: 16px;
}

.step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.step:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.step-icon {
  width: 22px;
  min-width: 22px;
  display: flex;
  justify-content: center;
  color: var(--ra-primary);
}

.step-info {
  color: var(--ra-text-soft);
}

.step-name {
  color: var(--ra-text);
  font-weight: 700;
}

.step-msg {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
}

.progress-bar-wrap {
  margin-top: 18px;
  height: 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--ra-primary), var(--ra-secondary));
}

.current-msg {
  margin-top: 12px;
  color: var(--ra-text-soft);
  font-size: 13px;
  line-height: 1.7;
}

.hero :deep(.el-date-editor),
.hero :deep(.el-slider),
.hero :deep(.field-control) {
  width: 100%;
}

.hero :deep(.el-slider__runway) {
  height: 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
}

.hero :deep(.el-slider__bar) {
  background: linear-gradient(90deg, var(--ra-primary), var(--ra-secondary));
}

.hero :deep(.el-slider__button) {
  width: 16px;
  height: 16px;
  border: 3px solid #fff;
  background: var(--ra-primary);
  box-shadow: 0 8px 20px rgba(24, 59, 107, 0.18);
}

.hero :deep(.el-date-editor.el-input),
.hero :deep(.el-date-editor.el-input__wrapper),
.hero :deep(.el-date-editor .el-input__wrapper) {
  border-radius: 16px;
}

.hero :deep(.el-dialog) {
  background: rgba(251, 252, 253, 0.94);
}

.auth-tab-switch {
  display: flex;
  gap: 0;
  background: rgba(238, 242, 250, 0.95);
  border-radius: 16px;
  padding: 4px;
}

.auth-tab-switch button {
  flex: 1;
  border: none;
  background: transparent;
  padding: 11px 0;
  border-radius: 14px;
  cursor: pointer;
  color: var(--ra-text-soft);
  font-weight: 600;
  font-size: 14px;
  transition: background 0.2s ease, color 0.2s ease;
}

.auth-tab-switch button.active {
  background: #fff;
  color: var(--ra-primary);
  box-shadow: 0 8px 18px rgba(24, 59, 107, 0.08);
}

.full-btn {
  width: 100%;
}

@media (max-width: 992px) {
  .workspace.with-panel {
    grid-template-columns: 1fr;
  }

  .hero-topbar,
  .account-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 768px) {
  .hero-inner,
  .workspace {
    padding-left: 14px;
    padding-right: 14px;
  }

  .hero-copy h1 {
    font-size: 38px;
  }

  .form-card,
  .panel {
    padding: 20px;
    border-radius: 24px;
  }

  .mode-tabs {
    display: flex;
    width: 100%;
  }

  .tab {
    flex: 1;
    text-align: center;
    padding-left: 14px;
    padding-right: 14px;
  }
}
</style>
