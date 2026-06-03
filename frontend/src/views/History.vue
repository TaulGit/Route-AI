<template>
  <div class="history-page">
    <div class="history-header">
      <div>
        <p class="history-kicker">RouteAI</p>
        <h1>历史记录</h1>
        <p>查看并管理你的聊天会话与行程结果，支持重命名和删除。</p>
      </div>
      <div class="history-actions">
        <el-button @click="$router.push('/')">返回首页</el-button>
        <el-button type="primary" @click="refreshHistory" :loading="historyStore.loading">刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="history-tabs">
      <el-tab-pane label="聊天历史" name="chat">
        <div class="history-list" v-loading="historyStore.loading">
          <el-empty v-if="!historyStore.chatItems.length" description="暂无聊天历史" />
          <div v-for="item in historyStore.chatItems" :key="item.session_id" class="history-card">
            <div class="history-card-head">
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.latest_message || '暂无摘要' }}</p>
              </div>
              <div class="history-card-actions">
                <el-button text @click="openRename('chat', item.session_id, item.title)">重命名</el-button>
                <el-button text type="primary" @click="openChat(item.session_id)">打开</el-button>
                <el-button text type="danger" @click="removeChat(item.session_id)">删除</el-button>
              </div>
            </div>
            <div class="history-meta">
              <span>消息数：{{ item.message_count }}</span>
              <span>更新时间：{{ formatDate(item.updated_at) }}</span>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="行程历史" name="trip">
        <div class="history-list" v-loading="historyStore.loading">
          <el-empty v-if="!historyStore.tripItems.length" description="暂无行程历史" />
          <div v-for="item in historyStore.tripItems" :key="item.session_id" class="history-card">
            <div class="history-card-head">
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.city }} · {{ item.record_type === 'local_route' ? '本地路线' : '旅行行程' }}</p>
              </div>
              <div class="history-card-actions">
                <el-button text @click="openRename('trip', item.session_id, item.title)">重命名</el-button>
                <el-button text type="primary" @click="openTrip(item.session_id)">打开</el-button>
                <el-button text type="danger" @click="removeTrip(item.session_id)">删除</el-button>
              </div>
            </div>
            <div class="history-meta">
              <span>创建时间：{{ formatDate(item.created_at) }}</span>
              <span>更新时间：{{ formatDate(item.updated_at) }}</span>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="renameDialogVisible" title="重命名记录" width="420px">
      <el-input v-model="renameTitle" maxlength="255" show-word-limit placeholder="请输入新标题" />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { useHistoryStore } from '@/stores/history'
import { useTripStore } from '@/stores/trip'

const router = useRouter()
const historyStore = useHistoryStore()
const chatStore = useChatStore()
const tripStore = useTripStore()

const activeTab = ref<'chat' | 'trip'>('chat')
const renameDialogVisible = ref(false)
const renameTitle = ref('')
const renameType = ref<'chat' | 'trip'>('chat')
const renameSessionId = ref('')

async function refreshHistory() {
  try {
    await historyStore.loadAll()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '加载历史失败')
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

async function openChat(sessionId: string) {
  try {
    const detail = await historyStore.loadChatDetail(sessionId)
    chatStore.setSessionId(detail.session_id)
    chatStore.setTitle(detail.title)
    chatStore.setMessages(detail.history.map((item) => ({
      role: item.role,
      content: item.content,
      timestamp: item.timestamp ? new Date(item.timestamp) : new Date()
    })))
    tripStore.setSessionId(detail.session_id)
    tripStore.setTitle('')
    tripStore.setTripPlan(null)
    tripStore.setRoutePlan(null)
    router.push('/chat')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '打开聊天历史失败')
  }
}

async function openTrip(sessionId: string) {
  try {
    const detail = await historyStore.loadTripDetail(sessionId)
    tripStore.loadTripHistory(detail.session_id, detail.title, detail.result_data as any, detail.record_type)
    router.push('/result')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '打开行程历史失败')
  }
}

function openRename(type: 'chat' | 'trip', sessionId: string, title: string) {
  renameType.value = type
  renameSessionId.value = sessionId
  renameTitle.value = title
  renameDialogVisible.value = true
}

async function confirmRename() {
  const title = renameTitle.value.trim()
  if (!title) {
    ElMessage.warning('标题不能为空')
    return
  }

  try {
    if (renameType.value === 'chat') {
      await historyStore.renameChat(renameSessionId.value, title)
      if (chatStore.sessionId === renameSessionId.value) {
        chatStore.setTitle(title)
      }
    } else {
      await historyStore.renameTrip(renameSessionId.value, title)
      if (tripStore.sessionId === renameSessionId.value) {
        tripStore.setTitle(title)
      }
    }
    renameDialogVisible.value = false
    ElMessage.success('重命名成功')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '重命名失败')
  }
}

async function removeChat(sessionId: string) {
  try {
    await ElMessageBox.confirm('确认删除这条聊天历史吗？', '提示', { type: 'warning' })
    await historyStore.removeChat(sessionId)
    ElMessage.success('删除成功')
  } catch {
    // 用户取消或请求失败
  }
}

async function removeTrip(sessionId: string) {
  try {
    await ElMessageBox.confirm('确认删除这条行程历史吗？', '提示', { type: 'warning' })
    await historyStore.removeTrip(sessionId)
    ElMessage.success('删除成功')
  } catch {
    // 用户取消或请求失败
  }
}

onMounted(() => {
  refreshHistory()
})
</script>

<style scoped>
.history-page {
  min-height: 100vh;
  padding: 28px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  max-width: 1040px;
  margin: 0 auto 24px;
  padding: 28px 30px;
  border-radius: 30px;
  background: linear-gradient(135deg, rgba(20, 44, 80, 0.94), rgba(32, 63, 108, 0.94) 52%, rgba(101, 118, 197, 0.88));
  color: #fff;
  box-shadow: var(--ra-shadow-lg);
}

.history-kicker {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(226, 211, 189, 0.9);
  font-weight: 700;
}

.history-header h1 {
  margin: 8px 0 10px;
  font-size: clamp(30px, 4vw, 38px);
  line-height: 1.1;
  color: #fff;
}

.history-header p {
  max-width: 660px;
  color: rgba(235, 240, 249, 0.84);
  line-height: 1.8;
}

.history-actions {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.history-tabs {
  max-width: 1040px;
  margin: 0 auto;
  padding: 22px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.72);
  box-shadow: var(--ra-shadow-lg);
  backdrop-filter: blur(16px);
}

.history-list {
  display: grid;
  gap: 16px;
}

.history-card {
  padding: 22px;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(247, 249, 252, 0.86));
  box-shadow: 0 14px 32px rgba(18, 31, 53, 0.06);
  transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}

.history-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 22px 44px rgba(18, 31, 53, 0.1);
  border-color: rgba(24, 59, 107, 0.14);
}

.history-card-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.history-card-head h3 {
  margin: 0 0 8px;
  color: var(--ra-text);
  font-size: 20px;
}

.history-card-head p {
  color: var(--ra-text-soft);
  line-height: 1.7;
}

.history-card-actions {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.history-card-actions :deep(.el-button--primary.is-text) {
  color: #f3f7ff;
}

.history-card-actions :deep(.el-button--primary.is-text:hover) {
  color: #ffffff;
}

:deep(.history-tabs .el-tabs__header) {
  margin-bottom: 18px;
}

:deep(.history-tabs .el-tabs__item) {
  height: 40px;
  border-radius: 999px;
  padding: 0 18px;
  font-weight: 600;
  color: var(--ra-text-soft);
}

:deep(.history-tabs .el-tabs__item.is-active) {
  color: var(--ra-primary);
  background: rgba(24, 59, 107, 0.08);
}

:deep(.history-tabs .el-tabs__active-bar) {
  display: none;
}

@media (max-width: 768px) {
  .history-page {
    padding: 14px;
  }

  .history-header,
  .history-card-head {
    flex-direction: column;
  }

  .history-header,
  .history-tabs {
    border-radius: 24px;
    padding: 20px;
  }

  .history-actions,
  .history-card-actions,
  .history-meta {
    flex-wrap: wrap;
  }
}
</style>
