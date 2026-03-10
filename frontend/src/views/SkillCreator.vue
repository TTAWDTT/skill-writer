<template>
  <div class="mx-auto max-w-4xl space-y-6">
    <section class="ui-panel p-6">
      <h1 class="text-3xl font-display font-semibold text-dark-300">创建 Skill</h1>
      <p class="mt-2 text-sm text-dark-50">上传模板文档，自动抽取结构并生成可复用写作 Skill。</p>
    </section>

    <section class="ui-panel p-6">
      <h2 class="text-sm font-semibold text-dark-300">1. 上传模板</h2>
      <div
        class="ui-card mt-3 border-2 border-dashed p-6 text-center transition-colors"
        :class="isDragging ? 'border-signal-500 bg-signal-50' : 'border-warm-300'"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <input
          ref="fileInput"
          type="file"
          class="hidden"
          accept=".md,.doc,.docx,.pdf,.txt,.pptx"
          @change="handleFileSelect"
        />
        <div v-if="!uploadedFile">
          <p class="text-sm text-dark-300">拖拽文件到此处，或点击选择</p>
          <button
            class="ui-btn mt-3"
            @click="fileInput?.click()"
          >
            选择文件
          </button>
          <p class="mt-2 text-xs text-dark-50">支持：MD, DOC, DOCX, PDF, TXT, PPTX</p>
        </div>

        <div v-else class="ui-card flex items-center justify-between gap-3 p-3 text-left">
          <div>
            <p class="text-sm font-medium text-dark-300">{{ uploadedFile.name }}</p>
            <p class="text-xs text-dark-50">{{ formatFileSize(uploadedFile.size) }}</p>
          </div>
          <button class="ui-btn-danger px-3 py-1 text-xs" @click="removeFile">
            移除
          </button>
        </div>
      </div>
    </section>

    <section v-if="uploadedFile" class="ui-panel p-6">
      <h2 class="text-sm font-semibold text-dark-300">2. 基本信息</h2>
      <div class="mt-3 grid gap-3">
        <label class="text-xs text-dark-50">
          Skill 名称
          <input
            v-model="skillInfo.name"
            type="text"
            class="ui-input mt-1"
            placeholder="例如：项目申报书写作"
          />
        </label>

        <label class="text-xs text-dark-50">
          描述
          <textarea
            v-model="skillInfo.description"
            rows="3"
            class="ui-input mt-1"
            placeholder="描述该 Skill 的用途"
          ></textarea>
        </label>

        <div class="grid gap-3 md:grid-cols-2">
          <label class="text-xs text-dark-50">
            分类
            <select
              v-model="skillInfo.category"
              class="ui-input mt-1"
            >
              <option value="">请选择分类</option>
              <option value="research">科研学术</option>
              <option value="business">商业/企业</option>
              <option value="legal">法律/专利</option>
              <option value="technical">技术写作</option>
              <option value="creative">创意写作</option>
              <option value="other">其他</option>
            </select>
          </label>

          <label class="text-xs text-dark-50">
            标签（逗号分隔）
            <input
              v-model="skillInfo.tags"
              type="text"
              class="ui-input mt-1"
              placeholder="项目申请, 科研"
            />
          </label>
        </div>
      </div>
    </section>

    <section v-if="uploadedFile" class="ui-panel p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <button
          @click="generateSkill"
          :disabled="isGenerating || !skillInfo.name"
          class="ui-btn-accent"
        >
          {{ isGenerating ? '生成中...' : '生成 Skill' }}
        </button>
        <p v-if="isGenerating" class="text-xs text-dark-50">{{ generationStatus }}（{{ generationProgress }}%）</p>
      </div>
      <div class="mt-3 h-2 w-full overflow-hidden rounded-full border border-warm-300">
        <div class="h-full bg-white transition-all duration-500" :style="{ width: `${generationProgress}%` }"></div>
      </div>
    </section>

    <section v-if="generationComplete" class="ui-card border-signal-200 bg-signal-50 p-6">
      <h3 class="text-lg font-semibold text-dark-300">Skill 创建成功</h3>
      <p class="mt-1 text-sm text-dark-300">「{{ skillInfo.name }}」已可使用。</p>
      <div class="mt-4 flex gap-3">
        <router-link to="/" class="ui-btn border-signal-200 text-dark-300 hover:bg-signal-50 hover:text-dark-300">返回技能列表</router-link>
        <button @click="resetForm" class="ui-btn">再建一个</button>
      </div>
    </section>

    <section v-if="error" class="ui-card border-signal-200 bg-signal-50 p-5 text-sm text-dark-300">
      {{ error }}
    </section>

    <Toast :show="toastVisible" :title="toastTitle" :message="toastMessage" @close="toastVisible = false" />
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { api } from '../api'
import Toast from '../components/Toast.vue'

const isDragging = ref(false)
const uploadedFile = ref(null)
const fileInput = ref(null)
const isGenerating = ref(false)
const generationProgress = ref(0)
const generationStatus = ref('')
const generationComplete = ref(false)
const error = ref(null)
const toastVisible = ref(false)
const toastTitle = ref('')
const toastMessage = ref('')
let toastTimer = null

const skillInfo = ref({
  name: '',
  description: '',
  category: '',
  tags: '',
})

const handleDrop = (e) => {
  isDragging.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) processFile(files[0])
}

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files.length > 0) processFile(files[0])
}

const processFile = (file) => {
  const allowedTypes = ['.md', '.doc', '.docx', '.pdf', '.txt', '.pptx']
  const ext = '.' + file.name.split('.').pop().toLowerCase()

  if (!allowedTypes.includes(ext)) {
    error.value = `不支持的文件类型：${ext}。请上传 MD、DOC、DOCX、PDF、TXT 或 PPTX。`
    return
  }

  uploadedFile.value = file
  error.value = null

  if (!skillInfo.value.name) {
    const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '')
    skillInfo.value.name = nameWithoutExt.replace(/[-_]/g, ' ')
  }
}

const removeFile = () => {
  uploadedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const showToast = (title, message) => {
  toastTitle.value = title
  toastMessage.value = message
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
  }, 2600)
}

const notifyModelNotConfigured = (requestError) => {
  const detail = requestError?.response?.data?.detail
  if (detail === '模型未配置') {
    showToast('模型未配置', '请先在设置中配置模型。')
    return true
  }
  return false
}

const generateSkill = async () => {
  if (!uploadedFile.value || !skillInfo.value.name) return

  isGenerating.value = true
  generationProgress.value = 0
  generationComplete.value = false
  error.value = null

  try {
    const formData = new FormData()
    formData.append('file', uploadedFile.value)
    formData.append('name', skillInfo.value.name)
    formData.append('description', skillInfo.value.description)
    formData.append('category', skillInfo.value.category)
    formData.append('tags', skillInfo.value.tags)

    generationStatus.value = '正在上传模板'
    generationProgress.value = 20

    const response = await api.post('/skills/create-from-template', formData, {
      onUploadProgress: (progressEvent) => {
        const uploadPercent = Math.round((progressEvent.loaded * 50) / progressEvent.total)
        generationProgress.value = 20 + uploadPercent
      },
    })

    generationStatus.value = '正在解析并生成 Skill'
    generationProgress.value = 85
    await new Promise(resolve => setTimeout(resolve, 400))

    generationProgress.value = 100
    generationComplete.value = true
    if (Array.isArray(response.data?.warnings) && response.data.warnings.length > 0) {
      showToast('已生成 Skill', response.data.warnings.join('\n'))
    }
  } catch (e) {
    console.error('Failed to generate skill:', e)
    if (notifyModelNotConfigured(e)) {
      error.value = null
      return
    }
    const detail = e.response?.data?.detail
    if (detail && typeof detail === 'object') {
      const errors = Array.isArray(detail.errors) ? detail.errors.join('；') : ''
      error.value = [detail.message, errors].filter(Boolean).join('：') || 'Skill 生成失败，请重试。'
    } else {
      error.value = detail || 'Skill 生成失败，请重试。'
    }
  } finally {
    isGenerating.value = false
  }
}

const resetForm = () => {
  uploadedFile.value = null
  skillInfo.value = {
    name: '',
    description: '',
    category: '',
    tags: '',
  }
  generationComplete.value = false
  generationProgress.value = 0
  error.value = null
}

onUnmounted(() => {
  if (toastTimer) clearTimeout(toastTimer)
})
</script>



