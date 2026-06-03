<template>
  <div class="chat-page">
    <div class="page-glow page-glow-left"></div>
    <div class="page-glow page-glow-right"></div>

    <aside class="sidebar">
      <div class="sidebar-card brand-card">
        <div class="brand-row">
          <div class="brand-mark">✦</div>
          <div>
            <p class="section-label">RouteAI Workspace</p>
            <h2>对话模式</h2>
          </div>
        </div>
        <p class="brand-desc">
          像和一位懂路线、懂预算、懂节奏的旅行策划师协作一样，边聊边把行程打磨完整。
        </p>
        <div class="brand-actions">
          <el-button type="primary" class="full-button" @click="handleNewChat">
            <el-icon><Plus /></el-icon>
            新对话
          </el-button>
        </div>
      </div>

      <div class="sidebar-card session-card">
        <div class="card-head">
          <span class="section-label">会话状态</span>
          <span class="session-pill" :class="statusClass">{{ sessionStatusLabel }}</span>
        </div>

        <div class="metric-grid">
          <div class="metric-item">
            <span class="metric-label">消息数</span>
            <strong>{{ messageCount }}</strong>
          </div>
          <div class="metric-item">
            <span class="metric-label">当前模型</span>
            <strong>{{ providerLabel }}</strong>
          </div>
          <div class="metric-item">
            <span class="metric-label">行程草案</span>
            <strong>{{ hasTripPlan ? '已生成' : '未生成' }}</strong>
          </div>
          <div class="metric-item">
            <span class="metric-label">最近更新</span>
            <strong>{{ lastUpdatedText }}</strong>
          </div>
        </div>

        <div class="summary-box">
          <p class="summary-label">最近一条消息</p>
          <p class="summary-text">{{ lastMessagePreview }}</p>
        </div>
      </div>

      <div v-if="tripStore.sessionId" class="sidebar-card context-card">
        <div class="card-head">
          <span class="section-label">当前会话</span>
          <span class="session-id">{{ shortSessionId }}</span>
        </div>
        <div class="context-list">
          <div v-if="chatStore.title" class="context-item">
            <span class="context-key">标题</span>
            <span class="context-value">{{ chatStore.title }}</span>
          </div>
          <div class="context-item">
            <span class="context-key">目的地</span>
            <span class="context-value">{{ currentCity || '待确认' }}</span>
          </div>
          <div class="context-item">
            <span class="context-key">日期</span>
            <span class="context-value">{{ currentDates || '尚未生成' }}</span>
          </div>
          <div class="context-item">
            <span class="context-key">阶段</span>
            <span class="context-value">{{ hasTripPlan ? '可继续细化' : '需求收集中' }}</span>
          </div>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="sidebar-footer-actions">
          <el-button text @click="$router.push('/history')">
            <el-icon><Edit /></el-icon>
            查看历史记录
          </el-button>
          <el-button text @click="$router.push('/')">
            <el-icon><Edit /></el-icon>
            切换到表单模式
          </el-button>
        </div>
      </div>
    </aside>

    <section class="workspace">
      <header class="workspace-header">
        <div>
          <p class="section-label">智能旅行对话</p>
          <h1>{{ workspaceTitle }}</h1>
          <p v-if="!chatStore.hasMessages" class="workspace-subtitle">{{ workspaceSubtitle }}</p>
        </div>
        <div class="header-pills">
          <span class="header-pill">{{ providerLabel }}</span>
          <span class="header-pill">{{ headerStatusText }}</span>
          <span v-if="hasTripPlan" class="header-pill success">已生成结果预览</span>
        </div>
      </header>

      <div class="conversation-card">
        <div class="topbar">
          <div class="topbar-item">
            <span class="topbar-dot"></span>
            <span>{{ topbarPrimaryText }}</span>
          </div>
          <div class="topbar-item subtle">
            <span>{{ topbarSecondaryText }}</span>
          </div>
        </div>

        <div ref="messageListRef" class="message-list">
          <div v-if="!chatStore.hasMessages" class="welcome-panel">
            <div class="welcome-badge">多轮协作 · 路线规划 · 结果可继续细化</div>
            <h2>告诉我城市、时间、预算和偏好，我会先聊清楚，再给出能落地的行程建议。</h2>
            <p>
              你可以边聊边补充条件，我会持续调整路线、节奏和推荐内容。
            </p>

            <div class="welcome-examples">
              <button
                v-for="example in examples"
                :key="example"
                class="example-card"
                :disabled="chatStore.isLoading"
                @click="handleQuickCommand(example)"
              >
                {{ example }}
              </button>
            </div>

            <div class="feature-row">
              <div class="feature-chip">📍 目的地与交通建议</div>
              <div class="feature-chip">🗺️ 路线顺序持续优化</div>
              <div class="feature-chip">🍜 景点、餐饮、节奏联动规划</div>
            </div>
          </div>

          <div
            v-for="(msg, index) in chatStore.messages"
            :key="index"
            :class="['message-row', msg.role]"
          >
            <div class="message-avatar">
              <el-avatar v-if="msg.role === 'user'" :size="42" class="avatar-user">
                <el-icon><User /></el-icon>
              </el-avatar>
              <el-avatar v-else :size="42" class="avatar-assistant">
                <el-icon><Service /></el-icon>
              </el-avatar>
            </div>

            <div class="message-body">
              <div class="message-meta">
                <span class="message-role">{{ msg.role === 'user' ? '你' : '旅行助手' }}</span>
                <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="message-bubble" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>

          <div v-if="chatStore.isLoading" class="message-row assistant loading-row">
            <div class="message-avatar">
              <el-avatar :size="42" class="avatar-assistant">
                <el-icon><Service /></el-icon>
              </el-avatar>
            </div>
            <div class="message-body">
              <div class="message-meta">
                <span class="message-role">旅行助手</span>
                <span class="message-time">正在生成</span>
              </div>
              <div class="message-bubble loading-bubble">
                <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <p>正在整理你的需求、路线与建议…</p>
              </div>
            </div>
          </div>
        </div>

        <div class="composer-card">
          <div class="composer-head">
            <div>
              <p class="section-label">输入需求</p>
              <p class="composer-desc">可以直接描述城市、天数、预算和偏好，也可以先从快捷指令开始。</p>
            </div>
            <div class="llm-selector">
              <el-radio-group v-model="llmProvider" size="small">
                <el-radio-button label="deepseek">DeepSeek</el-radio-button>
                <el-radio-button label="aliyun">阿里云百炼</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="composer-body">
            <el-input
              v-model="inputMessage"
              class="composer-input"
              type="textarea"
              resize="none"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :disabled="chatStore.isLoading"
              placeholder="例如：帮我规划一个武汉一日游路线，想吃热干面、不想排队，预算 300 以内。"
              @keydown.enter.ctrl.prevent="handleSend"
            />

            <el-button
              type="primary"
              class="send-button"
              :disabled="!inputMessage.trim() || chatStore.isLoading"
              @click="handleSend"
            >
              <el-icon><Promotion /></el-icon>
              {{ chatStore.isLoading ? '生成中' : '发送' }}
            </el-button>
          </div>

          <div class="composer-footer">
            <span>Ctrl + Enter 快速发送</span>
            <span>{{ composerHint }}</span>
          </div>
        </div>
      </div>
    </section>

    <el-drawer
      v-model="showTripDrawer"
      class="trip-drawer"
      direction="rtl"
      size="42%"
    >
      <template #header>
        <div class="drawer-header">
          <div>
            <p class="section-label">行程草案</p>
            <h3>{{ tripStore.tripPlan?.city || '行程预览' }}</h3>
          </div>
          <span class="drawer-badge">{{ tripDaysLabel }}</span>
        </div>
      </template>

      <div v-if="tripStore.tripPlan" class="trip-preview">
        <div class="preview-hero">
          <p class="preview-kicker">已根据当前对话生成草案</p>
          <h4>你可以继续在对话里补充要求，也可以直接查看完整结果。</h4>
          <p class="preview-desc">
            {{ previewSuggestionText }}
          </p>
        </div>

        <div class="preview-grid">
          <div class="preview-card">
            <span class="preview-label">目的地</span>
            <strong>{{ tripStore.tripPlan.city }}</strong>
          </div>
          <div class="preview-card">
            <span class="preview-label">日期</span>
            <strong>{{ currentDates || '未设置' }}</strong>
          </div>
          <div class="preview-card">
            <span class="preview-label">行程天数</span>
            <strong>{{ tripDaysLabel }}</strong>
          </div>
          <div class="preview-card">
            <span class="preview-label">当前状态</span>
            <strong>可继续细化</strong>
          </div>
        </div>

        <div class="preview-section">
          <div class="preview-section-head">
            <span class="section-label">亮点概览</span>
          </div>
          <ul class="preview-points">
            <li>已生成 {{ tripStore.tripPlan.days?.length || 0 }} 天行程框架</li>
            <li>可继续追问预算、节奏、景点替换或路线优化</li>
            <li>支持跳转结果页查看更完整的地图与每日安排</li>
          </ul>
        </div>

        <el-button type="primary" class="full-button" @click="handleViewDetail">
          查看完整行程 →
        </el-button>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Plus, Edit, User, Service, Promotion
} from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { useTripStore } from '@/stores/trip'
import { useHistoryStore } from '@/stores/history'
import { sendChatMessage } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const chatStore = useChatStore()
const tripStore = useTripStore()
const authStore = useAuthStore()
const historyStore = useHistoryStore()

const inputMessage = ref('')
const llmProvider = ref<'deepseek' | 'aliyun'>('deepseek')
const messageListRef = ref<HTMLElement>()
const showTripDrawer = ref(false)

const providerTextMap: Record<'deepseek' | 'aliyun', string> = {
  deepseek: 'DeepSeek',
  aliyun: '阿里云百炼'
}

// 快捷指令
const quickCommands = [
  { label: '📍 本地路线', text: '帮我规划一个武汉一日游路线，想吃热干面不排队' },
  { label: '🏛️ 历史文化', text: '我对历史文化景点感兴趣' },
  { label: '🍜 美食之旅', text: '帮我规划一个美食之旅' },
  { label: '⏰ 高效路线', text: '帮我规划一个不走冤枉路的路线' }
]

// 示例对话
const examples = [
  '帮我规划一个武汉一日游路线，偏好美食历史文化，预算300以内',
  '我想去北京玩一天，想看故宫和吃烤鸭，怎么安排路线最合理',
  '上海周末一日游，不想排队，预算500元',
  '杭州西湖一日游，自驾出行'
]

const hasTripPlan = computed(() => !!tripStore.tripPlan)
const messageCount = computed(() => chatStore.messages.length)
const providerLabel = computed(() => providerTextMap[llmProvider.value])
const currentCity = computed(() => tripStore.tripPlan?.city || '')
const currentDates = computed(() => {
  if (tripStore.tripPlan?.start_date && tripStore.tripPlan?.end_date) {
    return `${tripStore.tripPlan.start_date} ~ ${tripStore.tripPlan.end_date}`
  }
  return ''
})
const tripDaysLabel = computed(() => `${tripStore.tripPlan?.days?.length || 0} 天`)
const shortSessionId = computed(() => {
  if (!tripStore.sessionId) return '--'
  return tripStore.sessionId.length > 12
    ? `${tripStore.sessionId.slice(0, 6)}...${tripStore.sessionId.slice(-4)}`
    : tripStore.sessionId
})
const lastMessage = computed(() => chatStore.messages[chatStore.messages.length - 1])
const lastMessagePreview = computed(() => {
  if (!lastMessage.value?.content) return '还没有消息，先从一个旅行目标开始吧。'
  const normalized = lastMessage.value.content.replace(/\s+/g, ' ').trim()
  return normalized.length > 42 ? `${normalized.slice(0, 42)}…` : normalized
})
const lastUpdatedText = computed(() => {
  if (!lastMessage.value?.timestamp) return '暂无'
  return formatTime(lastMessage.value.timestamp)
})
const sessionStatusLabel = computed(() => {
  if (chatStore.isLoading) return '生成中'
  if (hasTripPlan.value) return '草案已生成'
  if (chatStore.hasMessages) return '对话进行中'
  return '待开始'
})
const statusClass = computed(() => {
  if (chatStore.isLoading) return 'is-loading'
  if (hasTripPlan.value) return 'is-success'
  if (chatStore.hasMessages) return 'is-active'
  return 'is-idle'
})
const workspaceTitle = computed(() => currentCity.value
  ? `一起打磨你的 ${currentCity.value} 行程`
  : chatStore.hasMessages
    ? '继续细化你的旅行需求'
    : '把旅行需求聊清楚，再生成更靠谱的行程')
const workspaceSubtitle = computed(() => {
  if (currentDates.value) {
    return `当前已经形成 ${currentDates.value} 的行程上下文，你可以继续细化预算、景点和路线偏好。`
  }
  return '从一句自然语言开始，逐步补充城市、时间、预算与偏好，让行程更贴近真实出行。'
})
const headerStatusText = computed(() => {
  if (chatStore.isLoading) return 'AI 正在整理建议'
  if (hasTripPlan.value) return '已生成可继续细化的草案'
  return '准备就绪，可直接开始提问'
})
const topbarPrimaryText = computed(() => {
  if (chatStore.isLoading) return '正在结合当前上下文生成回复与路线建议'
  if (hasTripPlan.value) return '已生成行程草案，可继续在对话中追加要求'
  return '先聊天明确需求，再生成结果会更准确'
})
const topbarSecondaryText = computed(() => {
  if (tripStore.sessionId) return `会话 ID：${shortSessionId.value}`
  return '尚未开始会话'
})
const composerHint = computed(() => chatStore.isLoading
  ? '助手生成中，请稍候。'
  : hasTripPlan.value
    ? '可以继续追问“换个景点”“压缩预算”“调整顺序”等。'
    : '建议一次说清城市、时长、预算和偏好。')
const previewSuggestionText = computed(() => {
  const suggestion = tripStore.tripPlan?.overall_suggestions?.trim()
  if (!suggestion) return '如果你想更省钱、更轻松、少排队或更偏美食/历史，可以继续在对话中补充要求。'
  return suggestion.length > 120 ? `${suggestion.slice(0, 120)}…` : suggestion
})

// 渲染Markdown
function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

// 格式化时间
function formatTime(date: Date): string {
  return new Date(date).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 发送消息
async function handleSend() {
  const message = inputMessage.value.trim()
  if (!message || chatStore.isLoading) return

  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录后再发起对话')
    router.push('/?auth=login')
    return
  }

  inputMessage.value = ''
  chatStore.addMessage('user', message)
  chatStore.setLoading(true)
  scrollToBottom()

  try {
    if (!chatStore.sessionId) {
      const sessionId = `chat_${Date.now()}`
      chatStore.setSessionId(sessionId)
      tripStore.setSessionId(sessionId)
      // 新建会话时写入 Supabase
      historyStore.upsertChatSession(sessionId, message.slice(0, 30))
    }

    const response = await sendChatMessage({
      session_id: chatStore.sessionId,
      message,
      llm_provider: llmProvider.value
    })

    chatStore.addMessage('assistant', response.response)
    scrollToBottom()

    // 保存消息到 Supabase
    historyStore.insertChatMessage(chatStore.sessionId, 'user', message)
    historyStore.insertChatMessage(chatStore.sessionId, 'assistant', response.response)

    if (response.trip_plan) {
      tripStore.setTripPlan(response.trip_plan as any)
      showTripDrawer.value = true
    }
  } catch (error: any) {
    ElMessage.error(error.message || '发送失败')
    chatStore.addMessage('assistant', '抱歉，我遇到了一些问题，请稍后再试。')
  } finally {
    chatStore.setLoading(false)
  }
}

// 快捷指令
function handleQuickCommand(text: string) {
  inputMessage.value = text
  handleSend()
}

// 新对话
function handleNewChat() {
  chatStore.reset()
  tripStore.reset()
  showTripDrawer.value = false
  ElMessage.success('已开始新对话')
}

// 查看详情
function handleViewDetail() {
  showTripDrawer.value = false
  router.push('/result')
}

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-page {
  position: relative;
  display: grid;
  grid-template-columns: 260px minmax(0, 920px);
  justify-content: center;
  min-height: 100vh;
  padding: 18px;
  gap: 18px;
  overflow: hidden;
}

.page-glow {
  position: absolute;
  width: 440px;
  height: 440px;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.24;
  pointer-events: none;
}

.page-glow-left {
  top: -140px;
  left: -100px;
  background: rgba(24, 59, 107, 0.42);
}

.page-glow-right {
  right: -140px;
  bottom: -180px;
  background: rgba(182, 146, 103, 0.28);
}

.sidebar,
.workspace {
  position: relative;
  z-index: 1;
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}

.sidebar-card,
.conversation-card {
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow: var(--ra-shadow-lg);
  backdrop-filter: blur(16px);
}

.sidebar-card {
  background: rgba(255, 255, 255, 0.72);
  border-radius: 24px;
  padding: 16px;
}

.brand-card {
  background: linear-gradient(180deg, rgba(16, 37, 67, 0.98), rgba(22, 47, 84, 0.96) 54%, rgba(73, 89, 164, 0.88));
  color: #fff;
  border-color: rgba(255, 255, 255, 0.08);
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  color: rgba(255, 249, 241, 0.96);
  background: rgba(255, 255, 255, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.brand-card h2 {
  margin: 2px 0 0;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
}

.brand-desc {
  margin: 14px 0 16px;
  color: rgba(234, 239, 248, 0.88);
  line-height: 1.75;
  font-size: 13px;
}

.section-label {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ra-text-faint);
}

.brand-card .section-label {
  color: rgba(226, 211, 189, 0.88);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.session-pill,
.header-pill,
.drawer-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
}

.session-pill {
  background: rgba(24, 59, 107, 0.08);
  color: var(--ra-primary);
}

.session-pill.is-loading {
  background: rgba(92, 116, 214, 0.14);
  color: #4862cc;
}

.session-pill.is-success {
  background: rgba(30, 143, 102, 0.12);
  color: var(--ra-success);
}

.session-pill.is-active {
  background: rgba(182, 146, 103, 0.12);
  color: #9f7b55;
}

.session-pill.is-idle {
  background: rgba(125, 137, 161, 0.14);
  color: #6c778f;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-item {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(244, 247, 251, 0.88));
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 18px;
  padding: 12px;
}

.metric-label,
.summary-label,
.context-key,
.preview-label,
.subtle-text {
  color: var(--ra-text-faint);
  font-size: 12px;
}

.metric-item strong,
.context-value,
.preview-card strong {
  display: block;
  margin-top: 8px;
  color: var(--ra-text);
  font-size: 15px;
}

.summary-box {
  margin-top: 12px;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(245, 247, 251, 0.9));
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.summary-text {
  margin-top: 8px;
  line-height: 1.7;
  color: var(--ra-text-soft);
  font-size: 13px;
}

.session-id {
  font-size: 12px;
  color: var(--ra-text-faint);
}

.context-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.context-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.context-item:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.context-value {
  margin-top: 0;
  text-align: right;
}

.quick-list {
  display: grid;
  gap: 10px;
}

.quick-command {
  width: 100%;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(245, 247, 251, 0.92));
  border-radius: 20px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}

.quick-command:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 18px 28px rgba(18, 31, 53, 0.08);
  border-color: rgba(24, 59, 107, 0.14);
}

.quick-command:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.quick-label {
  display: block;
  color: var(--ra-text);
  font-weight: 700;
  margin-bottom: 6px;
}

.quick-text {
  display: block;
  color: var(--ra-text-soft);
  font-size: 13px;
  line-height: 1.6;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  justify-content: center;
}

.sidebar-footer-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.workspace {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.workspace-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.workspace-header h1 {
  margin: 4px 0 0;
  color: var(--ra-text);
  font-size: clamp(28px, 4vw, 36px);
  line-height: 1.1;
}

.workspace-subtitle {
  max-width: 820px;
  margin-top: 8px;
  color: var(--ra-text-soft);
  line-height: 1.7;
  font-size: 13px;
}

.header-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.header-pill {
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(15, 23, 42, 0.06);
  color: var(--ra-text-soft);
}

.header-pill.success {
  background: rgba(30, 143, 102, 0.1);
  border-color: rgba(30, 143, 102, 0.16);
  color: var(--ra-success);
}

.conversation-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.72);
  overflow: hidden;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(247, 249, 252, 0.78));
}

.topbar-item {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ra-text);
  font-size: 13px;
  font-weight: 600;
}

.topbar-item.subtle {
  color: var(--ra-text-faint);
  font-weight: 500;
}

.topbar-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--ra-primary), var(--ra-secondary));
  box-shadow: 0 0 0 6px rgba(24, 59, 107, 0.1);
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 18px 12px;
}

.welcome-panel {
  max-width: 900px;
  margin: 0 auto;
  padding: 26px;
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.14), transparent 24%),
    linear-gradient(135deg, rgba(16, 37, 67, 0.98), rgba(24, 52, 90, 0.96) 54%, rgba(84, 100, 181, 0.88));
  color: #fff;
  box-shadow: 0 22px 44px rgba(24, 38, 67, 0.18);
}

.welcome-badge {
  display: inline-flex;
  align-items: center;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.88);
  font-size: 11px;
  margin-bottom: 14px;
}

.welcome-panel h2 {
  max-width: 760px;
  font-size: clamp(24px, 4vw, 34px);
  line-height: 1.18;
  margin-bottom: 12px;
}

.welcome-panel p {
  max-width: 760px;
  color: rgba(240, 244, 255, 0.84);
  line-height: 1.8;
  font-size: 13px;
}

.welcome-examples {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.example-card {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  border-radius: 18px;
  padding: 13px 14px;
  text-align: left;
  line-height: 1.6;
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.24s ease, background 0.24s ease, border-color 0.24s ease;
}

.example-card:hover:not(:disabled) {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.14);
  border-color: rgba(255, 255, 255, 0.24);
}

.example-card:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.feature-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.feature-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
}

.message-row {
  display: flex;
  gap: 12px;
  max-width: 960px;
  margin-bottom: 18px;
}

.message-row.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar-user {
  background: linear-gradient(135deg, var(--ra-primary), #36578d);
  color: #fff;
  box-shadow: 0 12px 24px rgba(24, 59, 107, 0.2);
}

.avatar-assistant {
  background: linear-gradient(135deg, #173a68, #6d64c9);
  color: #fff;
  box-shadow: 0 12px 24px rgba(49, 66, 144, 0.2);
}

.message-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: min(740px, 100%);
}

.message-row.user .message-body {
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ra-text-faint);
  font-size: 12px;
}

.message-role {
  color: var(--ra-text);
  font-weight: 700;
}

.message-bubble {
  padding: 14px 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 14px 24px rgba(18, 31, 53, 0.06);
  color: var(--ra-text-soft);
  line-height: 1.8;
  word-break: break-word;
}

.message-row.user .message-bubble {
  background: linear-gradient(135deg, var(--ra-primary), #274b80 58%, var(--ra-secondary));
  border-color: transparent;
  color: #fff;
  box-shadow: 0 16px 28px rgba(24, 59, 107, 0.18);
}

.message-bubble :deep(code) {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(35, 53, 97, 0.08);
  font-size: 0.92em;
}

.message-row.user .message-bubble :deep(code) {
  background: rgba(255, 255, 255, 0.16);
}

.loading-row .message-bubble {
  display: flex;
  align-items: center;
  gap: 14px;
}

.loading-bubble p {
  color: var(--ra-text-soft);
}

.typing-indicator {
  display: flex;
  gap: 6px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--ra-primary);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-8px);
    opacity: 1;
  }
}

.composer-card {
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  padding: 14px 18px 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(246, 248, 251, 0.8));
}

.composer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.composer-desc {
  margin-top: 4px;
  color: var(--ra-text-soft);
  font-size: 12px;
}

.composer-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: flex-end;
}

.composer-input :deep(.el-textarea__inner) {
  border-radius: 18px;
  padding: 13px 14px;
  line-height: 1.7;
}

.send-button {
  min-width: 108px;
  height: 50px;
  border-radius: 16px;
  font-weight: 700;
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
  color: var(--ra-text-faint);
  font-size: 12px;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}

.drawer-header h3 {
  margin-top: 6px;
  color: var(--ra-text);
  font-size: 24px;
}

.drawer-badge {
  background: rgba(24, 59, 107, 0.08);
  color: var(--ra-primary);
}

.trip-preview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.preview-hero {
  padding: 22px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(16, 37, 67, 0.98), rgba(26, 53, 95, 0.96) 58%, rgba(79, 95, 170, 0.88));
  color: #fff;
}

.preview-kicker {
  color: rgba(226, 211, 189, 0.88);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.preview-hero h4 {
  margin: 10px 0 12px;
  font-size: 22px;
  line-height: 1.45;
}

.preview-desc {
  color: rgba(238, 243, 255, 0.9);
  line-height: 1.8;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.preview-card,
.preview-section {
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.preview-card {
  padding: 16px;
}

.preview-section {
  padding: 18px;
}

.preview-points {
  margin: 12px 0 0 18px;
  color: var(--ra-text-soft);
  line-height: 1.9;
}

.full-button {
  width: 100%;
}

:deep(.trip-drawer .el-drawer) {
  background: rgba(248, 250, 252, 0.92);
}

:deep(.trip-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 24px 24px 8px;
}

:deep(.trip-drawer .el-drawer__body) {
  padding: 20px 24px 24px;
}

@media (max-width: 1280px) {
  .chat-page {
    grid-template-columns: 260px minmax(0, 1fr);
  }
}

@media (max-width: 1024px) {
  .chat-page {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .sidebar {
    order: 2;
  }

  .workspace {
    order: 1;
  }

  .workspace-header,
  .composer-head,
  .topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-pills {
    justify-content: flex-start;
  }

  :deep(.trip-drawer .el-drawer) {
    width: min(92vw, 560px) !important;
  }
}

@media (max-width: 768px) {
  .chat-page {
    padding: 12px;
    gap: 14px;
  }

  .sidebar-card,
  .conversation-card {
    border-radius: 24px;
  }

  .workspace-header h1 {
    font-size: 24px;
  }

  .welcome-panel {
    padding: 22px;
  }

  .welcome-panel h2 {
    font-size: 22px;
  }

  .welcome-examples,
  .preview-grid,
  .metric-grid,
  .composer-body {
    grid-template-columns: 1fr;
  }

  .message-list {
    padding: 16px 14px 10px;
  }

  .composer-card {
    padding: 16px;
  }

  .message-row {
    gap: 10px;
  }

  .message-bubble {
    border-radius: 18px;
    padding: 14px 16px;
  }

  .composer-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
