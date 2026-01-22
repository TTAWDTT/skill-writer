<template>
  <div class="flex h-[calc(100vh-110px)] gap-6">
    <!-- Left: Requirements Panel -->
    <div class="w-1/2 flex flex-col gap-4 min-h-0">
      <!-- Top: File Upload Area -->
      <div class="bg-warm-50 rounded-2xl border border-warm-300 p-5 max-h-[260px] overflow-y-auto">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <h3 class="font-semibold text-dark-300">Upload Materials</h3>
            <p class="text-xs text-dark-50">Upload files to auto-fill requirements</p>
          </div>
        </div>

        <!-- Upload Zone -->
        <div
          class="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200"
          :class="isDragging ? 'border-anthropic-orange bg-anthropic-orange/5' : 'border-warm-300 hover:border-anthropic-orange hover:bg-warm-100'"
          @click="triggerFileUpload"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <input ref="fileInputRef" type="file" multiple accept=".md,.txt,.doc,.docx,.pdf,.pptx" class="hidden" @change="handleFileSelect" />

          <div v-if="isUploading" class="flex flex-col items-center">
            <div class="w-12 h-12 border-3 border-warm-300 border-t-anthropic-orange rounded-full spinner mb-3"></div>
            <p class="text-dark-100 font-medium">Extracting information...</p>
            <p class="text-xs text-dark-50 mt-1">Please wait</p>
          </div>

          <div v-else>
            <svg class="w-10 h-10 mx-auto text-warm-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p class="text-dark-100 font-medium">Drag & drop files here</p>
            <p class="text-sm text-dark-50 mt-1">or click to browse</p>
            <p class="text-xs text-warm-400 mt-3">Supports: .md, .txt, .doc, .docx, .pdf, .pptx</p>
          </div>
        </div>

        <!-- Uploaded Files List -->
        <div v-if="uploadedFiles.length > 0" class="mt-4 space-y-2 max-h-28 overflow-y-auto">
          <p class="text-xs font-medium text-dark-100 mb-2">Uploaded Files:</p>
          <div v-for="(file, index) in uploadedFiles" :key="index" class="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg">
            <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="flex-1 text-sm text-dark-300 truncate">{{ file.name }}</span>
            <span class="text-xs text-green-600">{{ file.extractedCount }} fields extracted</span>
          </div>
        </div>

        <!-- External Information -->
        <div v-if="externalInformation" class="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <div class="flex items-center gap-2 mb-2">
            <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-sm font-medium text-blue-700">Additional Information Extracted</span>
          </div>
          <p class="text-xs text-blue-600 leading-relaxed line-clamp-4">{{ externalInformation }}</p>
        </div>

        <!-- Skill Fixer Status -->
        <div v-if="skillOverlay" class="mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div class="flex items-center gap-2 mb-2">
            <svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-sm font-medium text-emerald-700">Skill-fixer 已应用</span>
          </div>
          <p class="text-xs text-emerald-700">已基于上传材料补充写作规范与章节提示，仅对本次会话生效。</p>
          <div v-if="overlayStats" class="mt-2 flex flex-wrap gap-2">
            <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
              补充规范：{{ overlayStats.hasGuidelines ? '有' : '无' }}
            </span>
            <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
              写作准则：{{ overlayStats.principles }} 条
            </span>
            <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
              章节补充：{{ overlayStats.sectionCount }} 个
            </span>
            <span v-if="overlayStats.hasMaterialContext" class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
              材料摘要：已注入
            </span>
            <span v-if="overlayStats.relaxRequirements" class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
              必填限制：已解除
            </span>
          </div>
        </div>
      </div>

      <!-- Bottom: Requirements Form -->
      <div class="flex-1 bg-warm-50 rounded-2xl border border-warm-300 flex flex-col overflow-hidden min-h-0">
        <!-- Form Header -->
        <div class="px-5 py-3 border-b border-warm-300 bg-warm-100 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gradient-to-br from-anthropic-orange to-anthropic-orange-dark rounded-xl flex items-center justify-center">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div>
              <h3 class="font-semibold text-dark-300">{{ skill?.name || 'Requirements' }}</h3>
              <p class="text-xs text-dark-50">Complete required fields. Optional and inferred fields improve quality.</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-sm px-3 py-1.5 rounded-full font-medium" :class="completionBadgeClass">
              {{ filledFieldsCount }}/{{ totalFieldsCount }} completed
            </span>
          </div>
        </div>

        <!-- Requirements Tables -->
        <div class="flex-1 overflow-y-auto p-5">
          <div v-if="totalFieldsCountAll === 0" class="text-center text-sm text-dark-50 py-10">
            No requirement fields defined for this skill.
          </div>
          <div v-else class="space-y-5">
            <div v-for="group in fieldGroups" :key="group.key">
              <div class="flex items-center justify-between mb-2">
                <div>
                  <p class="text-sm font-semibold text-dark-300">{{ group.label }}</p>
                  <p class="text-xs text-dark-50">{{ group.description }}</p>
                </div>
                <span class="text-xs font-medium px-2.5 py-1 rounded-full" :class="group.badgeClass">
                  {{ group.fields.length }}
                </span>
              </div>
              <div v-if="group.fields.length === 0" class="text-xs text-warm-400 py-4 text-center border border-dashed border-warm-300 rounded-xl">
                No fields in this group.
              </div>
              <div v-else class="overflow-hidden rounded-xl border border-warm-300 bg-white">
                <table class="w-full text-sm">
                  <thead class="bg-warm-100 text-dark-50">
                    <tr>
                      <th class="text-left px-4 py-3 font-medium">{{ group.tableLabel }}</th>
                      <th class="text-left px-4 py-3 font-medium w-2/3">Value</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-warm-200">
                    <tr v-for="field in group.fields" :key="field.id" class="align-top">
                      <td class="px-4 py-3">
                        <div class="flex flex-wrap items-center gap-2">
                          <div class="font-medium text-dark-300">{{ field.name }}</div>
                          <span class="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full" :class="priorityBadgeClass(field)">
                            {{ priorityLabel(field) }}
                          </span>
                          <span v-if="field.collection === 'infer'" class="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                            Inferred
                          </span>
                        </div>
                        <p v-if="field.description" class="text-xs text-dark-50 mt-1">{{ field.description }}</p>
                        <p v-if="field.example" class="text-xs text-warm-400 mt-2">Example: {{ field.example }}</p>
                        <span v-if="extractedFields[field.id]" class="mt-2 inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                          </svg>
                          Auto-filled
                        </span>
                      </td>
                      <td class="px-4 py-3">
                        <div class="flex gap-3" :class="isTextareaField(field) ? 'items-start' : 'items-center'">
                          <textarea
                            v-if="isTextareaField(field)"
                            v-model="formData[field.id]"
                            :placeholder="field.placeholder || 'Enter ' + field.name.toLowerCase() + '...'"
                            rows="4"
                            class="flex-1 px-4 py-3 bg-white border border-warm-300 rounded-xl text-sm text-dark-300 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent resize-none transition-all"
                          ></textarea>
                          <input
                            v-else
                            v-model="formData[field.id]"
                            :type="field.type === 'number' ? 'number' : 'text'"
                            :placeholder="field.placeholder || 'Enter ' + field.name.toLowerCase() + '...'"
                            class="flex-1 px-4 py-3 bg-white border border-warm-300 rounded-xl text-sm text-dark-300 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent transition-all"
                          />
                          <button
                            type="button"
                            @click="generateField(field)"
                            :disabled="!canAutoGenerate || isGeneratingField(field.id)"
                            class="shrink-0 px-3 py-2 text-xs font-medium rounded-lg border border-warm-300 bg-warm-100 text-dark-100 hover:bg-warm-200 disabled:bg-warm-200 disabled:text-warm-500 disabled:cursor-not-allowed transition-all"
                          >
                            {{ isGeneratingField(field.id) ? '生成中...' : 'AI生成' }}
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <!-- Generate Button -->
        <div class="p-4 border-t border-warm-300 bg-warm-100">
          <button
            @click="startGeneration"
            :disabled="!canGenerate || isWriting"
            class="w-full py-3 bg-gradient-to-r from-anthropic-orange to-anthropic-orange-dark text-white rounded-xl font-semibold text-base hover:shadow-lg disabled:from-warm-300 disabled:to-warm-400 disabled:text-warm-500 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-3"
          >
            <svg v-if="!isWriting" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <div v-else class="w-6 h-6 border-3 border-white/30 border-t-white rounded-full spinner"></div>
            {{ isWriting ? 'Generating Document...' : 'Generate Document' }}
          </button>
          <p v-if="!canGenerate && !isWriting" class="text-xs text-warm-400 text-center mt-2">
            Please fill all required fields to continue
          </p>
        </div>
      </div>
    </div>

    <!-- Right: Document Preview -->
    <div class="w-1/2 flex flex-col bg-warm-50 rounded-2xl border border-warm-300 overflow-hidden min-h-0">
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
        <Transition name="fade">
          <div v-if="documentContent" class="flex gap-2">
            <button @click="copyDocument" class="px-4 py-2 text-sm bg-warm-200 text-dark-100 rounded-xl hover:bg-warm-300 transition-all font-medium">
              {{ copyButtonText }}
            </button>
            <div class="relative" ref="exportDropdown">
              <button @click="showExportMenu = !showExportMenu" class="px-4 py-2 text-sm bg-anthropic-orange text-white rounded-xl hover:bg-anthropic-orange-dark transition-all font-medium flex items-center gap-2">
                Export
                <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-180': showExportMenu }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              <Transition name="dropdown">
                <div v-if="showExportMenu" class="absolute right-0 mt-2 w-40 bg-white rounded-xl shadow-lg border border-warm-300 py-2 z-10">
                  <button @click="exportAs('md')" class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-100 flex items-center gap-3">
                    <span class="font-mono text-xs bg-warm-200 rounded px-1.5 py-0.5">MD</span> Markdown
                  </button>
                  <button @click="exportAs('docx')" class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-100 flex items-center gap-3">
                    <span class="font-mono text-xs bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">W</span> Word
                  </button>
                  <button @click="exportAs('pdf')" class="w-full px-4 py-2 text-left text-sm text-dark-300 hover:bg-warm-100 flex items-center gap-3">
                    <span class="font-mono text-xs bg-red-100 text-red-700 rounded px-1.5 py-0.5">PDF</span> PDF
                  </button>
                </div>
              </Transition>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Writing Progress -->
      <Transition name="fade">
        <div v-if="isWriting" class="px-6 py-4 bg-anthropic-orange/5 border-b border-anthropic-orange/20">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-5 h-5 border-2 border-warm-300 border-t-anthropic-orange rounded-full spinner"></div>
            <span class="font-medium text-dark-300">Generating document...</span>
          </div>
          <div v-if="writingProgress.total > 0">
            <div class="flex justify-between mb-2 text-sm text-dark-50">
              <span>{{ currentSection || 'Processing...' }}</span>
              <span>{{ writingProgress.current }} / {{ writingProgress.total }}</span>
            </div>
            <div class="w-full bg-warm-200 rounded-full h-2 overflow-hidden">
              <div class="bg-gradient-to-r from-anthropic-orange to-anthropic-orange-dark h-2 rounded-full progress-bar" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <span
                v-for="stage in stageOrder"
                :key="stage"
                class="px-2.5 py-1 text-xs rounded-full border transition-colors"
                :class="stageBadgeClass(stageState[stage])"
              >
                {{ stageLabels[stage] }}
              </span>
            </div>
            <p v-if="currentStageLabel" class="mt-2 text-xs text-dark-50">
              Now: {{ currentStageLabel }}
            </p>
            <p v-if="reviewSnapshot" class="mt-1 text-xs" :class="reviewSnapshot.passed ? 'text-green-700' : 'text-amber-700'">
              Review score: {{ reviewSnapshot.score ?? '-' }} · {{ reviewSnapshot.passed ? 'Pass' : 'Needs revision' }}
            </p>
          </div>
        </div>
      </Transition>

      <!-- Preview Content -->
      <div class="flex-1 overflow-y-auto p-6">
        <Transition name="fade" mode="out-in">
          <div v-if="documentContent" key="content" class="markdown-content prose prose-warm max-w-none" v-html="renderedDocumentDebounced"></div>
          <div v-else key="empty" class="h-full flex items-center justify-center">
            <div class="text-center">
              <div class="w-20 h-20 bg-warm-200 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <svg class="w-10 h-10 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p class="text-dark-100 font-semibold text-lg">Document Preview</p>
              <p class="text-sm text-warm-400 mt-2">Fill in the requirements and click<br>"Generate Document" to preview</p>
            </div>
          </div>
        </Transition>
      </div>
    </div>
    <Toast
      :show="toastVisible"
      :title="toastTitle"
      :message="toastMessage"
      @close="toastVisible = false"
    />
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

// State
const skill = ref(null)
const sessionId = ref(null)
const isWriting = ref(false)
const isComplete = ref(false)
const documentContent = ref('')
const currentSection = ref('')
const writingProgress = ref({ current: 0, total: 0 })
const currentStage = ref('')
const stageOrder = ['outline', 'draft', 'review', 'revise']
const stageLabels = {
  outline: 'Outline',
  draft: 'Draft',
  review: 'Review',
  revise: 'Revise'
}
const stageState = reactive({
  outline: 'pending',
  draft: 'pending',
  review: 'pending',
  revise: 'pending'
})
const reviewSnapshot = ref(null)
const showExportMenu = ref(false)
const exportDropdown = ref(null)
const copyButtonText = ref('Copy')
const savedDocumentId = ref(null)

// Requirements form state
const requirementFields = ref([])
const formData = reactive({})
const extractedFields = ref({})
const externalInformation = ref('')
const skillOverlay = ref(null)

// File upload state
const fileInputRef = ref(null)
const isUploading = ref(false)
const isDragging = ref(false)
const uploadedFiles = ref([])
const generatingFields = reactive({})

// Store EventSource reference for cleanup
const eventSourceRef = shallowRef(null)
const toastVisible = ref(false)
const toastTitle = ref('')
const toastMessage = ref('')
let toastTimer = null

// Debounced rendered document
const renderedDocumentDebounced = ref('')
const updateRenderedDocument = debounce((content) => {
  if (!content) {
    renderedDocumentDebounced.value = ''
    return
  }
  renderedDocumentDebounced.value = marked(content)
}, 150)

watch(documentContent, (newContent) => {
  updateRenderedDocument(newContent)
}, { immediate: true })

const getFieldCollection = (field) => {
  return field.collection || (field.required ? 'required' : 'optional')
}

const getFieldPriority = (field) => {
  const value = Number(field.priority)
  return [1, 2, 3].includes(value) ? value : 3
}

const priorityLabel = (field) => {
  return `P${getFieldPriority(field)}`
}

const priorityBadgeClass = (field) => {
  const priority = getFieldPriority(field)
  if (priority === 1) return 'bg-red-100 text-red-700'
  if (priority === 2) return 'bg-yellow-100 text-yellow-700'
  return 'bg-warm-200 text-dark-50'
}

const sortFields = (fields) => {
  return [...fields].sort((a, b) => {
    const priorityDiff = getFieldPriority(a) - getFieldPriority(b)
    if (priorityDiff !== 0) return priorityDiff
    return (a.name || '').localeCompare(b.name || '')
  })
}

// Computed
const requiredFields = computed(() => (
  sortFields(requirementFields.value.filter(field => getFieldCollection(field) === 'required'))
))

const optionalFields = computed(() => (
  sortFields(requirementFields.value.filter(field => getFieldCollection(field) === 'optional'))
))

const inferFields = computed(() => (
  sortFields(requirementFields.value.filter(field => getFieldCollection(field) === 'infer'))
))

const fieldGroups = computed(() => ([
  {
    key: 'required',
    label: 'Required Fields',
    tableLabel: 'Required Field',
    description: 'Must be completed before generation.',
    badgeClass: 'bg-red-100 text-red-700',
    fields: requiredFields.value
  },
  {
    key: 'optional',
    label: 'Optional Fields',
    tableLabel: 'Optional Field',
    description: 'Optional but improves quality.',
    badgeClass: 'bg-warm-200 text-dark-50',
    fields: optionalFields.value
  },
  {
    key: 'infer',
    label: 'Infer From Materials',
    tableLabel: 'Inferred Field',
    description: 'Prefer extracted from uploaded materials.',
    badgeClass: 'bg-blue-100 text-blue-700',
    fields: inferFields.value
  }
]))

const filledFieldsCount = computed(() => {
  return requiredFields.value.filter(f => {
    const val = formData[f.id]
    return val && val.toString().trim()
  }).length
})

const totalFieldsCount = computed(() => requiredFields.value.length)

const totalFieldsCountAll = computed(() => requirementFields.value.length)

const completionBadgeClass = computed(() => {
  const ratio = totalFieldsCount.value > 0 ? filledFieldsCount.value / totalFieldsCount.value : 0
  if (ratio >= 1) return 'bg-green-100 text-green-700'
  if (ratio >= 0.5) return 'bg-yellow-100 text-yellow-700'
  return 'bg-warm-200 text-dark-100'
})

const canGenerate = computed(() => {
  return requiredFields.value.every(f => {
    const val = formData[f.id]
    return val && val.toString().trim()
  })
})

const canAutoGenerate = computed(() => {
  return !!sessionId.value && uploadedFiles.value.length > 0
})

const progressPercent = computed(() => {
  if (writingProgress.value.total === 0) return 0
  return Math.round(writingProgress.value.current / writingProgress.value.total * 100)
})

const currentStageLabel = computed(() => stageLabels[currentStage.value] || '')

const overlayStats = computed(() => {
  if (!skillOverlay.value) return null
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
    relaxRequirements: !!skillOverlay.value.relax_requirements,
    hasMaterialContext: !!materialContext,
  }
})

const isTextareaField = (field) => {
  return field.type === 'textarea' || (field.description && field.description.length > 50)
}

const resetStageState = () => {
  stageOrder.forEach((stage) => {
    stageState[stage] = 'pending'
  })
  currentStage.value = ''
  reviewSnapshot.value = null
}

const stageBadgeClass = (status) => {
  if (status === 'active') return 'bg-anthropic-orange/10 border-anthropic-orange text-anthropic-orange-dark'
  if (status === 'done') return 'bg-green-50 border-green-200 text-green-700'
  if (status === 'skipped') return 'bg-warm-100 border-warm-200 text-warm-400'
  return 'bg-warm-50 border-warm-200 text-warm-400'
}

const setStageStart = (stage) => {
  stageOrder.forEach((key) => {
    if (stageState[key] === 'active') {
      stageState[key] = 'done'
    }
  })
  stageState[stage] = 'active'
  currentStage.value = stage
}

const setStageComplete = (stage, willRevise) => {
  stageState[stage] = 'done'
  if (stage === 'review' && !willRevise) {
    stageState.revise = 'skipped'
  }
  if (currentStage.value === stage) {
    currentStage.value = ''
  }
}

const getDocumentTitle = () => {
  const candidates = [
    formData.title,
    formData.project_title,
    formData.project_name,
    formData.name
  ]
  const matched = candidates.find((value) => value && value.toString().trim())
  if (matched) return matched.toString().trim()

  const base = skill.value?.name || 'Document'
  const stamp = new Date().toISOString().slice(0, 10)
  return `${base} ${stamp}`
}

const saveDocument = async () => {
  if (!documentContent.value || !sessionId.value) return

  try {
    if (savedDocumentId.value) {
      await api.put(`/documents/${savedDocumentId.value}`, {
        content: documentContent.value
      })
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

const showToast = (title, message) => {
  toastTitle.value = title
  toastMessage.value = message
  toastVisible.value = true
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, 2600)
}

const notifyModelNotConfigured = (error) => {
  const detail = error?.response?.data?.detail
  if (detail === '模型未配置') {
    showToast('模型未配置', '请先在设置中配置模型。')
    return true
  }
  return false
}

// Methods
const fetchSkill = async () => {
  try {
    const response = await api.get(`/skills/${skillId.value}`)
    skill.value = response.data
  } catch (e) {
    console.error('Failed to fetch skill:', e)
  }
}

const startSession = async () => {
  try {
    const response = await api.post('/chat/start', {
      skill_id: skillId.value
    })
    sessionId.value = response.data.session_id
    savedDocumentId.value = null
    skillOverlay.value = null
    await fetchRequirements()
    await fetchSessionFiles()
  } catch (e) {
    if (notifyModelNotConfigured(e)) return
    console.error('Failed to start session:', e)
    alert(e.response?.data?.detail || 'Failed to start session.')
  }
}

const fetchRequirements = async () => {
  if (!sessionId.value) return

  try {
    const response = await api.get(`/chat/session/${sessionId.value}/requirements`)
    applyRequirementsPayload(response.data)
  } catch (e) {
    try {
      const fallback = await api.get(`/skills/${skillId.value}/requirements`)
      applyRequirementsPayload({
        fields: fallback.data.fields || [],
        requirements: {},
        external_information: '',
      })
    } catch (fallbackError) {
      console.error('Failed to fetch requirements:', fallbackError)
    }
  }
}

const fetchSessionFiles = async () => {
  if (!sessionId.value) return

  try {
    const response = await api.get(`/chat/session/${sessionId.value}/files`)
    const files = response.data.files || []
    uploadedFiles.value = files.map((file) => ({
      name: file.filename,
      extractedCount: file.extracted_fields ? Object.keys(file.extracted_fields).length : 0,
    }))

    if (response.data.external_information) {
      externalInformation.value = response.data.external_information
    }
  } catch (e) {
    console.error('Failed to fetch session files:', e)
  }
}

// Save form data to server (debounced)
const saveRequirementsDebounced = debounce(async () => {
  if (!sessionId.value) return
  try {
    await api.put(`/chat/session/${sessionId.value}/requirements`, {
      requirements: { ...formData }
    })
  } catch (e) {
    console.error('Failed to save requirements:', e)
  }
}, 500)

watch(formData, () => {
  saveRequirementsDebounced()
}, { deep: true })

const isGeneratingField = (fieldId) => {
  return !!generatingFields[fieldId]
}

const generateField = async (field) => {
  if (!sessionId.value || !canAutoGenerate.value || isGeneratingField(field.id)) return

  generatingFields[field.id] = true
  try {
    const response = await api.post(`/chat/session/${sessionId.value}/generate-field`, {
      field_id: field.id
    })

    if (response.data.success) {
      formData[field.id] = response.data.value ?? ''
    } else {
      alert(response.data.message || 'AI 生成失败')
    }
  } catch (e) {
    console.error('AI generate failed:', e)
    if (notifyModelNotConfigured(e)) return
    alert(e.response?.data?.detail || 'AI 生成失败')
  } finally {
    generatingFields[field.id] = false
  }
}

const startGeneration = async () => {
  if (!canGenerate.value || isWriting.value) return

  try {
    await api.put(`/chat/session/${sessionId.value}/requirements`, {
      requirements: { ...formData }
    })

    const response = await api.post(`/chat/session/${sessionId.value}/start-generation`)

    if (!response.data.success) {
      alert(response.data.message)
      return
    }

    await startStreamGeneration()

  } catch (e) {
    console.error('Failed to start generation:', e)
    if (notifyModelNotConfigured(e)) return
    alert(e.response?.data?.detail || 'Failed to start generation. Please try again.')
  }
}

const startStreamGeneration = async () => {
  isWriting.value = true
  documentContent.value = ''
  writingProgress.value = { current: 0, total: 0 }
  resetStageState()

  try {
    const eventSource = new EventSource(`/api/chat/generate/${sessionId.value}/stream`)
    eventSourceRef.value = eventSource

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'start':
          writingProgress.value.total = data.total_sections
          break

        case 'section_start':
          currentSection.value = data.section_title
          writingProgress.value.current = data.section_index
          resetStageState()
          if (documentContent.value && !documentContent.value.endsWith('\n\n')) {
            documentContent.value += '\n\n'
          }
          const level = data.section_level || 1
          const heading = '#'.repeat(level) + ' ' + data.section_title
          documentContent.value += heading + '\n\n'
          break

        case 'stage_start':
          setStageStart(data.stage)
          break

        case 'stage_complete':
          setStageComplete(data.stage, data.will_revise)
          if (data.stage === 'review') {
            reviewSnapshot.value = {
              score: data.score,
              passed: data.passed
            }
          }
          break

        case 'chunk':
          documentContent.value += data.content
          break

        case 'complete':
          isWriting.value = false
          isComplete.value = true
          currentSection.value = ''
          resetStageState()
          documentContent.value = data.document
          closeEventSource()
          saveDocument()
          break

        case 'error':
          isWriting.value = false
          resetStageState()
          closeEventSource()
          alert(`Generation failed: ${data.error}`)
          break
      }
    }

    eventSource.onerror = () => {
      isWriting.value = false
      resetStageState()
      closeEventSource()
    }

  } catch (e) {
    console.error('Failed to start generation:', e)
    isWriting.value = false
  }
}

const closeEventSource = () => {
  if (eventSourceRef.value) {
    eventSourceRef.value.close()
    eventSourceRef.value = null
  }
}

// File upload methods
const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  if (files.length > 0) {
    uploadFiles(files)
  }
  event.target.value = ''
}

const handleDrop = (event) => {
  isDragging.value = false
  const files = Array.from(event.dataTransfer.files)
  if (files.length > 0) {
    uploadFiles(files)
  }
}

const uploadFiles = async (files) => {
  if (!sessionId.value || files.length === 0) return

  isUploading.value = true

  try {
    const payloadFiles = await Promise.all(files.map(readFileAsBase64))
    let response = null

    try {
      response = await api.post(`/chat/session/${sessionId.value}/upload-json`, {
        files: payloadFiles
      })
    } catch (jsonError) {
      if (jsonError.response?.status === 404) {
        const formDataUpload = new FormData()
        files.forEach(file => {
          formDataUpload.append('files', file)
        })
        response = await api.post(`/chat/session/${sessionId.value}/upload`, formDataUpload, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } else {
        throw jsonError
      }
    }

    const result = response.data

    if (result.success) {
      const extracted = result.extracted_fields || {}
      const fieldIds = new Set(requirementFields.value.map(field => field.id))
      let extractedCount = 0

      Object.entries(extracted).forEach(([key, value]) => {
        if (!fieldIds.has(key)) return
        if (value && value.toString().trim()) {
          const field = requirementFields.value.find((item) => item.id === key)
          formData[key] = normalizeFieldValue(value, field || { id: key, type: 'text' })
          extractedFields.value[key] = value
          extractedCount++
        }
      })

      if (result.external_information) {
        externalInformation.value = result.external_information
      }

      await fetchSessionFiles()
      await fetchRequirements()
    } else {
      alert(result.message || 'File processing failed')
    }

  } catch (e) {
    console.error('File upload failed:', e)
    if (notifyModelNotConfigured(e)) return
    alert(e.response?.data?.detail || 'File upload failed')
  } finally {
    isUploading.value = false
  }
}

const readFileAsBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result || ''
      const resultString = typeof result === 'string' ? result : ''
      const commaIndex = resultString.indexOf(',')
      const base64 = commaIndex >= 0 ? resultString.slice(commaIndex + 1) : resultString
      resolve({
        filename: file.name,
        content_base64: base64,
        content_type: file.type || ''
      })
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const copyDocument = async () => {
  if (documentContent.value) {
    await navigator.clipboard.writeText(documentContent.value)
    copyButtonText.value = 'Copied!'
    setTimeout(() => {
      copyButtonText.value = 'Copy'
    }, 2000)
  }
}

const exportAs = async (format) => {
  showExportMenu.value = false
  if (!documentContent.value) return

  const filename = skill.value?.name || 'document'

  if (format === 'md') {
    const blob = new Blob([documentContent.value], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `${filename}.md`)
  } else if (format === 'docx' || format === 'pdf') {
    try {
      const response = await api.post('/documents/export', {
        content: documentContent.value,
        format: format,
        filename: filename
      }, { responseType: 'blob' })

      const contentType = format === 'docx'
        ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        : 'application/pdf'
      const blob = new Blob([response.data], { type: contentType })
      downloadBlob(blob, `${filename}.${format}`)
    } catch (e) {
      console.error('Export failed:', e)
      alert(`Export to ${format.toUpperCase()} failed.`)
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

const normalizeFields = (fields) => {
  return (fields || []).map((field) => ({
    ...field,
    type: field.type || field.field_type || 'text',
    collection: field.collection || (field.required ? 'required' : 'optional'),
    priority: Number(field.priority) || 3,
    example: field.example || '',
  }))
}

const normalizeFieldValue = (value, field) => {
  if (value === null || value === undefined) return ''
  const fieldId = field?.id || ''
  const fieldName = field?.name || ''
  const nameHint = `${fieldId} ${fieldName}`.toLowerCase()
  const prefersTitle = ['title', 'name', '名称', '标题', '题目'].some(token => nameHint.includes(token))
  if (typeof value !== 'string') {
    if (Array.isArray(value)) return value.join(field.type === 'textarea' ? '\n' : '、')
    if (typeof value === 'object') return JSON.stringify(value, null, 2)
    return String(value)
  }

  const trimmed = value.trim()
  if (!trimmed) return ''
  if (!(trimmed.startsWith('{') || trimmed.startsWith('['))) return value

  let parsed = null
  try {
    parsed = JSON.parse(trimmed)
  } catch (e) {
    return value
  }

  if (Array.isArray(parsed)) {
    return parsed.map(item => (typeof item === 'string' ? item : JSON.stringify(item))).join(field.type === 'textarea' ? '\n' : '、')
  }

  if (parsed && typeof parsed === 'object') {
    if (fieldId && parsed[fieldId]) return String(parsed[fieldId])
    const keys = Object.keys(parsed)
    if (keys.length === 1) return String(parsed[keys[0]])
    const titleKeys = ['title', 'name', '标题', '名称', 'topic', 'subject', '项目名称', '课题名称', 'project_title', 'projectname', 'project']
    const contentKeys = ['content', '正文', '内容', 'text', 'body', 'detail', 'details', 'description', 'summary', '简介', '说明', '背景']
    const orderedKeys = prefersTitle ? [...titleKeys, ...contentKeys] : [...contentKeys, ...titleKeys]
    const normalizedKeys = keys.reduce((acc, key) => {
      acc[key.toString().toLowerCase()] = key
      return acc
    }, {})
    for (const key of orderedKeys) {
      if (parsed[key]) return String(parsed[key])
      const normalizedKey = key.toLowerCase()
      if (normalizedKeys[normalizedKey] && parsed[normalizedKeys[normalizedKey]]) {
        return String(parsed[normalizedKeys[normalizedKey]])
      }
      const partial = keys.find((rawKey) => rawKey.toLowerCase().includes(normalizedKey))
      if (partial && parsed[partial]) return String(parsed[partial])
    }
  }

  return value
}

const applyRequirementsPayload = (payload) => {
  requirementFields.value = normalizeFields(payload.fields)
  externalInformation.value = payload.external_information || ''
  skillOverlay.value = payload.skill_overlay || null

  const existingReqs = payload.requirements || {}
  requirementFields.value.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(existingReqs, field.id)) {
      formData[field.id] = normalizeFieldValue(existingReqs[field.id], field)
    } else if (!(field.id in formData)) {
      formData[field.id] = ''
    }
  })
}

const handleClickOutside = (event) => {
  if (exportDropdown.value && !exportDropdown.value.contains(event.target)) {
    showExportMenu.value = false
  }
}

// Lifecycle
onMounted(async () => {
  await fetchSkill()
  await startSession()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  closeEventSource()
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
})
</script>

<style scoped>
.border-3 { border-width: 3px; }

.spinner {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-bar {
  transition: width 0.3s ease-out;
}

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

.line-clamp-4 {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
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

.markdown-content :deep(a) { color: #D97757; }
.markdown-content :deep(a:hover) { color: #C25E3D; }

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
