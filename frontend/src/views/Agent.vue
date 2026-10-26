<template>
  <div class="agent-page">
    <header class="topbar">
      <RouterLink to="/" class="brand"><span>◈</span> RouteAI <small>旅行工作台</small></RouterLink>
      <RouterLink to="/classic" class="back-link">打开经典版 <span>↗</span></RouterLink>
    </header>

    <section class="intro">
      <div>
        <p class="eyebrow">A LITTLE LESS GUESSWORK. A BETTER DAY OUT.</p>
        <h1>把一天，安排得刚刚好。</h1>
        <p class="intro-copy">查找有来源的地点，核对时间与预算。最后一步，交给你确认。</p>
      </div>
      <div class="intro-steps"><span>01 查找地点</span><i>→</i><span>02 核对约束</span><i>→</i><span>03 由你确认</span></div>
    </section>

    <div v-if="error" class="notice error" role="alert"><span>{{ error }}</span><button type="button" @click="error = ''" aria-label="关闭提示">×</button></div>
    <div v-if="savedRun" class="recovery-bar">
      <span><span class="saved-dot"></span>{{ snapshot ? '本次进度已保存，刷新后可继续。' : '发现一份已保存的规划，可以继续查看或审阅。' }}</span>
      <button type="button" :disabled="busy || restoring" @click="restoreRun(savedRun)">{{ restoring ? '恢复中…' : '恢复记录' }} ↻</button>
    </div>

    <main class="workspace">
      <aside class="brief-panel panel">
        <div class="panel-title"><span class="step-number">01</span><h2>你想怎么出发</h2></div>
        <div class="mode-picker" role="group" aria-label="运行模式">
          <button :class="{ selected: mode === 'demo' }" :disabled="busy" @click="mode = 'demo'" type="button">示例体验</button>
          <button :class="{ selected: mode === 'live' }" :disabled="busy" @click="mode = 'live'" type="button">实时规划</button>
        </div>
        <p class="mode-note" v-if="mode === 'demo'">武汉固定示例数据，不调用真实模型或高德。可体验补充需求、审阅与恢复。</p>
        <p class="mode-note" v-else>调用服务端已配置的模型与高德检索，数据来源会逐项标注。</p>

        <form @submit.prevent="startRun">
          <fieldset :disabled="busy">
            <label class="field"><span>目的地 <small>留空可体验主动澄清</small></span><input v-model="form.city" maxlength="80" placeholder="例如：武汉" /></label>
            <label class="field"><span>游玩日期</span><input v-model="form.date" type="date" /></label>
            <div class="two-fields">
              <label class="field"><span>开始时间</span><input v-model="form.start_time" type="time" required /></label>
              <label class="field"><span>结束时间</span><input v-model="form.end_time" type="time" required /></label>
            </div>
            <div class="two-fields">
              <label class="field"><span>预算上限 / 人</span><div class="money-input"><span>¥</span><input v-model="form.budget_max" type="number" min="0" max="100000" step="1" placeholder="可先留空" /></div></label>
              <label class="field"><span>最多去几处</span><select v-model.number="form.max_pois"><option v-for="n in 6" :key="n" :value="n">{{ n }} 个地点</option></select></label>
            </div>
            <label class="field"><span>出行方式</span><select v-model="form.transportation"><option value="walking">步行慢逛</option><option value="transit">公共交通</option><option value="driving">自驾出行</option></select></label>
            <div class="field"><span>这次想体验 <small>最多选 4 项</small></span><div class="preference-chips"><button v-for="preference in preferences" :key="preference" type="button" :aria-pressed="form.preferences.includes(preference)" :class="{ active: form.preferences.includes(preference) }" @click="togglePreference(preference)">{{ preference }}</button></div></div>
            <label class="field"><span>还有什么要考虑</span><textarea v-model="form.notes" rows="3" maxlength="2000" placeholder="例如：想看老建筑，安排松一点" /></label>
            <label v-if="mode === 'live'" class="field"><span>模型服务</span><select v-model="provider"><option value="deepseek">DeepSeek</option><option value="aliyun">阿里云百炼</option><option value="openai">OpenAI</option></select></label>
            <button class="primary-button start-button" type="submit" :disabled="busy || restoring"><span v-if="busy" class="spinner"></span>{{ busy ? '正在处理…' : snapshot ? '新建一份规划' : '开始安排这一天' }}<span v-if="!busy">↗</span></button>
          </fieldset>
        </form>
        <p class="auth-note">正式环境需登录。免登录示例仅在服务端开启本地演示时可用。<RouterLink :to="{ path: '/classic', query: { auth: 'login', redirect: '/agent' } }">去登录 →</RouterLink></p>
      </aside>

      <div class="results-column" aria-live="polite" aria-atomic="false">
        <section v-if="!snapshot && events.length === 0" class="welcome-panel panel">
          <div class="map-art" aria-hidden="true"><div class="map-line"></div><span class="map-point point-a">01</span><span class="map-point point-b">02</span><span class="map-point point-c">03</span><span class="map-caption">YOUR NEXT GOOD DAY</span></div>
          <div class="welcome-copy"><span class="tag">从武汉的一天开始</span><h2>好行程，不只是一段回答。</h2><p>地点来源、路线和估算约束逐项展示。你可以补充条件、要求重排，也可以回来继续上次的进度。</p><div class="welcome-features"><span>有来源的推荐</span><span>可检查的预算</span><span>可继续的规划</span></div></div>
        </section>

        <section v-if="activeInterrupt?.payload.kind === 'clarify'" class="decision-panel clarify-panel panel">
          <span class="tag">需要你补充</span><h2>再确认几个小细节</h2>
          <p>请在需求栏补充{{ missingLabel }}，然后继续当前规划。</p>
          <div class="decision-actions"><button class="primary-button" :disabled="busy || restoring" @click="review('clarify')">{{ busy ? '正在继续…' : '补充好了，继续规划' }} →</button></div>
        </section>

        <section v-if="draft" class="itinerary-panel panel">
          <div class="section-heading"><div><p class="eyebrow">YOUR DAY, AT A GLANCE</p><h2>{{ snapshot?.brief?.city || form.city }} · 一日提案</h2></div><span class="tag" :class="draftStatus.tone">{{ draftStatus.label }}</span></div>
          <p v-if="draft.summary" class="plan-summary">{{ draft.summary }}</p>
          <div class="plan-totals"><div><small>预计总时长</small><strong>{{ durationLabel }}</strong></div><div><small>预计支出 / 人</small><strong>{{ costLabel }}</strong></div><div><small>推荐地点</small><strong>{{ stops.length }}<em> 处</em></strong></div></div>
          <ol class="itinerary-list"><li v-for="(stop, index) in stops" :key="`${stop.poi_id}-${index}`"><span class="stop-index">{{ String(index + 1).padStart(2, '0') }}</span><div class="stop-content"><div class="stop-heading"><h3>{{ poiFor(stop.poi_id).name || stop.poi_id }}</h3><span class="source-badge" :class="String(poiFor(stop.poi_id).source)">{{ sourceLabel(poiFor(stop.poi_id).source) }}</span></div><p v-if="poiFor(stop.poi_id).address" class="stop-address">{{ poiFor(stop.poi_id).address }}</p><p v-if="stop.reason">{{ stop.reason }}</p><div class="stop-meta"><span>停留 {{ stop.visit_minutes }} 分钟</span><span v-if="poiFor(stop.poi_id).source === 'amap' && poiFor(stop.poi_id).estimated_ticket_cost === 0">票价待核实</span><span v-else-if="isNumber(poiFor(stop.poi_id).estimated_ticket_cost)">门票估算 ¥{{ poiFor(stop.poi_id).estimated_ticket_cost }}</span></div><div v-if="segments[index]" class="transfer-note">↓ 下一站约 {{ segments[index].duration_minutes }} 分钟 · {{ distanceLabel(segments[index].distance_meters) }} <span>{{ sourceLabel(segments[index].source, true) }}</span></div></div></li></ol>
          <ul v-if="caveats.length" class="plain-notes"><li v-for="(caveat, index) in caveats" :key="index">{{ caveat }}</li></ul>
        </section>

        <section v-if="validation" class="validation-panel panel">
          <div class="section-heading"><div><p class="eyebrow">A REALITY CHECK</p><h2>时间与预算核对</h2></div><span class="validation-result" :class="{ passed: validation.feasible }">{{ validation.feasible ? '估算范围内通过' : '尚需调整' }}</span></div>
          <p class="validation-copy">核对地点引用、停留与路途时长、预算上限；估算项保留来源标识。</p>
          <ul v-if="violations.length" class="check-messages violation"><li v-for="(item, index) in violations" :key="index">! {{ item }}</li></ul>
          <p v-else-if="validation.feasible" class="passed-copy">✓ 按现有估算，当前提案满足已检查的时间、预算与地点引用要求。</p>
          <ul v-if="warnings.length" class="check-messages"><li v-for="(item, index) in warnings" :key="index">{{ item }}</li></ul>
        </section>

        <section v-if="activeInterrupt?.payload.kind === 'review'" class="decision-panel review-panel panel">
          <span class="tag">最后一步，由你决定</span><h2>这一天，就这样出发？</h2><p>满意就确认。想换个节奏，在需求栏修改要求后点击「按新要求重排」。</p>
          <div class="decision-actions"><button class="primary-button" :disabled="busy || restoring || validation?.feasible === false" @click="review('approve')">确认这份行程 ✓</button><button class="secondary-button" :disabled="busy || restoring" @click="review('revise')">按新要求重排 ↻</button><button class="text-button" :disabled="busy || restoring" @click="review('reject')">结束规划</button></div>
        </section>

        <section v-if="events.length || snapshot" class="progress-panel panel">
          <div class="section-heading"><div><p class="eyebrow">PLANNING PROGRESS</p><h2>{{ draft ? '这份行程，如何形成' : '这一刻，正在做什么' }}</h2></div><span class="status-badge" :class="status">{{ statusLabel }}</span></div>
          <div v-if="snapshot?.run_id" class="run-info"><span>记录 {{ snapshot.run_id.slice(0, 12) }}</span><span>{{ snapshot.mode === 'demo' ? '示例数据 · 未调用真实模型' : '实时规划' }}</span></div>
          <details class="trace-details">
            <summary><span class="trace-summary-copy"><span class="trace-label">{{ status === 'running' ? '当前阶段' : '执行概览' }}</span><strong>{{ currentStageLabel }}</strong></span><span class="trace-summary-more"><span>{{ visibleEvents.length }} 条记录</span><i aria-hidden="true"></i></span></summary>
            <ol class="event-list"><li v-for="event in visibleEvents" :key="`${event.seq}-${event.type}`" :class="{ current: activeNodeStarts.has(event.seq), problem: event.type === 'error' }"><span class="event-mark">{{ activeNodeStarts.has(event.seq) ? '◌' : event.type === 'node_start' ? '·' : event.type === 'error' ? '!' : '✓' }}</span><div><strong>{{ eventLabel(event) }}</strong><p v-if="eventDetails(event)">{{ eventDetails(event) }}</p></div><span class="event-seq">{{ String(event.seq).padStart(2, '0') }}</span></li></ol>
          </details>
          <p v-if="busy" class="progress-note"><span class="spinner"></span>处理完成后会自动保存进度。</p>
          <p v-if="snapshot?.status === 'failed' || snapshot?.status === 'rejected'" class="progress-note">{{ snapshot.message || (snapshot.status === 'rejected' ? '这份规划已结束。你可以调整要求，开启新规划。' : '本次规划未完成，请查看执行记录后重试。') }}</p>
        </section>

        <section v-if="pois.length" class="evidence-panel panel">
          <div class="section-heading"><div><p class="eyebrow">BEHIND THE RECOMMENDATIONS</p><h2>查到了哪些地点</h2></div><span class="subtle-label">{{ pois.length }} 个去重候选</span></div>
          <div class="poi-grid"><article v-for="poi in pois" :key="String(poi.id)" class="poi-card"><div class="stop-heading"><h3>{{ poi.name }}</h3><span class="source-badge" :class="String(poi.source)">{{ sourceLabel(poi.source) }}</span></div><p>{{ poi.address || '未提供地址' }}</p><div class="poi-footer"><span>{{ fetchedLabel(poi.fetched_at) }}</span><a v-if="safeSourceUrl(poi.source_url)" :href="safeSourceUrl(poi.source_url)" target="_blank" rel="noopener noreferrer">查看来源 ↗</a></div></article></div>
          <ul v-if="diagnostics.length" class="plain-notes"><li v-for="(diagnostic, index) in diagnostics" :key="index">{{ diagnostic }}</li></ul>
        </section>

        <section v-if="metricItems.length" class="metrics-panel panel"><div class="section-heading"><div><p class="eyebrow">RUN RECORD</p><h2>本次执行记录</h2></div><span class="subtle-label">来自实际运行</span></div><div class="metric-grid"><div v-for="metric in metricItems" :key="metric.label"><small>{{ metric.label }}</small><strong>{{ metric.value }}<em>{{ metric.unit }}</em></strong></div></div><p v-if="snapshot?.mode === 'demo'" class="mode-note">示例模式的模型调用数为 0；耗时与调用记录仅代表本次示例执行。</p></section>
      </div>
    </main>
    <footer>RouteAI <span>·</span> 从有依据的推荐，到你认可的行程。</footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getAgentRun, resumeAgentRun, startAgentRun } from '@/services/agent'
import type { AgentBrief, AgentEvent, AgentInterrupt, AgentMode, AgentProvider, AgentSnapshot, ReviewAction } from '@/services/agent'

const storageKey = 'routeai.agent.last-run'
const nextDay = new Date()
nextDay.setDate(nextDay.getDate() + 1)
const localDate = `${nextDay.getFullYear()}-${String(nextDay.getMonth() + 1).padStart(2, '0')}-${String(nextDay.getDate()).padStart(2, '0')}`
const form = reactive({ city: '武汉', date: localDate, start_time: '09:00', end_time: '18:00', budget_max: 300 as number | string | null, max_pois: 3, preferences: ['人文历史', '城市漫步'], transportation: 'walking' as AgentBrief['transportation'], notes: '' })
const preferences = ['人文历史', '城市漫步', '自然风光', '当地美食', '艺术展馆', '亲子友好']
const mode = ref<AgentMode>('demo')
const provider = ref<AgentProvider>('deepseek')
const snapshot = ref<AgentSnapshot | null>(null)
const events = ref<AgentEvent[]>([])
const pendingInterrupt = ref<AgentInterrupt | null>(null)
const busy = ref(false)
const restoring = ref(false)
const error = ref('')
const runId = ref('')
const savedRun = ref('')
let refreshTimer: ReturnType<typeof setTimeout> | undefined
let unmounted = false

type JsonObject = Record<string, unknown>
function object(value: unknown): JsonObject { return value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : {} }
function list(value: unknown): JsonObject[] { return Array.isArray(value) ? value.map(object) : [] }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.map(String) : [] }
function isNumber(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) }
const activeInterrupt = computed(() => snapshot.value?.interrupt || pendingInterrupt.value)
const draft = computed(() => snapshot.value?.draft || activeInterrupt.value?.payload.draft || null)
const validation = computed(() => snapshot.value?.validation || activeInterrupt.value?.payload.validation || null)
const stops = computed(() => list(draft.value?.stops))
const segments = computed(() => list(object(snapshot.value?.route).segments))
const research = computed(() => list(snapshot.value?.research_results))
const pois = computed(() => {
  const all = Array.isArray(snapshot.value?.pois) ? list(snapshot.value?.pois) : research.value.flatMap(item => list(item.pois))
  return [...new Map(all.map(poi => [String(poi.id), poi])).values()]
})
const diagnostics = computed(() => research.value.flatMap(item => strings(item.diagnostics)))
const caveats = computed(() => strings(draft.value?.caveats))
const violations = computed(() => strings(validation.value?.violations))
const warnings = computed(() => [...new Set([...strings(validation.value?.warnings), ...strings(object(snapshot.value?.route).warnings)])])
const status = computed(() => busy.value ? 'running' : snapshot.value?.status || (pendingInterrupt.value ? 'interrupted' : 'running'))
const statusLabel = computed(() => ({ running: '正在规划', interrupted: '等你确认', completed: '已确认完成', failed: '未能完成', rejected: '已结束' }[status.value]))
const visibleEvents = computed(() => events.value.filter(event => ['node_start', 'node_end', 'interrupt', 'complete', 'error'].includes(event.type)))
const activeNodeStarts = computed(() => {
  const active = new Map<string, AgentEvent>()
  for (const event of visibleEvents.value) {
    if (event.type === 'node_start' && event.node) active.set(event.node, event)
    else if (event.type === 'node_end' && event.node) active.delete(event.node)
    else if (['interrupt', 'complete', 'error'].includes(event.type)) active.clear()
  }
  return new Set(status.value === 'running' ? [...active.values()].map(event => event.seq) : [])
})
const currentStageLabel = computed(() => {
  if (status.value === 'completed') return '行程已确认，规划记录已保存'
  if (status.value === 'rejected') return '本次规划已结束'
  if (status.value === 'failed') return '未能生成满足约束的行程'
  if (activeInterrupt.value?.payload.kind === 'clarify') return '等待补充旅行要求'
  if (activeInterrupt.value?.payload.kind === 'review') return '提案已准备好，等待你审阅'
  const active = visibleEvents.value.filter(event => activeNodeStarts.value.has(event.seq))
  if (active.length > 1) return `正在并行处理 ${active.length} 组任务`
  const latest = active[0] || visibleEvents.value[visibleEvents.value.length - 1]
  return latest ? eventLabel(latest).replace(/ · 开始$/, '') : '正在整理旅行要求'
})
const draftStatus = computed(() => {
  if (status.value === 'completed') return { label: '你已确认', tone: 'approved' }
  if (status.value === 'failed') return { label: '未通过校验', tone: 'not-approved' }
  if (status.value === 'rejected') return { label: '已结束', tone: 'ended' }
  if (activeInterrupt.value?.payload.kind === 'review') return { label: '待确认提案', tone: '' }
  return { label: status.value === 'running' ? '正在核对' : '行程草稿', tone: '' }
})
const missingNames: Record<string, string> = { city: '目的地', date: '游玩日期', budget_max: '预算上限' }
const missingLabel = computed(() => (activeInterrupt.value?.payload.missing || []).map(key => missingNames[key] || key).join('、') || '旅行要求')
const durationLabel = computed(() => isNumber(validation.value?.duration_minutes) ? `${validation.value.duration_minutes} 分钟` : '等待核对')
const costLabel = computed(() => isNumber(validation.value?.cost_estimate) ? `¥${validation.value.cost_estimate.toFixed(0)}` : '等待核对')
const metricItems = computed(() => {
  const metrics = snapshot.value?.metrics || {}
  return [
    { key: 'tool_calls', label: '工具调用', unit: '次' },
    { key: 'model_calls', label: '模型调用', unit: '次' },
    { key: 'proposal_attempts', label: '提案轮次', unit: '轮' },
    { key: 'elapsed_seconds', label: '执行耗时', unit: '秒' }
  ].filter(item => isNumber(metrics[item.key])).map(item => ({ ...item, value: item.key === 'elapsed_seconds' ? Number(metrics[item.key]).toFixed(2) : metrics[item.key] }))
})

function poiFor(id: unknown): JsonObject { return pois.value.find(poi => poi.id === id) || {} }
function sourceLabel(source: unknown, route = false): string {
  if (source === 'fixture') return '示例数据'
  if (source === 'amap') return route ? '高德路径' : '高德检索'
  if (source === 'amap_route' || source === 'amap_direction') return '高德路径'
  if (typeof source === 'string' && (source.includes('estimat') || source === 'fallback' || source === 'haversine')) return '估算'
  return source ? String(source) : '来源未提供'
}
function safeSourceUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined } catch { return undefined }
}
function fetchedLabel(value: unknown): string {
  if (typeof value !== 'string') return '未提供检索时间'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '未提供检索时间' : `${date.toLocaleDateString('zh-CN')} 检索`
}
function distanceLabel(value: unknown): string { return isNumber(value) ? value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m` : '距离未提供' }
function eventLabel(event: AgentEvent): string {
  if (event.type === 'interrupt') return '等待你的补充或确认'
  if (event.type === 'complete') return '当前阶段已保存'
  if (event.type === 'error') return '执行遇到问题'
  const labels: Record<string, string> = { clarify: '确认旅行要求', intake: '整理旅行要求', research: '查找候选地点', research_worker: '查找候选地点', gather: '归并地点与来源', plan_research: '安排检索任务', research_plan: '安排检索任务', dispatch: '分发检索任务', route: '核对路途信息', build_route: '核对路途信息', propose: '生成行程提案', planner: '生成行程提案', validate: '检查时间与预算', repair: '调整不满足约束的部分', review: '等待你审阅提案', finalize: '保存确认后的行程' }
  const [node, branch] = (event.node || '').split(':')
  const label = labels[node] || '处理旅行规划'
  return `${label}${branch !== undefined ? ` · 第 ${Number(branch) + 1} 组` : ''}${event.type === 'node_end' ? ' · 完成' : event.type === 'node_start' ? ' · 开始' : ''}`
}
function eventDetails(event: AgentEvent): string {
  if (!event.message || event.message === eventLabel(event)) return ''
  if (event.node && [ `开始 ${event.node}`, `完成 ${event.node}` ].includes(event.message)) return ''
  return event.message
}
function togglePreference(value: string) {
  const index = form.preferences.indexOf(value)
  if (index >= 0) form.preferences.splice(index, 1)
  else if (form.preferences.length < 4) form.preferences.push(value)
}
function brief(): AgentBrief {
  return { ...form, city: form.city.trim(), date: form.date || '', budget_max: form.budget_max === '' || form.budget_max === null ? null : Number(form.budget_max), preferences: [...form.preferences] }
}
function saveRun(id: string) {
  runId.value = id
  savedRun.value = id
  try { localStorage.setItem(storageKey, id) } catch { /* In-memory progress still works when storage is disabled. */ }
}
function applySnapshot(value: AgentSnapshot, updateForm = false) {
  snapshot.value = value
  events.value = value.events || []
  pendingInterrupt.value = value.interrupt || null
  saveRun(value.run_id)
  if (updateForm && value.brief) Object.assign(form, value.brief)
  if (value.mode) mode.value = value.mode
}
function receiveEvent(event: AgentEvent) {
  saveRun(event.run_id)
  if (!events.value.some(item => item.seq === event.seq)) events.value.push(event)
  if (event.type === 'interrupt') {
    pendingInterrupt.value = event.data as AgentInterrupt
    if (snapshot.value) snapshot.value.interrupt = pendingInterrupt.value
  }
  if (event.type === 'complete' && object(event.data).run_id) applySnapshot(event.data as AgentSnapshot)
  if (event.type === 'error') error.value = event.message || '执行遇到问题，可恢复记录查看已保存的进度。'
}
function scheduleRefresh() {
  clearTimeout(refreshTimer)
  if (!unmounted && snapshot.value?.status === 'running' && !busy.value) {
    refreshTimer = setTimeout(() => { if (runId.value && !busy.value) void restoreRun(runId.value, true) }, 3000)
  }
}
async function restoreRun(id: string, quiet = false) {
  if (restoring.value || busy.value) return
  restoring.value = true
  if (!quiet) error.value = ''
  try { applySnapshot(await getAgentRun(id), !quiet); scheduleRefresh() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '无法恢复记录，请重试。' }
  finally { restoring.value = false }
}
async function execute(work: () => Promise<void>) {
  busy.value = true
  error.value = ''
  clearTimeout(refreshTimer)
  try { await work() }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '连接中断，请尝试恢复记录。' }
  finally {
    // The persisted snapshot, rather than the last delivered SSE frame, is authoritative.
    if (runId.value) {
      try { applySnapshot(await getAgentRun(runId.value)) }
      catch (cause) { if (!error.value) error.value = cause instanceof Error ? cause.message : '无法加载已保存的进度。' }
    }
    busy.value = false
    scheduleRefresh()
  }
}
async function startRun() {
  if (busy.value || restoring.value) return
  snapshot.value = null
  events.value = []
  pendingInterrupt.value = null
  runId.value = ''
  await execute(() => startAgentRun(brief(), mode.value, provider.value, receiveEvent))
}
async function review(action: ReviewAction) {
  const interrupt = activeInterrupt.value
  if (!interrupt || !runId.value || busy.value || restoring.value) return
  const id = interrupt.id
  pendingInterrupt.value = null
  if (snapshot.value) snapshot.value.interrupt = null
  await execute(() => resumeAgentRun(runId.value, id, action, brief(), receiveEvent))
}

onMounted(() => {
  try { savedRun.value = localStorage.getItem(storageKey) || '' } catch { /* Storage is optional. */ }
  if (savedRun.value) void restoreRun(savedRun.value)
})
onBeforeUnmount(() => { unmounted = true; clearTimeout(refreshTimer) })
</script>

<style scoped>
.agent-page{max-width:1360px;margin:auto;padding:0 42px;color:var(--ra-text)}
.topbar{height:94px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--ra-line)}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;font-family:var(--ra-font-sans);font-size:23px;font-weight:700;letter-spacing:-.7px}.brand>span{color:var(--ra-primary);font-size:30px}.brand small{font-size:11px;font-weight:500;border-left:1px solid #cad2df;padding-left:13px;letter-spacing:1px;color:var(--ra-text-soft);margin-left:5px}
.back-link{font-size:12px;color:var(--ra-text-soft);text-decoration:none}.back-link span{padding-left:10px}.intro{padding:52px 0 34px;display:flex;gap:30px;justify-content:space-between;align-items:flex-end}.eyebrow{font:10px var(--ra-font-sans);font-weight:600;letter-spacing:1.7px;color:var(--ra-text-faint);line-height:1.6}.intro h1{font-size:38px;letter-spacing:-1px;line-height:1.5;margin:9px 0}.intro-copy{font-size:13px;color:var(--ra-text-soft);line-height:1.8}.intro-steps{display:flex;gap:10px;align-items:center;font-size:11px;color:var(--ra-text-soft);white-space:nowrap;padding-bottom:7px}.intro-steps i{font-style:normal;color:#b0b9c7}
.workspace{display:grid;grid-template-columns:330px minmax(0,1fr);gap:24px;align-items:start}.panel{background:var(--ra-surface-strong);border:1px solid rgba(255,255,255,.9);border-radius:22px;box-shadow:var(--ra-shadow-sm);padding:28px}.brief-panel{padding:26px;position:sticky;top:20px}.panel-title{display:flex;align-items:center;gap:10px;margin-bottom:22px}.panel h2{font-size:21px;line-height:1.5}.panel-title h2{font-size:18px}.step-number{font-size:10px;font-weight:600;letter-spacing:1px;color:var(--ra-accent);border:1px solid #e7ddd2;border-radius:7px;padding:5px}
.mode-picker{display:flex;background:#edf1f6;padding:4px;border-radius:11px;gap:3px}.mode-picker button{flex:1;border:none;background:transparent;padding:9px;font-size:12px;border-radius:8px;color:var(--ra-text-soft);cursor:pointer}.mode-picker button.selected{background:#fff;color:var(--ra-primary);box-shadow:0 2px 7px #1720330d;font-weight:600}.mode-note{font-size:11px;color:var(--ra-text-soft);line-height:1.9;margin:12px 0 22px}
fieldset{border:0;min-width:0;padding:0;margin:0}.field{display:block;margin-bottom:18px;min-width:0}.field>span{display:flex;align-items:center;gap:7px;font-size:12px;font-weight:600;margin-bottom:8px}.field small{font-size:10px;color:var(--ra-text-faint);font-weight:400}.field input,.field select,.field textarea{display:block;width:100%;background:#f9fafc;border:1px solid #e3e8ef;border-radius:10px;padding:11px 12px;font-size:12px;line-height:1.5;color:var(--ra-text);outline:none;transition:border-color .2s,box-shadow .2s}.field textarea{resize:vertical}.field input:focus,.field select:focus,.field textarea:focus{border-color:#a6b7d0;box-shadow:0 0 0 3px #183b6b08}.two-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}.money-input{position:relative}.money-input>span{position:absolute;left:12px;top:12px;color:#8996a9;font-size:12px}.money-input input{padding-left:27px}.preference-chips{display:flex;gap:7px;flex-wrap:wrap}.preference-chips button{border:1px solid #e4e8ef;background:#fff;color:var(--ra-text-soft);border-radius:7px;font-size:11px;padding:7px 10px;cursor:pointer}.preference-chips button.active{background:#edf2f9;border-color:#b6c7de;color:var(--ra-primary)}
button:disabled,fieldset:disabled button{cursor:wait;opacity:.55;transform:none}.primary-button,.secondary-button{display:inline-flex;align-items:center;justify-content:center;gap:10px;border:1px solid var(--ra-primary);background:var(--ra-primary);color:#fff;padding:12px 18px;line-height:1.5;font-size:12px;font-weight:500;border-radius:10px;cursor:pointer}.primary-button:hover{background:var(--ra-primary-strong);box-shadow:0 6px 16px #183b6b20}.start-button{width:100%;margin-top:3px;justify-content:space-between}.secondary-button{background:transparent;color:var(--ra-primary);border-color:#c9d4e4}.text-button{font-size:12px;color:var(--ra-text-soft);border:0;background:none;cursor:pointer;padding:8px}.auth-note{font-size:10px;color:var(--ra-text-faint);line-height:1.9;margin-top:16px}.auth-note a{color:var(--ra-primary);white-space:nowrap;margin-left:4px;text-underline-offset:3px}.results-column{display:grid;gap:20px;min-width:0}.welcome-panel{padding:0;overflow:hidden;min-height:570px}.map-art{height:290px;position:relative;background-color:#eaf0f2;background-image:linear-gradient(32deg,transparent 45%,#fff9 45%,#fff9 48%,transparent 48%),linear-gradient(-42deg,transparent 36%,#fff8 36%,#fff8 39%,transparent 39%),linear-gradient(90deg,transparent 58%,#dae5de 58%,#dae5de 75%,transparent 75%),linear-gradient(0deg,transparent 28%,#f6f4ee 28%,#f6f4ee 68%,transparent 68%);border-bottom:1px solid #dfe7eb}.map-line{position:absolute;left:26%;right:23%;height:114px;top:68px;border:2px dashed #406b8a;border-radius:20px 55px 12px 45px;transform:rotate(-14deg)}.map-point{position:absolute;background:var(--ra-primary);color:#fff;border:5px solid #fff;border-radius:50%;font-size:10px;width:38px;height:38px;display:grid;place-items:center;box-shadow:0 5px 20px #183b6b20}.point-a{left:24%;top:113px}.point-b{left:52%;top:46px}.point-c{right:20%;top:153px;background:#ad8a64}.map-caption{position:absolute;bottom:19px;left:26px;font-size:9px;letter-spacing:2px;color:#7f9599}.welcome-copy{padding:35px}.tag{font-size:10px;color:#8b6f4f;background:#f6f0e8;border:1px solid #e9e0d5;border-radius:6px;padding:5px 9px;display:inline-block;white-space:nowrap;line-height:1.5}.welcome-copy h2{font-size:27px;margin:15px 0 12px}.welcome-copy p{font-size:13px;line-height:2;color:var(--ra-text-soft);max-width:470px}.welcome-features{display:flex;gap:18px;flex-wrap:wrap;margin-top:25px;color:#718096;font-size:10px}.welcome-features span:before{content:'✓';color:var(--ra-success);padding-right:6px}
.notice{padding:14px 18px;border-radius:12px;margin-bottom:18px;display:flex;align-items:center;justify-content:space-between;gap:15px;font-size:12px;line-height:1.8}.notice.error{background:#fff0ee;border:1px solid #f0d8d2;color:#9e4b41}.notice button{background:none;border:0;color:inherit;font-size:20px;cursor:pointer}.recovery-bar{display:flex;gap:14px;align-items:center;justify-content:space-between;border:1px solid #dce4ec;border-radius:11px;padding:11px 16px;font-size:11px;color:var(--ra-text-soft);margin-bottom:20px;background:#f5f8fb}.saved-dot{display:inline-block;width:5px;height:5px;background:#6c99a1;border-radius:50%;margin-right:8px;vertical-align:2px}.recovery-bar button{font-size:11px;white-space:nowrap;color:var(--ra-primary);border:none;background:none;cursor:pointer}.section-heading{display:flex;gap:14px;align-items:center;justify-content:space-between;margin-bottom:19px}.section-heading .eyebrow{margin-bottom:5px}.status-badge{font-size:11px;border-radius:100px;padding:7px 11px;white-space:nowrap;background:#eaf0f9;color:var(--ra-primary)}.status-badge.interrupted{background:#f6f0e6;color:#8b6f4f}.status-badge.completed{background:#eaf5ef;color:#287354}.status-badge.failed,.status-badge.rejected{background:#f5eae8;color:#9e5b54}.run-info{display:flex;gap:12px;flex-wrap:wrap;color:var(--ra-text-faint);font-size:10px;margin:-7px 0 22px}.event-list{list-style:none;display:grid;gap:0;max-height:320px;overflow:auto;padding-right:4px}.event-list li{display:flex;gap:11px;align-items:flex-start;padding:10px 0;border-bottom:1px solid #eff2f6}.event-list li:last-child{border-bottom:0}.event-mark{color:#4f8e7d;font-size:13px;line-height:1.5;min-width:14px}.current .event-mark{color:#6f88ad}.event-list li.problem{color:var(--ra-danger)}.event-list strong{font-size:12px;font-weight:500;line-height:1.8;display:block}.event-list p{font-size:11px;color:var(--ra-text-soft);line-height:1.8}.event-seq{font-size:9px;color:#adb6c4;margin-left:auto;padding-top:5px}.progress-note{font-size:11px;line-height:1.8;color:var(--ra-text-soft);display:flex;gap:8px;align-items:center;margin-top:15px}.spinner{height:13px;width:13px;border:1.5px solid currentColor;border-right-color:transparent;border-radius:50%;display:inline-block;animation:spin .9s linear infinite;flex-shrink:0}@keyframes spin{to{transform:rotate(360deg)}}
.decision-panel{background:linear-gradient(120deg,#f4f6fc,#fff);border-color:#dbe2ef}.decision-panel h2{margin:13px 0 9px;font-size:24px}.decision-panel p{font-size:12px;line-height:1.9;color:var(--ra-text-soft)}.decision-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:22px}.decision-panel .tag{background:#eaf0f9;border-color:#d3dfee;color:var(--ra-primary)}.clarify-panel{background:#faf7f1;border-color:#e8decd}.plan-summary{font-size:13px;line-height:1.9;color:var(--ra-text-soft);margin-bottom:23px}.plan-totals{display:grid;grid-template-columns:1fr 1fr 1fr;background:#f6f8fb;border:1px solid #e9edf3;border-radius:13px;margin-bottom:27px;padding:18px}.plan-totals div{padding:0 16px;border-right:1px solid #e1e6ef}.plan-totals div:first-child{padding-left:0}.plan-totals div:last-child{border:0}.plan-totals small,.metric-grid small{display:block;font-size:10px;color:var(--ra-text-faint);margin-bottom:9px}.plan-totals strong{font-size:19px;font-weight:600;color:var(--ra-primary);line-height:1.4}.plan-totals em{font-size:11px;font-style:normal;font-weight:400}.itinerary-list{list-style:none}.itinerary-list>li{display:flex;gap:17px;position:relative}.stop-index{font-size:11px;color:var(--ra-primary);border:1px solid #d6e0ef;background:#edf2f9;width:32px;height:32px;flex-shrink:0;display:grid;place-items:center;border-radius:10px;position:relative;z-index:1}.itinerary-list>li:not(:last-child):before{content:'';position:absolute;width:1px;background:#e4e9f0;left:16px;top:32px;bottom:0}.stop-content{padding:3px 0 24px;flex:1;min-width:0}.itinerary-list>li:last-child .stop-content{padding-bottom:0}.stop-heading{display:flex;gap:10px;align-items:center;justify-content:space-between}.stop-heading h3{font-size:16px;line-height:1.7}.stop-content>p{font-size:12px;line-height:1.9;color:var(--ra-text-soft);margin-top:6px}.stop-content .stop-address{font-size:11px;color:var(--ra-text-faint)}.source-badge{font-size:9px;white-space:nowrap;border:1px solid #dbe2ec;background:#f5f7fa;color:#6d7e93;border-radius:4px;padding:3px 6px;font-weight:400}.source-badge.fixture{background:#f8f2e9;border-color:#e9dfd1;color:#92744d}.source-badge.amap{background:#eaf4f0;border-color:#d7e7df;color:#478166}.stop-meta{display:flex;gap:16px;color:#78879a;font-size:10px;margin-top:10px}.transfer-note{font-size:10px;line-height:1.8;color:#8d9aab;background:#f8f9fb;padding:8px 10px;border-radius:7px;margin-top:16px}.transfer-note>span{float:right;color:#9b8567}.plain-notes{margin:20px 0 0;padding-left:17px;font-size:11px;line-height:1.9;color:var(--ra-text-soft)}.approved{background:#eaf5ef;border-color:#d4e7dc;color:#287354}.validation-result{font-size:11px;color:#a26e40;white-space:nowrap}.validation-result.passed{color:var(--ra-success)}.validation-copy{font-size:12px;color:var(--ra-text-soft);line-height:1.9}.check-messages{font-size:11px;line-height:1.9;color:#8e795f;margin-top:12px;padding-left:16px}.check-messages.violation{color:#a7544b;list-style:none;padding-left:0}.passed-copy{font-size:12px;color:var(--ra-success);margin-top:16px}.subtle-label{color:var(--ra-text-faint);font-size:10px;white-space:nowrap}.poi-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.poi-card{border:1px solid #e8edf2;border-radius:12px;padding:16px;background:#fcfdff;min-width:0}.poi-card .stop-heading{align-items:flex-start}.poi-card h3{font-size:13px}.poi-card>p{font-size:11px;line-height:1.8;color:var(--ra-text-soft);margin:9px 0 15px}.poi-footer{display:flex;gap:8px;align-items:center;justify-content:space-between;font-size:9px;color:#99a4b4}.poi-footer a{color:#6d87a5;text-decoration:none;white-space:nowrap}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric-grid strong{font-size:23px;font-weight:500;color:var(--ra-primary)}.metric-grid em{font-size:10px;font-style:normal;color:#9ba6b7;margin-left:5px}.metrics-panel .mode-note{margin-bottom:0;margin-top:18px;font-size:10px}footer{font-size:10px;letter-spacing:.5px;color:#8f9bad;display:flex;justify-content:center;align-items:center;gap:12px;padding:40px 0 32px}
.trace-details{border:1px solid #e1e7ef;border-radius:13px;background:#f8fafc;overflow:hidden}
.trace-details summary{display:flex;justify-content:space-between;align-items:center;gap:20px;min-height:76px;padding:15px 17px;cursor:pointer;list-style:none}
.trace-details summary::-webkit-details-marker{display:none}
.trace-summary-copy{display:grid;gap:6px;min-width:0}.trace-label{font-size:10px;color:#748298;letter-spacing:.5px}.trace-summary-copy strong{font-size:13px;font-weight:500;line-height:1.7;overflow-wrap:anywhere}
.trace-summary-more{display:flex;align-items:center;gap:13px;flex-shrink:0;color:#708097;font-size:10px}.trace-summary-more i{width:7px;height:7px;display:block;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg);transition:transform .2s}
.trace-details[open] .trace-summary-more i{transform:rotate(225deg)}.trace-details[open] summary{border-bottom:1px solid #e1e7ef;background:#f1f5fa}
.trace-details .event-list{padding:6px 17px 10px;background:#fff;max-height:320px}.trace-details .event-list li>div{min-width:0;overflow-wrap:anywhere}.not-approved{background:#faeeeb;border-color:#eed5d0;color:#9b5149}.ended{background:#eef1f5;border-color:#dde3ec;color:#69788e}
:is(button,a,summary,input,select,textarea):focus-visible{outline:3px solid #7c9fc7;outline-offset:3px}.trace-details summary:focus-visible{outline-offset:-3px}
@media(min-width:1400px){.agent-page{padding:0 32px}.workspace{grid-template-columns:350px minmax(0,1fr);gap:28px}.brief-panel{padding:30px}.panel:not(.brief-panel):not(.welcome-panel){padding:32px}}
@media(max-width:1050px){.agent-page{padding:0 26px}.intro-steps{display:none}.workspace{grid-template-columns:300px minmax(0,1fr);gap:18px}.panel{padding:23px}.brief-panel{padding:23px}.poi-grid{grid-template-columns:1fr}.plan-totals{padding:15px}.plan-totals div{padding:0 10px}.plan-totals strong{font-size:16px}.welcome-copy{padding:28px}.welcome-copy h2{font-size:24px}.welcome-features{gap:12px}.metric-grid{grid-template-columns:1fr 1fr;gap:22px}}
@media(max-width:760px){.agent-page{padding:0 18px}.topbar{height:76px}.brand{font-size:21px}.brand small{font-size:10px}.back-link{font-size:11px}.intro{padding:31px 0 25px}.intro .eyebrow{font-size:8px;letter-spacing:1px}.intro h1{font-size:29px;margin-top:10px}.intro-copy{font-size:12px;max-width:310px}.workspace{grid-template-columns:1fr;gap:20px}.brief-panel{position:static}.panel{border-radius:18px;padding:23px}.brief-panel{padding:25px}.welcome-panel{min-height:0}.map-art{height:225px}.map-line{height:90px;top:55px}.point-a{top:85px}.point-b{top:32px}.point-c{top:120px}.welcome-copy{padding:25px}.welcome-copy h2{font-size:23px}.welcome-copy p{font-size:12px}.section-heading{gap:10px}.panel h2{font-size:20px}.section-heading .eyebrow{font-size:8px;letter-spacing:1.4px}.recovery-bar{font-size:10px;padding:10px 12px}.status-badge{font-size:10px;padding:6px 9px}.decision-actions{gap:8px}.decision-actions .primary-button,.decision-actions .secondary-button{flex:1;padding:11px 13px;white-space:nowrap;font-size:11px}.poi-grid{grid-template-columns:1fr 1fr}.poi-card .stop-heading{flex-direction:column;gap:6px}.poi-footer{flex-wrap:wrap}.stop-heading h3{font-size:15px}.plan-totals strong{font-size:17px}.plan-totals small{font-size:9px}.plan-totals div{padding:0 9px}.stop-index{width:28px;height:28px;border-radius:8px}.itinerary-list>li{gap:12px}.itinerary-list>li:not(:last-child):before{left:14px;top:28px}.stop-meta{gap:10px}.transfer-note>span{float:none;margin-left:8px}footer{font-size:9px;gap:9px}}
@media(max-width:520px){
  .agent-page{padding:0 16px}.brand small{display:none}.topbar{gap:14px}.back-link{min-height:44px;display:inline-flex;align-items:center;font-size:12px}.panel,.brief-panel{padding:20px}.welcome-panel{padding:0}.welcome-copy{padding:23px}
  button{min-height:44px}.mode-picker button{font-size:13px}.field input,.field select,.field textarea{min-width:0;min-height:48px;font-size:16px;padding:11px 10px}.field textarea{min-height:116px}.field>span{font-size:13px;flex-wrap:wrap;gap:4px 7px}.field small{font-size:11px;color:#6d7b90}.money-input input{padding-left:28px}.money-input>span{top:14px;font-size:14px}.two-fields{gap:10px}
  .preference-chips{gap:8px}.preference-chips button{font-size:12px;padding:8px 12px}.primary-button,.secondary-button,.text-button{font-size:13px}.auth-note{font-size:11px}.auth-note a{min-height:44px;display:inline-flex;align-items:center;margin-left:0}.mode-note{font-size:12px;line-height:1.8}.recovery-bar{align-items:center;font-size:11px;line-height:1.7;padding:8px 12px}.recovery-bar>span{min-width:0}.recovery-bar button{font-size:12px;padding:0 3px}
  .poi-grid{grid-template-columns:1fr}.poi-card{padding:17px}.poi-card .stop-heading{flex-direction:row;align-items:flex-start}.poi-card h3{font-size:15px}.poi-card>p{font-size:13px}.source-badge{font-size:11px}.poi-footer{font-size:12px;color:#6d7b90;gap:4px 12px}.poi-footer a{min-height:44px;display:inline-flex;align-items:center;font-size:12px}
  .plan-summary,.stop-content>p,.validation-copy,.decision-panel p{font-size:13px}.stop-content .stop-address,.stop-meta,.plain-notes,.check-messages{font-size:12px}.stop-meta{flex-wrap:wrap;gap:6px 12px}.transfer-note{font-size:12px}.plan-totals{padding:13px 10px}.plan-totals div{padding:0 8px}.plan-totals strong{font-size:15px}.plan-totals small,.metric-grid small{font-size:11px;line-height:1.6}.plan-totals em{font-size:11px}.decision-actions{display:grid;grid-template-columns:1fr;gap:10px}.decision-actions .primary-button,.decision-actions .secondary-button{font-size:13px;white-space:normal}.decision-actions .text-button{justify-self:start;padding-left:0}
  .trace-details summary{padding:14px;gap:12px}.trace-summary-copy strong{font-size:13px}.trace-label,.trace-summary-more{font-size:11px}.trace-summary-more{gap:9px}.trace-details .event-list{padding:6px 14px 10px}.event-list strong{font-size:12px}.event-list p{font-size:12px}.run-info{font-size:11px;line-height:1.8}.section-heading{align-items:flex-start;flex-wrap:wrap}.section-heading .eyebrow{font-size:9px}.validation-result,.subtle-label{font-size:11px}.status-badge{font-size:11px}.intro-copy{font-size:13px}
}
@media(prefers-reduced-motion:reduce){:global(html){scroll-behavior:auto}.spinner{animation:none}button,a,summary,.trace-summary-more i,.field input,.field select,.field textarea{transition:none}button:hover{transform:none}}
</style>
