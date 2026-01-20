<template>
  <div class="flex h-[calc(100vh-140px)] gap-6">
    <!-- Left: Chat Panel -->
    <div class="flex-1 flex flex-col bg-warm-50 rounded-2xl border border-warm-300 overflow-hidden">
      <!-- Chat Header -->
      <div class="px-6 py-4 border-b border-warm-300 bg-warm-100">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-anthropic-orange to-anthropic-orange-dark rounded-xl flex items-center justify-center shadow-sm">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h3 class="font-semibold text-dark-300">{{ skill?.name || 'Loading...' }}</h3>
            <p class="text-xs text-dark-50">
              Phase: {{ phaseText }}
              <span v-if="currentSection" class="ml-2 text-anthropic-orange">| Writing: {{ currentSection }}</span>
            </p>
          </div>
        </div>
      </div>

      <!-- Messages -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto p-6 space-y-4">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="[
            'max-w-[85%] p-4 rounded-2xl',
            msg.role === 'user'
              ? 'ml-auto bg-anthropic-orange text-white shadow-sm'
              : 'bg-warm-200 text-dark-300 border border-warm-300'
          ]"
        >
          <div class="whitespace-pre-wrap text-sm leading-relaxed">{{ msg.content }}</div>
        </div>

        <!-- Typing indicator -->
        <div v-if="isTyping" class="bg-warm-200 text-dark-300 max-w-[85%] p-4 rounded-2xl border border-warm-300">
          <span class="inline-flex space-x-1.5">
            <span class="w-2 h-2 bg-anthropic-orange rounded-full animate-bounce"></span>
            <span class="w-2 h-2 bg-anthropic-orange rounded-full animate-bounce" style="animation-delay: 0.1s"></span>
            <span class="w-2 h-2 bg-anthropic-orange rounded-full animate-bounce" style="animation-delay: 0.2s"></span>
          </span>
        </div>

        <!-- Writing progress -->
        <div v-if="isWriting" class="bg-warm-200 border border-anthropic-orange-light text-dark-300 p-5 rounded-2xl">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-5 h-5 border-2 border-warm-300 border-t-anthropic-orange rounded-full animate-spin"></div>
            <span class="font-medium text-dark-300">Generating document...</span>
          </div>
          <div v-if="writingProgress.total > 0" class="text-sm">
            <div class="flex justify-between mb-2 text-dark-50">
              <span>{{ writingProgress.current }} / {{ writingProgress.total }} sections</span>
              <span>{{ Math.round(writingProgress.current / writingProgress.total * 100) }}%</span>
            </div>
            <div class="w-full bg-warm-300 rounded-full h-2">
              <div
                class="bg-gradient-to-r from-anthropic-orange to-anthropic-orange-dark h-2 rounded-full transition-all duration-300"
                :style="{ width: (writingProgress.current / writingProgress.total * 100) + '%' }"
              ></div>
            </div>
            <p v-if="currentSection" class="mt-3 text-xs text-dark-50">Current: {{ currentSection }}</p>
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="p-4 border-t border-warm-300 bg-warm-100">
        <div class="flex gap-3">
          <input
            v-model="inputMessage"
            @keyup.enter="sendMessage"
            :disabled="isTyping || isWriting || isComplete"
            type="text"
            placeholder="Type your response..."
            class="flex-1 px-5 py-3 bg-warm-50 border border-warm-300 rounded-xl text-dark-300 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent disabled:bg-warm-200 disabled:text-warm-400 transition-all"
          />
          <button
            @click="sendMessage"
            :disabled="!inputMessage.trim() || isTyping || isWriting || isComplete"
            class="px-6 py-3 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark disabled:bg-warm-300 disabled:text-warm-400 disabled:cursor-not-allowed transition-colors shadow-sm hover:shadow-md"
          >
            Send
          </button>
        </div>
      </div>
    </div>

    <!-- Right: Document Preview -->
    <div class="w-[45%] flex flex-col bg-warm-50 rounded-2xl border border-warm-300 overflow-hidden">
      <!-- Preview Header -->
      <div class="px-6 py-4 border-b border-warm-300 bg-warm-100 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-warm-200 rounded-xl flex items-center justify-center">
            <svg class="w-5 h-5 text-dark-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 class="font-semibold text-dark-300">Document Preview</h3>
        </div>
        <div v-if="documentContent" class="flex gap-2">
          <button
            @click="copyDocument"
            class="px-3 py-2 text-sm bg-warm-200 text-dark-100 rounded-xl hover:bg-warm-300 transition-colors font-medium"
          >
            Copy
          </button>
          <div class="relative" ref="exportDropdown">
            <button
              @click="showExportMenu = !showExportMenu"
              class="px-3 py-2 text-sm bg-anthropic-orange text-white rounded-xl hover:bg-anthropic-orange-dark transition-colors font-medium shadow-sm flex items-center gap-1"
            >
              Export
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div
              v-if="showExportMenu"
              class="absolute right-0 mt-2 w-40 bg-white rounded-xl shadow-lg border border-warm-300 py-2 z-10"
            >
              <button
                @click="exportAs('md')"
                class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-100 flex items-center gap-2"
              >
                <span class="w-6 text-center text-xs font-mono bg-warm-200 rounded px-1">MD</span>
                Markdown
              </button>
              <button
                @click="exportAs('docx')"
                class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-100 flex items-center gap-2"
              >
                <span class="w-6 text-center text-xs font-mono bg-blue-100 text-blue-700 rounded px-1">W</span>
                Word (.docx)
              </button>
              <button
                @click="exportAs('pdf')"
                class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-100 flex items-center gap-2"
              >
                <span class="w-6 text-center text-xs font-mono bg-red-100 text-red-700 rounded px-1">PDF</span>
                PDF
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Preview Content -->
      <div class="flex-1 overflow-y-auto p-6">
        <div v-if="documentContent" class="markdown-content prose prose-warm max-w-none" v-html="renderedDocument"></div>
        <div v-else-if="isWriting" class="h-full flex items-center justify-center">
          <div class="text-center">
            <div class="w-12 h-12 border-3 border-warm-300 border-t-anthropic-orange rounded-full animate-spin mx-auto"></div>
            <p class="mt-4 text-dark-50 font-medium">Generating document...</p>
          </div>
        </div>
        <div v-else class="h-full flex items-center justify-center">
          <div class="text-center">
            <div class="w-16 h-16 bg-warm-200 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p class="text-dark-100 font-medium">Document Preview</p>
            <p class="text-sm text-warm-400 mt-1">Complete the conversation to generate your document</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { api } from '../api'

const route = useRoute()
const skillId = computed(() => route.params.skillId)

// State
const skill = ref(null)
const sessionId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const isTyping = ref(false)
const isWriting = ref(false)
const isComplete = ref(false)
const documentContent = ref('')
const phase = ref('init')
const messagesContainer = ref(null)
const currentSection = ref('')
const writingProgress = ref({ current: 0, total: 0 })
const showExportMenu = ref(false)
const exportDropdown = ref(null)
const currentSectionLevel = ref(1)

// Computed
const phaseText = computed(() => {
  const phases = {
    'init': 'Initializing',
    'requirement': 'Collecting Requirements',
    'writing': 'Generating Document',
    'review': 'Reviewing',
    'complete': 'Complete',
    'error': 'Error'
  }
  return phases[phase.value] || phase.value
})

const renderedDocument = computed(() => {
  if (!documentContent.value) return ''
  return marked(documentContent.value)
})

// Methods
const fetchSkill = async () => {
  try {
    const response = await api.get(`/skills/${skillId.value}`)
    skill.value = response.data
  } catch (e) {
    console.error('Failed to fetch skill:', e)
  }
}

const startConversation = async () => {
  isTyping.value = true
  try {
    const response = await api.post('/chat/start', {
      skill_id: skillId.value
    })

    sessionId.value = response.data.session_id
    phase.value = response.data.phase

    messages.value.push({
      role: 'assistant',
      content: response.data.message
    })
  } catch (e) {
    console.error('Failed to start conversation:', e)
    messages.value.push({
      role: 'assistant',
      content: 'Sorry, failed to start the conversation. Please ensure the backend server is running.'
    })
  } finally {
    isTyping.value = false
  }
}

const sendMessage = async () => {
  const message = inputMessage.value.trim()
  if (!message || isTyping.value || isWriting.value) return

  // Add user message
  messages.value.push({
    role: 'user',
    content: message
  })
  inputMessage.value = ''
  isTyping.value = true

  await nextTick()
  scrollToBottom()

  try {
    const response = await api.post('/chat/message', {
      session_id: sessionId.value,
      message: message
    })

    phase.value = response.data.phase
    isComplete.value = response.data.is_complete

    messages.value.push({
      role: 'assistant',
      content: response.data.message
    })

    // If entering writing phase, start streaming generation
    if (response.data.phase === 'writing') {
      isTyping.value = false
      await startStreamGeneration()
    }

    if (response.data.document) {
      documentContent.value = response.data.document
    }
  } catch (e) {
    console.error('Failed to send message:', e)
    messages.value.push({
      role: 'assistant',
      content: 'Sorry, failed to send. Please try again.'
    })
  } finally {
    isTyping.value = false
    await nextTick()
    scrollToBottom()
  }
}

const startStreamGeneration = async () => {
  isWriting.value = true
  documentContent.value = ''
  writingProgress.value = { current: 0, total: 0 }

  try {
    const eventSource = new EventSource(`/api/chat/generate/${sessionId.value}/stream`)

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'start':
          writingProgress.value.total = data.total_sections
          break

        case 'section_start':
          currentSection.value = data.section_title
          currentSectionLevel.value = data.section_level || 1
          writingProgress.value.current = data.section_index
          // 添加标题到文档（带换行）
          if (documentContent.value && !documentContent.value.endsWith('\n\n')) {
            documentContent.value += '\n\n'
          }
          const heading = '#'.repeat(currentSectionLevel.value) + ' ' + data.section_title
          documentContent.value += heading + '\n\n'
          break

        case 'chunk':
          documentContent.value += data.content
          break

        case 'section_complete':
          // Section complete
          break

        case 'complete':
          isWriting.value = false
          isComplete.value = true
          phase.value = 'complete'
          currentSection.value = ''
          documentContent.value = data.document
          eventSource.close()

          messages.value.push({
            role: 'assistant',
            content: 'Document generation complete! You can preview and download it on the right.'
          })
          break

        case 'error':
          isWriting.value = false
          phase.value = 'error'
          eventSource.close()
          messages.value.push({
            role: 'assistant',
            content: `Generation failed: ${data.error}`
          })
          break
      }
    }

    eventSource.onerror = (e) => {
      console.error('SSE error:', e)
      isWriting.value = false
      eventSource.close()
    }

  } catch (e) {
    console.error('Failed to start generation:', e)
    isWriting.value = false
    messages.value.push({
      role: 'assistant',
      content: 'Document generation failed. Please try again.'
    })
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const copyDocument = () => {
  if (documentContent.value) {
    navigator.clipboard.writeText(documentContent.value)
    alert('Copied to clipboard')
  }
}

const exportAs = async (format) => {
  showExportMenu.value = false
  if (!documentContent.value) return

  const filename = skill.value?.name || 'document'

  if (format === 'md') {
    // 直接下载 Markdown
    const blob = new Blob([documentContent.value], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `${filename}.md`)
  } else if (format === 'docx' || format === 'pdf') {
    // 调用后端 API 进行转换
    try {
      const response = await api.post('/documents/export', {
        content: documentContent.value,
        format: format,
        filename: filename
      }, {
        responseType: 'blob'
      })

      const contentType = format === 'docx'
        ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        : 'application/pdf'
      const blob = new Blob([response.data], { type: contentType })
      downloadBlob(blob, `${filename}.${format}`)
    } catch (e) {
      console.error('Export failed:', e)
      alert(`Export to ${format.toUpperCase()} failed. Please try again.`)
    }
  }
}

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = window.document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const handleClickOutside = (event) => {
  if (exportDropdown.value && !exportDropdown.value.contains(event.target)) {
    showExportMenu.value = false
  }
}

// Watch for message changes to auto-scroll
watch(messages, () => {
  nextTick(() => scrollToBottom())
}, { deep: true })

// Lifecycle
onMounted(async () => {
  await fetchSkill()
  await startConversation()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.border-3 {
  border-width: 3px;
}

.prose-warm {
  --tw-prose-body: #252523;
  --tw-prose-headings: #191918;
  --tw-prose-links: #D97757;
  --tw-prose-bold: #191918;
  --tw-prose-counters: #2D2D2B;
  --tw-prose-bullets: #D1CBC0;
  --tw-prose-hr: #E8E4DD;
  --tw-prose-quotes: #252523;
  --tw-prose-quote-borders: #D97757;
  --tw-prose-code: #191918;
  --tw-prose-pre-code: #F5F3EF;
  --tw-prose-pre-bg: #252523;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  color: #191918;
  font-weight: 600;
}

.markdown-content :deep(a) {
  color: #D97757;
}

.markdown-content :deep(a:hover) {
  color: #C25E3D;
}

.markdown-content :deep(code) {
  background-color: #F5F3EF;
  padding: 0.125rem 0.375rem;
  border-radius: 0.375rem;
  font-size: 0.875em;
}

.markdown-content :deep(pre) {
  background-color: #252523;
  border-radius: 0.75rem;
  padding: 1rem;
}

.markdown-content :deep(blockquote) {
  border-left-color: #D97757;
  background-color: #FAF9F6;
  padding: 1rem;
  border-radius: 0 0.5rem 0.5rem 0;
}
</style>
