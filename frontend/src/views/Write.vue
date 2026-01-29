<template>
  <div class="flex flex-col lg:flex-row flex-1 min-h-0 h-full gap-6 lg:gap-5 lg:overflow-hidden">
    <!-- Left Pane: Upload + Skill-Fixer -->
    <section class="flex flex-col flex-1 min-h-0 h-full rounded-2xl border border-warm-300 bg-warm-50/80 overflow-hidden shadow-sm hover:shadow-lg transition-shadow">
      <header class="px-5 py-4 border-b border-warm-300 bg-gradient-to-b from-warm-100 to-warm-50 flex items-start justify-between gap-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-signal-400 to-signal-600 rounded-xl flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <p class="font-display font-semibold text-dark-300">材料与会话增强</p>
            <p class="text-xs text-dark-50">上传材料后，Skill-Fixer 会生成本会话的补充规范与写作提示。</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span
            class="text-xs px-2 py-0.5 rounded-full border"
            :class="skillOverlay ? 'bg-signal-200 text-dark-300 border-signal-200' : 'bg-warm-200 text-dark-100 border-warm-300'"
          >
            {{ skillOverlay ? 'Skill-Fixer 已启用' : 'Skill-Fixer 未启用' }}
          </span>
        </div>
      </header>

      <div class="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
        <!-- Upload Zone -->
        <div
          class="border-2 border-dashed rounded-2xl p-6 cursor-pointer transition-colors transition-transform duration-200 hover:scale-[1.01] active:scale-[0.995]"
          :class="isDragging ? 'border-anthropic-orange bg-anthropic-orange/5' : 'border-warm-300 hover:border-anthropic-orange hover:bg-warm-100'"
          @click="triggerFileUpload"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <input
            ref="fileInputRef"
            type="file"
            multiple
            accept=".md,.txt,.doc,.docx,.pdf,.pptx"
            class="hidden"
            @change="handleFileSelect"
          />

          <div v-if="isUploading" class="flex flex-col items-center">
            <div class="w-12 h-12 border-3 border-warm-300 border-t-anthropic-orange rounded-full spinner mb-3"></div>
            <p class="text-dark-100 font-medium">正在抽取信息...</p>
            <p class="text-xs text-dark-50 mt-1">请稍候</p>
          </div>

          <div v-else class="text-center">
            <svg class="w-10 h-10 mx-auto text-warm-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p class="text-dark-100 font-medium">拖拽文件到此处</p>
            <p class="text-sm text-dark-50 mt-1">或点击选择</p>
            <p class="text-xs text-warm-400 mt-3">支持：.md, .txt, .doc, .docx, .pdf, .pptx</p>
          </div>
        </div>

        <!-- Uploaded Files -->
        <div class="rounded-2xl border border-warm-300 bg-warm-100/80 p-4">
          <div class="flex items-center justify-between gap-3 mb-3">
            <p class="text-sm font-semibold text-dark-300">已上传文件</p>
            <span class="text-xs text-dark-50">{{ uploadedFiles.length ? `${uploadedFiles.length} 个` : '暂无' }}</span>
          </div>
          <div v-if="uploadedFiles.length === 0" class="text-xs text-dark-50">
            上传材料后会自动生成会话级补充信息。
          </div>
          <div v-else class="space-y-2 max-h-44 overflow-y-auto pr-1">
            <div
              v-for="(file, index) in uploadedFiles"
              :key="index"
              class="flex items-center gap-3 p-3 bg-warm-50 border border-warm-300 rounded-xl"
            >
              <svg class="w-5 h-5 text-green-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span class="flex-1 text-sm text-dark-300 truncate">{{ file.name }}</span>
              <span class="text-xs text-green-300 shrink-0">抽取字段：{{ file.extractedCount }}</span>
            </div>
          </div>
        </div>

        <!-- Skill-Fixer Overlay -->
        <div class="rounded-2xl border border-warm-300 bg-warm-100/80 p-4">
          <div class="flex items-center justify-between gap-3 mb-3">
            <p class="text-sm font-semibold text-dark-300">Skill-Fixer 输出</p>
            <span
              class="text-xs px-2 py-0.5 rounded-full border"
              :class="skillOverlay ? 'bg-signal-200 text-dark-300 border-signal-200' : 'bg-warm-200 text-dark-100 border-warm-300'"
            >
              {{ skillOverlay ? '已生成' : '等待材料' }}
            </span>
          </div>

          <div v-if="!skillOverlay" class="text-xs text-dark-50">
            当前会话还没有生成 Skill-Fixer 覆盖。上传材料后会自动生成。
          </div>

          <div v-else class="space-y-3">
            <div class="flex flex-wrap gap-2">
              <span class="text-xs bg-warm-200 text-dark-100 px-2 py-0.5 rounded-full">写作准则：{{ overlayStats.principles }}</span>
              <span class="text-xs bg-warm-200 text-dark-100 px-2 py-0.5 rounded-full">章节补充：{{ overlayStats.sectionCount }}</span>
              <span class="text-xs bg-warm-200 text-dark-100 px-2 py-0.5 rounded-full">规范补充：{{ overlayStats.hasGuidelines ? '有' : '无' }}</span>
              <span v-if="overlayStats.hasMaterialContext" class="text-xs bg-warm-200 text-dark-100 px-2 py-0.5 rounded-full">材料摘要已注入</span>
            </div>

            <details v-if="overlayPreview.guidelines" class="rounded-xl border border-warm-300 bg-warm-50/70 p-3 hover:bg-warm-50 transition-colors">
              <summary class="text-xs font-medium text-dark-100 cursor-pointer">补充规范</summary>
              <p class="text-xs text-dark-50 mt-2 whitespace-pre-wrap">{{ overlayPreview.guidelines }}</p>
            </details>

            <details v-if="overlayPreview.principles.length" class="rounded-xl border border-warm-300 bg-warm-50/70 p-3 hover:bg-warm-50 transition-colors">
              <summary class="text-xs font-medium text-dark-100 cursor-pointer">写作准则</summary>
              <ul class="text-xs text-dark-50 mt-2 list-disc pl-4 space-y-1">
                <li v-for="(item, idx) in overlayPreview.principles" :key="`p-${idx}`">{{ item }}</li>
              </ul>
            </details>

            <details v-if="overlayPreview.sections.length" class="rounded-xl border border-warm-300 bg-warm-50/70 p-3 hover:bg-warm-50 transition-colors">
              <summary class="text-xs font-medium text-dark-100 cursor-pointer">章节补充（命中）</summary>
              <div class="mt-2 flex flex-wrap gap-2">
                <span v-for="section in overlayPreview.sections" :key="section.id" class="text-xs bg-warm-200 text-dark-100 px-2 py-0.5 rounded-full">
                  {{ section.title }}
                </span>
              </div>
            </details>

            <details v-if="overlayPreview.material" class="rounded-xl border border-warm-300 bg-warm-50/70 p-3 hover:bg-warm-50 transition-colors">
              <summary class="text-xs font-medium text-dark-100 cursor-pointer">材料摘要</summary>
              <p class="text-xs text-dark-50 mt-2 whitespace-pre-wrap">{{ overlayPreview.material }}</p>
            </details>
          </div>
        </div>

        <details v-if="externalInformation" class="rounded-2xl border border-warm-300 bg-warm-100/80 p-4 hover:bg-warm-100 transition-colors">
          <summary class="text-sm font-semibold text-dark-300 cursor-pointer">补充信息摘要</summary>
          <p class="text-xs text-dark-50 mt-3 whitespace-pre-wrap">{{ externalInformation }}</p>
        </details>
      </div>
    </section>

    <!-- Right Pane: Preview + Actions -->
    <section class="flex flex-col flex-1 min-h-0 h-full rounded-2xl border border-warm-300 bg-warm-50/80 overflow-hidden shadow-sm hover:shadow-lg transition-shadow">
      <header class="px-4 py-3 border-b border-warm-300 bg-gradient-to-b from-warm-100 to-warm-50 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-9 h-9 bg-warm-200 rounded-xl flex items-center justify-center shrink-0">
            <svg class="w-4.5 h-4.5 text-dark-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div class="min-w-0">
            <p class="font-display font-semibold text-dark-300 truncate text-sm">文档预览</p>
            <p class="text-[11px] text-dark-50 truncate">{{ skill?.name ? `Skill：${skill.name}` : '正在加载 Skill...' }}</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <button
            type="button"
            @click="startGeneration"
            :disabled="!canGenerate || isWriting"
            class="px-2.5 py-1.5 text-[11px] font-semibold rounded-lg bg-anthropic-orange text-white hover:bg-anthropic-orange-dark disabled:bg-warm-300 disabled:text-warm-500 disabled:cursor-not-allowed transition-all duration-150 flex items-center gap-2 active:scale-[0.98]"
            :title="canGenerate ? '开始生成' : '请先上传材料'"
          >
            <svg v-if="!isWriting" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <div v-else class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full spinner"></div>
            {{ isWriting ? '生成中' : '生成文档' }}
          </button>

          <button
            v-if="documentContent"
            type="button"
            @click="copyDocument"
            class="px-2.5 py-1.5 text-[11px] font-semibold rounded-lg bg-warm-200 text-dark-100 hover:bg-warm-300 transition-colors active:scale-[0.98]"
          >
            {{ copyButtonText }}
          </button>

          <div v-if="documentContent" class="relative" ref="exportDropdown">
            <button type="button" @click="showExportMenu = !showExportMenu" class="px-2.5 py-1.5 text-[11px] font-semibold rounded-lg bg-warm-200 text-dark-100 hover:bg-warm-300 transition-colors flex items-center gap-2 active:scale-[0.98]">
              导出
              <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-180': showExportMenu }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <Transition name="dropdown">
              <div v-if="showExportMenu" class="absolute right-0 mt-2 w-44 bg-warm-100 rounded-xl shadow-lg border border-warm-300 py-2 z-10">
                <button @click="exportAs('md')" class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-50 flex items-center gap-3">
                  <span class="font-mono text-xs bg-warm-200 rounded px-1.5 py-0.5">MD</span> Markdown 格式
                </button>
                <button @click="exportAs('docx')" class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-50 flex items-center gap-3">
                  <span class="font-mono text-xs bg-signal-100 text-signal-700 rounded px-1.5 py-0.5">W</span> Word 文档
                </button>
                <button @click="exportAs('pdf')" class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-50 flex items-center gap-3">
                  <span class="font-mono text-xs bg-red-900/30 text-red-300 rounded px-1.5 py-0.5">PDF</span> PDF 文档
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </header>

      <div v-if="isWriting" class="px-4 py-3 border-b border-warm-300 bg-anthropic-orange/5">
        <div class="flex items-center gap-2 mb-2">
          <div class="w-4 h-4 border-2 border-warm-300 border-t-anthropic-orange rounded-full spinner"></div>
          <span class="font-medium text-dark-300 text-sm">正在生成...</span>
        </div>
        <div v-if="writingProgress.total > 0">
          <div class="flex justify-between mb-2 text-xs text-dark-50">
            <span class="truncate">{{ currentSection || '处理中...' }}</span>
            <span class="shrink-0">{{ writingProgress.current }} / {{ writingProgress.total }}</span>
          </div>
          <div class="w-full bg-warm-200 rounded-full h-2 overflow-hidden">
            <div class="bg-gradient-to-r from-anthropic-orange to-anthropic-orange-dark h-2 rounded-full progress-bar" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <div class="mt-2 flex flex-wrap gap-2">
            <span v-for="stage in stageOrder" :key="stage" class="px-2 py-0.5 text-[11px] rounded-full border transition-colors" :class="stageBadgeClass(stageState[stage])">
              {{ stageLabels[stage] }}
            </span>
          </div>
          <p v-if="currentStageLabel" class="mt-2 text-[11px] text-dark-50">当前阶段：{{ currentStageLabel }}</p>
          <p v-if="reviewSnapshot" class="mt-1 text-[11px]" :class="reviewSnapshot.passed ? 'text-green-300' : 'text-amber-300'">
            评审分数：{{ reviewSnapshot.score ?? '-' }} · {{ reviewSnapshot.passed ? '通过' : '需要修订' }}
          </p>
        </div>
      </div>

      <div v-else-if="isPostProcessing" class="px-4 py-3 border-b border-warm-300 bg-warm-100/60">
        <div class="flex items-center gap-2">
          <div class="w-4 h-4 border-2 border-warm-300 border-t-anthropic-orange rounded-full spinner"></div>
          <span class="font-medium text-dark-300 text-sm">Document-Refiner 正在进行{{ postProcessLabel || '润色以及格式调整' }}...</span>
        </div>
        <p class="text-[11px] text-dark-50 mt-1">
          自动执行：去重（信息层面，非语义）→ 标题/字段格式整理 → 清理无关输出。仅优化展示，不新增/篡改事实。
        </p>
      </div>
      <div v-else-if="postProcessToast" class="px-4 py-2 border-b border-warm-300 bg-black/20">
        <p class="text-[11px] text-dark-50">{{ postProcessToast }}</p>
      </div>

      <div class="flex-1 min-h-0 overflow-y-auto p-6">
        <Transition name="fade" mode="out-in">
          <div v-if="documentContent" key="content" class="markdown-content prose prose-warm max-w-none" v-html="renderedDocumentDebounced"></div>
          <div v-else key="empty" class="h-full flex items-center justify-center">
            <div class="text-center max-w-sm">
              <div class="w-20 h-20 bg-warm-200 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <svg class="w-10 h-10 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p class="text-dark-100 font-semibold text-lg">还没有内容</p>
              <p class="text-sm text-warm-400 mt-2">在左侧上传材料，然后点击右上角“生成文档”。</p>
            </div>
          </div>
        </Transition>
      </div>
    </section>

    <Toast :show="toastVisible" :title="toastTitle" :message="toastMessage" @close="toastVisible = false" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { api } from '../api'
import { debounce } from '../utils/performance'
import Toast from '../components/Toast.vue'

const route = useRoute()
const skillId = computed(() => route.params.skillId)

// Core state
const skill = ref(null)
const sessionId = ref(null)
const isWriting = ref(false)
const documentContent = ref('')
const savedDocumentId = ref(null)

// Streaming progress
const currentSection = ref('')
const writingProgress = ref({ current: 0, total: 0 })
const currentStage = ref('')
const stageOrder = ['outline', 'draft', 'review', 'revise']
const stageLabels = {
  outline: '提纲生成',
  draft: '内容写作',
  review: '质量评审',
  revise: '修订完善'
}
const stageState = reactive({
  outline: 'pending',
  draft: 'pending',
  review: 'pending',
  revise: 'pending'
})
const reviewSnapshot = ref(null)
const isPostProcessing = ref(false)
const postProcessLabel = ref('')
const postProcessMeta = ref(null)
const postProcessToast = ref('')

// Session augmentation
const externalInformation = ref('')
const skillOverlay = ref(null)
const uploadedFiles = ref([])

// UI state
const fileInputRef = ref(null)
const isUploading = ref(false)
const isDragging = ref(false)
const showExportMenu = ref(false)
const exportDropdown = ref(null)
const copyButtonText = ref('复制')
const toastVisible = ref(false)
const toastTitle = ref('')
const toastMessage = ref('')
let toastTimer = null

// EventSource cleanup
const eventSourceRef = shallowRef(null)

// Render markdown (debounced)
const renderedDocumentDebounced = ref('')
const updateRenderedDocument = debounce((content) => {
  renderedDocumentDebounced.value = content ? marked(content) : ''
}, 150)
watch(documentContent, (newContent) => updateRenderedDocument(newContent), { immediate: true })

const canGenerate = computed(() => {
  if (!sessionId.value) return false
  if (isUploading.value) return false
  return uploadedFiles.value.length > 0 || !!skillOverlay.value
})

const progressPercent = computed(() => {
  if (writingProgress.value.total === 0) return 0
  return Math.round((writingProgress.value.current / writingProgress.value.total) * 100)
})

const currentStageLabel = computed(() => stageLabels[currentStage.value] || '')

const overlayStats = computed(() => {
  if (!skillOverlay.value) return { hasGuidelines: false, principles: 0, sectionCount: 0, hasMaterialContext: false }
  const guidelineText = (skillOverlay.value.writing_guidelines_additions || '').trim()
  const principles = Array.isArray(skillOverlay.value.global_principles)
    ? skillOverlay.value.global_principles.filter(item => item && item.toString().trim()).length
    : 0
  const sectionOverrides = skillOverlay.value.section_overrides || {}
  const sectionCount = typeof sectionOverrides === 'object'
    ? Object.keys(sectionOverrides).filter(key => sectionOverrides[key] && sectionOverrides[key].toString().trim()).length
    : 0
  const materialContext = (skillOverlay.value.material_context || '').trim()
  return {
    hasGuidelines: !!guidelineText,
    principles,
    sectionCount,
    hasMaterialContext: !!materialContext
  }
})

const sectionTitleMap = computed(() => {
  const map = {}
  const walk = (sections = []) => {
    sections.forEach((section) => {
      if (!section) return
      if (section.id) map[section.id] = section.title || section.id
      if (Array.isArray(section.children) && section.children.length > 0) walk(section.children)
    })
  }
  walk(skill.value?.structure || [])
  return map
})

const overlayPreview = computed(() => {
  if (!skillOverlay.value) return { guidelines: '', principles: [], sections: [], material: '' }
  const guidelines = (skillOverlay.value.writing_guidelines_additions || '').trim()
  const principles = Array.isArray(skillOverlay.value.global_principles)
    ? skillOverlay.value.global_principles.filter(item => item && item.toString().trim())
    : []
  const sectionOverrides = skillOverlay.value.section_overrides || {}
  const sections = typeof sectionOverrides === 'object'
    ? Object.entries(sectionOverrides)
      .filter(([, value]) => value && value.toString().trim())
      .map(([id]) => ({ id, title: sectionTitleMap.value[id] || id }))
    : []
  const material = (skillOverlay.value.material_context || '').trim()
  return { guidelines, principles, sections, material }
})

const showToast = (title, message) => {
  toastTitle.value = title
  toastMessage.value = message
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 2600)
}

const notifyModelNotConfigured = (error) => {
  const detail = error?.response?.data?.detail
  if (detail === '模型未配置') {
    showToast('模型未配置', '请先在设置中配置模型。')
    return true
  }
  return false
}

const resetStageState = () => {
  stageOrder.forEach((stage) => { stageState[stage] = 'pending' })
  currentStage.value = ''
  reviewSnapshot.value = null
}

const stageBadgeClass = (status) => {
  if (status === 'active') return 'bg-anthropic-orange/10 border-anthropic-orange text-anthropic-orange-dark'
  if (status === 'done') return 'bg-green-900/30 border-green-500/40 text-green-300'
  if (status === 'skipped') return 'bg-warm-100 border-warm-200 text-warm-400'
  return 'bg-warm-50 border-warm-200 text-warm-400'
}

const setStageStart = (stage) => {
  stageOrder.forEach((key) => {
    if (stageState[key] === 'active') stageState[key] = 'done'
  })
  stageState[stage] = 'active'
  currentStage.value = stage
}

const setStageComplete = (stage, willRevise) => {
  stageState[stage] = 'done'
  if (stage === 'review' && !willRevise) stageState.revise = 'skipped'
  if (currentStage.value === stage) currentStage.value = ''
}

const getDocumentTitle = () => {
  const base = skill.value?.name || '文档'
  const stamp = new Date().toISOString().slice(0, 10)
  return `${base} ${stamp}`
}

const saveDocument = async () => {
  if (!documentContent.value || !sessionId.value) return
  try {
    if (savedDocumentId.value) {
      await api.put(`/documents/${savedDocumentId.value}`, { content: documentContent.value })
    } else {
      const response = await api.post('/documents/', {
        title: getDocumentTitle(),
        skill_id: skillId.value,
        content: documentContent.value,
        session_id: sessionId.value
      })
      savedDocumentId.value = response.data.id
    }
  } catch (e) {
    console.error('Failed to save document:', e)
  }
}

const fetchSkill = async () => {
  try {
    const response = await api.get(`/skills/${skillId.value}`)
    skill.value = response.data
  } catch (e) {
    console.error('Failed to fetch skill:', e)
  }
}

const fetchSessionMeta = async () => {
  if (!sessionId.value) return
  try {
    const response = await api.get(`/chat/session/${sessionId.value}/requirements`)
    externalInformation.value = response.data.external_information || ''
    skillOverlay.value = response.data.skill_overlay || null
  } catch (e) {
    console.error('Failed to fetch session meta:', e)
  }
}

const fetchSessionFiles = async () => {
  if (!sessionId.value) return
  try {
    const response = await api.get(`/chat/session/${sessionId.value}/files`)
    const files = response.data.files || []
    uploadedFiles.value = files.map((file) => ({
      name: file.filename,
      extractedCount: file.extracted_fields ? Object.keys(file.extracted_fields).length : 0
    }))
    if (response.data.external_information) externalInformation.value = response.data.external_information
  } catch (e) {
    console.error('Failed to fetch session files:', e)
  }
}

const startSession = async () => {
  try {
    const response = await api.post('/chat/start', { skill_id: skillId.value })
    sessionId.value = response.data.session_id
    savedDocumentId.value = null
    skillOverlay.value = null
    await fetchSessionMeta()
    await fetchSessionFiles()
  } catch (e) {
    if (notifyModelNotConfigured(e)) return
    console.error('Failed to start session:', e)
    alert(e.response?.data?.detail || '启动会话失败。')
  }
}

const startGeneration = async () => {
  if (!sessionId.value || isWriting.value) return
  try {
    const response = await api.post(`/chat/session/${sessionId.value}/start-generation`)
    if (!response.data.success) {
      showToast('无法生成', response.data.message || '请先补充信息后再生成。')
      return
    }
    await startStreamGeneration()
  } catch (e) {
    console.error('Failed to start generation:', e)
    if (notifyModelNotConfigured(e)) return
    showToast('启动失败', e.response?.data?.detail || '启动生成失败，请重试。')
  }
}

const startStreamGeneration = async () => {
  isWriting.value = true
  documentContent.value = ''
  writingProgress.value = { current: 0, total: 0 }
  resetStageState()
  isPostProcessing.value = false
  postProcessLabel.value = ''

  try {
    const eventSource = new EventSource(`/api/chat/generate/${sessionId.value}/stream`)
    eventSourceRef.value = eventSource

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      switch (data.type) {
        case 'start':
          writingProgress.value.total = data.total_sections
          break
        case 'section_start': {
          currentSection.value = data.section_title
          writingProgress.value.current = data.section_index
          resetStageState()
          if (documentContent.value && !documentContent.value.endsWith('\n\n')) documentContent.value += '\n\n'
          const level = data.section_level || 1
          const heading = '#'.repeat(level) + ' ' + data.section_title
          documentContent.value += heading + '\n\n'
          break
        }
        case 'stage_start':
          setStageStart(data.stage)
          break
        case 'stage_complete':
          setStageComplete(data.stage, data.will_revise)
          if (data.stage === 'review') reviewSnapshot.value = { score: data.score, passed: data.passed }
          break
        case 'chunk':
          documentContent.value += data.content
          break
        case 'complete':
          isWriting.value = false
          isPostProcessing.value = false
          currentSection.value = ''
          resetStageState()
          documentContent.value = data.document
          closeEventSource()
          saveDocument()
          break
        case 'error':
          isWriting.value = false
          isPostProcessing.value = false
          resetStageState()
          closeEventSource()
          showToast('生成失败', data.error || '未知错误')
          break

        case 'postprocess_start':
          isPostProcessing.value = true
          postProcessLabel.value = data.name || '润色以及格式调整'
          postProcessMeta.value = null
          postProcessToast.value = ''
          break

        case 'postprocess_complete':
          isPostProcessing.value = false
          postProcessLabel.value = ''
          postProcessMeta.value = data.meta || null
          if (postProcessMeta.value && typeof postProcessMeta.value === 'object') {
            const preRemoved = postProcessMeta.value?.dedupe_pre?.removed
            const postRemoved = postProcessMeta.value?.dedupe_post?.removed
            const pieces = []
            if (typeof preRemoved === 'number') pieces.push(`预去重移除 ${preRemoved} 块`)
            if (typeof postRemoved === 'number') pieces.push(`后去重移除 ${postRemoved} 块`)
            const reason = postProcessMeta.value?.reason
            if (reason) pieces.push(`结果：${reason}`)
            postProcessToast.value = pieces.join(' · ')
          }
          break
      }
    }

    eventSource.onerror = () => {
      isWriting.value = false
      resetStageState()
      closeEventSource()
      showToast('连接中断', '流式生成连接已断开，请重试。')
    }
  } catch (e) {
    console.error('Failed to start stream generation:', e)
    isWriting.value = false
    showToast('启动失败', '无法建立流式连接。')
  }
}

const closeEventSource = () => {
  if (eventSourceRef.value) {
    eventSourceRef.value.close()
    eventSourceRef.value = null
  }
}

const triggerFileUpload = () => { fileInputRef.value?.click() }

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  if (files.length > 0) uploadFiles(files)
  event.target.value = ''
}

const handleDrop = (event) => {
  isDragging.value = false
  const files = Array.from(event.dataTransfer.files)
  if (files.length > 0) uploadFiles(files)
}

const readFileAsBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result || ''
      const resultString = typeof result === 'string' ? result : ''
      const commaIndex = resultString.indexOf(',')
      const base64 = commaIndex >= 0 ? resultString.slice(commaIndex + 1) : resultString
      resolve({ filename: file.name, content_base64: base64, content_type: file.type || '' })
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const uploadFilesMultipart = async (files) => {
  const formDataUpload = new FormData()
  files.forEach(file => formDataUpload.append('files', file))
  // 不要手动设置 Content-Type，让浏览器自动带上 boundary，避免后端解析失败
  return await api.post(`/chat/session/${sessionId.value}/upload`, formDataUpload, { timeout: 300000 })
}

const uploadFilesJson = async (files) => {
  const payloadFiles = await Promise.all(files.map(readFileAsBase64))
  return await api.post(`/chat/session/${sessionId.value}/upload-json`, { files: payloadFiles }, { timeout: 300000 })
}

const uploadFiles = async (files) => {
  if (!sessionId.value || files.length === 0) return
  if (isUploading.value) return
  isUploading.value = true
  try {
    let response = null

    // 优先 multipart：避免 base64 JSON 体积膨胀导致 413/超时
    try {
      response = await uploadFilesMultipart(files)
    } catch (multipartError) {
      const status = multipartError.response?.status
      // 只有后端未注册 multipart 路由时（404）才回退 JSON；其余错误直接抛出，避免重复上传/重复提取
      if (status === 404) {
        response = await uploadFilesJson(files)
      } else {
        throw multipartError
      }
    }

    const result = response.data
    if (!result.success) {
      const details = Array.isArray(result.file_results) ? result.file_results.join('\n') : ''
      showToast('处理失败', [result.message || '文件处理失败', details].filter(Boolean).join('\n'))
      return
    }

    if (result.warning) {
      const llmLine = result.llm_used
        ? `LLM：${result.llm_used.provider_name || result.llm_used.provider || 'unknown'} · ${result.llm_used.model || ''}`.trim()
        : ''
      const timeLine = typeof result.extraction_ms === 'number' ? `提取耗时：${Math.round(result.extraction_ms / 1000)}s` : ''
      showToast('已上传', [result.warning, llmLine, timeLine].filter(Boolean).join('\n'))
    }
    if (result.external_information) externalInformation.value = result.external_information
    await fetchSessionFiles()
    await fetchSessionMeta()
  } catch (e) {
    console.error('File upload failed:', e)
    if (notifyModelNotConfigured(e)) return
    if (e.response?.status === 400 && typeof e.response?.data?.detail === 'string' && e.response.data.detail.includes('Cannot upload files in phase:')) {
      showToast('无法上传', '上传仅支持在需求收集阶段；正在生成/已完成时请新建会话再上传。')
      return
    }
    if (e.response?.status === 413) {
      showToast('上传失败', '文件过大或请求体超限（413）。建议使用更小的文件，或联系我把上传改为分片上传。')
      return
    }
    showToast('上传失败', e.response?.data?.detail || e.message || '文件上传失败')
  } finally {
    isUploading.value = false
  }
}

const copyDocument = async () => {
  if (!documentContent.value) return
  await navigator.clipboard.writeText(documentContent.value)
  copyButtonText.value = '已复制'
  setTimeout(() => { copyButtonText.value = '复制' }, 2000)
}

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = window.document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const exportAs = async (format) => {
  showExportMenu.value = false
  if (!documentContent.value) return

  const filename = skill.value?.name || '文档'

  if (format === 'md') {
    const blob = new Blob([documentContent.value], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `${filename}.md`)
    return
  }

  try {
    const response = await api.post('/documents/export', {
      content: documentContent.value,
      format,
      filename
    }, { responseType: 'blob' })

    const contentType = format === 'docx'
      ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      : 'application/pdf'
    const blob = new Blob([response.data], { type: contentType })
    downloadBlob(blob, `${filename}.${format}`)
  } catch (e) {
    console.error('Export failed:', e)
    showToast('导出失败', `导出 ${format.toUpperCase()} 失败。`)
  }
}

const handleClickOutside = (event) => {
  if (exportDropdown.value && !exportDropdown.value.contains(event.target)) showExportMenu.value = false
}

onMounted(async () => {
  await fetchSkill()
  await startSession()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  closeEventSource()
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
.border-3 { border-width: 3px; }

.spinner { animation: spin 0.8s linear infinite; }
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-bar { transition: width 0.3s ease-out; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.dropdown-enter-active { animation: dropdown-in 0.15s ease-out; }
.dropdown-leave-active { animation: dropdown-out 0.1s ease-in; }

@keyframes dropdown-in {
  from { opacity: 0; transform: translateY(-6px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes dropdown-out {
  from { opacity: 1; transform: translateY(0) scale(1); }
  to { opacity: 0; transform: translateY(-6px) scale(0.95); }
}

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

.markdown-content :deep(a) { color: #E36A3A; }
.markdown-content :deep(a:hover) { color: #F0A384; }

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
