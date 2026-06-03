import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string>('')
  const title = ref<string>('')
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)

  const hasMessages = computed(() => messages.value.length > 0)

  function setSessionId(id: string) {
    sessionId.value = id
  }

  function setTitle(value: string) {
    title.value = value
  }

  function setMessages(newMessages: ChatMessage[]) {
    messages.value = newMessages
  }

  function addMessage(role: 'user' | 'assistant', content: string) {
    messages.value.push({
      role,
      content,
      timestamp: new Date()
    })
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  function clearMessages() {
    messages.value = []
  }

  function reset() {
    sessionId.value = ''
    title.value = ''
    messages.value = []
    isLoading.value = false
  }

  return {
    sessionId,
    title,
    messages,
    isLoading,
    hasMessages,
    setSessionId,
    setTitle,
    setMessages,
    addMessage,
    setLoading,
    clearMessages,
    reset
  }
})

