<template>
  <div class="space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-display font-bold text-dark-300">我的文档</h2>
        <p class="text-dark-50 text-sm mt-1">查看与管理已生成的文档</p>
      </div>
      <router-link
        to="/"
        class="px-5 py-2.5 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-colors shadow-sm hover:shadow-md flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        新建文档
      </router-link>
    </div>

    <!-- Documents List -->
    <div v-if="documents.length > 0" class="grid gap-4">
      <div
        v-for="doc in documents"
        :key="doc.id"
          class="group bg-warm-100 rounded-2xl border border-warm-300 p-5 hover:border-anthropic-orange hover:shadow-lg transition-all duration-300"
      >
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 bg-warm-200 rounded-xl flex items-center justify-center group-hover:bg-anthropic-orange-light transition-colors">
              <svg class="w-6 h-6 text-warm-400 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h3 class="font-display font-semibold text-dark-300 group-hover:text-anthropic-orange transition-colors">{{ doc.title }}</h3>
              <p class="text-sm text-dark-50 mt-1 flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {{ formatDate(doc.updated_at) }}
              </p>
            </div>
          </div>
          <div class="flex gap-2">
            <button
              @click="viewDocument(doc)"
              class="px-4 py-2 text-sm bg-warm-200 text-dark-100 rounded-xl hover:bg-warm-300 transition-colors font-medium"
            >
              查看
            </button>
            <button
              @click="renameDocument(doc)"
              class="px-4 py-2 text-sm bg-warm-200 text-dark-100 rounded-xl hover:bg-warm-300 transition-colors font-medium"
            >
              重命名
            </button>
            <button
              @click="deleteDocument(doc.id)"
              class="px-4 py-2 text-sm bg-red-900/30 text-red-300 rounded-xl hover:bg-red-900/50 transition-colors font-medium"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="flex flex-col items-center justify-center py-20">
      <div class="w-20 h-20 bg-warm-200 rounded-2xl flex items-center justify-center mb-6">
        <svg class="w-10 h-10 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h3 class="text-xl font-display font-semibold text-dark-300">暂无文档</h3>
      <p class="text-dark-50 mt-2 mb-6">创建第一份文档开始使用</p>
      <router-link
        to="/"
        class="px-6 py-3 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-colors shadow-sm hover:shadow-md flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        新建文档
      </router-link>
    </div>

    <!-- Document Viewer Modal -->
    <Teleport to="body">
      <div
        v-if="selectedDocument"
        class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="selectedDocument = null"
      >
        <div class="bg-warm-50 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden border border-warm-300">
          <!-- Modal Header -->
          <div class="px-6 py-4 border-b border-warm-300 bg-warm-100 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-anthropic-orange rounded-xl flex items-center justify-center">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 class="font-semibold text-dark-300">{{ selectedDocument.title }}</h3>
            </div>
            <button
              @click="selectedDocument = null"
              class="w-10 h-10 rounded-xl bg-warm-200 hover:bg-warm-300 flex items-center justify-center transition-colors"
            >
              <svg class="w-5 h-5 text-dark-100" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <!-- Modal Content -->
          <div class="p-6 overflow-y-auto max-h-[calc(90vh-80px)]">
            <div class="markdown-content prose prose-warm max-w-none" v-html="renderedContent"></div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'
import { api } from '../api'

const documents = ref([])
const selectedDocument = ref(null)

const renderedContent = computed(() => {
  if (!selectedDocument.value) return ''
  return marked(selectedDocument.value.content)
})

const fetchDocuments = async () => {
  try {
    const response = await api.get('/documents/')
    documents.value = response.data
  } catch (e) {
    console.error('Failed to fetch documents:', e)
  }
}

const viewDocument = (doc) => {
  selectedDocument.value = doc
}

const renameDocument = async (doc) => {
  const newTitle = window.prompt('请输入新的文档名称：', doc.title)
  if (!newTitle || !newTitle.trim() || newTitle.trim() === doc.title) return

  try {
    const response = await api.put(`/documents/${doc.id}`, { title: newTitle.trim() })
    const updated = response.data
    documents.value = documents.value.map(item => (item.id === doc.id ? updated : item))
    if (selectedDocument.value?.id === doc.id) {
      selectedDocument.value = updated
    }
  } catch (e) {
    console.error('Failed to rename document:', e)
    alert('重命名失败')
  }
}

const deleteDocument = async (docId) => {
  if (!confirm('确认删除该文档？')) return

  try {
    await api.delete(`/documents/${docId}`)
    documents.value = documents.value.filter(d => d.id !== docId)
  } catch (e) {
    console.error('Failed to delete document:', e)
    alert('删除失败')
  }
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  fetchDocuments()
})
</script>

<style scoped>
.prose-warm {
  --tw-prose-body: #D5DDE9;
  --tw-prose-headings: #F8FAFC;
  --tw-prose-links: #E36A3A;
  --tw-prose-bold: #F8FAFC;
  --tw-prose-counters: #B7C3D6;
  --tw-prose-bullets: #2F3C55;
  --tw-prose-hr: #243044;
  --tw-prose-quotes: #D5DDE9;
  --tw-prose-quote-borders: #E36A3A;
  --tw-prose-code: #F8FAFC;
  --tw-prose-pre-code: #E6ECF4;
  --tw-prose-pre-bg: #0B0F14;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  color: #F8FAFC;
  font-weight: 600;
}

.markdown-content :deep(a) {
  color: #E36A3A;
}

.markdown-content :deep(a:hover) {
  color: #F0A384;
}

.markdown-content :deep(code) {
  background-color: #1B2230;
  padding: 0.125rem 0.375rem;
  border-radius: 0.375rem;
  font-size: 0.875em;
}

.markdown-content :deep(pre) {
  background-color: #0B0F14;
  border-radius: 0.75rem;
  padding: 1rem;
}

.markdown-content :deep(blockquote) {
  border-left-color: #E36A3A;
  background-color: #141A21;
  padding: 1rem;
  border-radius: 0 0.5rem 0.5rem 0;
}
</style>
