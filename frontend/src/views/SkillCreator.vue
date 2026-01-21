<template>
  <div class="max-w-4xl mx-auto space-y-8">
    <!-- Header -->
    <div class="text-center py-8">
      <div class="w-16 h-16 bg-gradient-to-br from-anthropic-orange to-anthropic-orange-dark rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
        <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      </div>
      <h1 class="text-3xl font-bold text-dark-300 mb-3">Create Writing Skill</h1>
      <p class="text-dark-50 max-w-xl mx-auto">
        Upload a template document and we'll automatically generate a writing skill that can help create similar documents.
      </p>
    </div>

    <!-- Upload Section -->
    <div class="bg-warm-50 rounded-2xl border border-warm-300 p-8">
      <h2 class="text-lg font-semibold text-dark-300 mb-4">Step 1: Upload Template</h2>

      <!-- File Upload Area -->
      <div
        class="border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-300"
        :class="[
          isDragging
            ? 'border-anthropic-orange bg-anthropic-orange-light/10'
            : 'border-warm-300 hover:border-anthropic-orange-light',
          uploadedFile ? 'bg-warm-100' : ''
        ]"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <div v-if="!uploadedFile">
          <div class="w-14 h-14 bg-warm-200 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg class="w-7 h-7 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p class="text-dark-300 font-medium mb-2">Drag and drop your template file here</p>
          <p class="text-dark-50 text-sm mb-4">or click to browse</p>
          <input
            type="file"
            ref="fileInput"
            @change="handleFileSelect"
            accept=".md,.doc,.docx,.pdf,.txt,.pptx"
            class="hidden"
          />
          <button
            @click="$refs.fileInput.click()"
            class="px-6 py-2.5 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-colors shadow-sm"
          >
            Browse Files
          </button>
          <p class="text-warm-400 text-xs mt-4">Supported formats: MD, DOC, DOCX, PDF, TXT, PPTX</p>
        </div>

        <!-- Uploaded File Preview -->
        <div v-else class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-anthropic-orange-light rounded-xl flex items-center justify-center">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div class="text-left">
              <p class="font-medium text-dark-300">{{ uploadedFile.name }}</p>
              <p class="text-sm text-dark-50">{{ formatFileSize(uploadedFile.size) }}</p>
            </div>
          </div>
          <button
            @click="removeFile"
            class="p-2 text-warm-400 hover:text-red-500 transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Skill Info Section -->
    <div v-if="uploadedFile" class="bg-warm-50 rounded-2xl border border-warm-300 p-8">
      <h2 class="text-lg font-semibold text-dark-300 mb-4">Step 2: Skill Information</h2>

      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-dark-100 mb-2">Skill Name</label>
          <input
            v-model="skillInfo.name"
            type="text"
            placeholder="e.g., Patent Application Writer"
            class="w-full px-4 py-3 bg-warm-100 border border-warm-300 rounded-xl text-dark-300 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-dark-100 mb-2">Description</label>
          <textarea
            v-model="skillInfo.description"
            rows="3"
            placeholder="Describe what this skill does..."
            class="w-full px-4 py-3 bg-warm-100 border border-warm-300 rounded-xl text-dark-300 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent resize-none"
          ></textarea>
        </div>

        <div>
          <label class="block text-sm font-medium text-dark-100 mb-2">Category</label>
          <select
            v-model="skillInfo.category"
            class="w-full px-4 py-3 bg-warm-100 border border-warm-300 rounded-xl text-dark-300 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent"
          >
            <option value="">Select a category</option>
            <option value="research">Research & Academic</option>
            <option value="business">Business & Corporate</option>
            <option value="legal">Legal & Patents</option>
            <option value="technical">Technical Writing</option>
            <option value="creative">Creative Writing</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-dark-100 mb-2">Tags (comma separated)</label>
          <input
            v-model="skillInfo.tags"
            type="text"
            placeholder="e.g., patent, application, intellectual property"
            class="w-full px-4 py-3 bg-warm-100 border border-warm-300 rounded-xl text-dark-300 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent"
          />
        </div>
      </div>
    </div>

    <!-- Generate Button -->
    <div v-if="uploadedFile" class="flex justify-center">
      <button
        @click="generateSkill"
        :disabled="isGenerating || !skillInfo.name"
        class="px-8 py-4 bg-anthropic-orange text-white rounded-xl font-semibold text-lg hover:bg-anthropic-orange-dark disabled:bg-warm-300 disabled:text-warm-400 disabled:cursor-not-allowed transition-colors shadow-lg hover:shadow-xl flex items-center gap-3"
      >
        <span v-if="isGenerating" class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
        <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        {{ isGenerating ? 'Generating Skill...' : 'Generate Writing Skill' }}
      </button>
    </div>

    <!-- Generation Progress -->
    <div v-if="isGenerating" class="bg-warm-50 rounded-2xl border border-warm-300 p-8">
      <div class="flex items-center gap-4 mb-4">
        <div class="w-10 h-10 border-3 border-warm-300 border-t-anthropic-orange rounded-full animate-spin"></div>
        <div>
          <p class="font-medium text-dark-300">{{ generationStatus }}</p>
          <p class="text-sm text-dark-50">This may take a moment...</p>
        </div>
      </div>
      <div class="w-full bg-warm-200 rounded-full h-2">
        <div
          class="bg-gradient-to-r from-anthropic-orange to-anthropic-orange-dark h-2 rounded-full transition-all duration-500"
          :style="{ width: generationProgress + '%' }"
        ></div>
      </div>
    </div>

    <!-- Success Message -->
    <div v-if="generationComplete" class="bg-green-50 rounded-2xl border border-green-200 p-8 text-center">
      <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h3 class="text-xl font-semibold text-green-800 mb-2">Skill Created Successfully!</h3>
      <p class="text-green-600 mb-6">Your new writing skill "{{ skillInfo.name }}" is now available.</p>
      <div class="flex justify-center gap-4">
        <router-link
          to="/"
          class="px-6 py-2.5 bg-white text-green-700 border border-green-300 rounded-xl font-medium hover:bg-green-50 transition-colors"
        >
          Back to Skills
        </router-link>
        <button
          @click="resetForm"
          class="px-6 py-2.5 bg-green-500 text-white rounded-xl font-medium hover:bg-green-600 transition-colors"
        >
          Create Another
        </button>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="bg-red-50 rounded-2xl border border-red-200 p-6">
      <div class="flex items-start gap-4">
        <div class="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div>
          <h4 class="font-medium text-red-800">Generation Failed</h4>
          <p class="text-red-600 text-sm mt-1">{{ error }}</p>
          <button
            @click="error = null"
            class="mt-3 text-sm text-red-700 hover:text-red-800 font-medium"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'

// State
const isDragging = ref(false)
const uploadedFile = ref(null)
const fileInput = ref(null)
const isGenerating = ref(false)
const generationProgress = ref(0)
const generationStatus = ref('')
const generationComplete = ref(false)
const error = ref(null)

const skillInfo = ref({
  name: '',
  description: '',
  category: '',
  tags: ''
})

// Methods
const handleDrop = (e) => {
  isDragging.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const handleFileSelect = (e) => {
  const files = e.target.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const processFile = (file) => {
  const allowedTypes = ['.md', '.doc', '.docx', '.pdf', '.txt', '.pptx']
  const ext = '.' + file.name.split('.').pop().toLowerCase()

  if (!allowedTypes.includes(ext)) {
    error.value = `Unsupported file type: ${ext}. Please upload MD, DOC, DOCX, PDF, TXT, or PPTX files.`
    return
  }

  uploadedFile.value = file
  error.value = null

  // Auto-fill skill name from filename
  if (!skillInfo.value.name) {
    const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '')
    skillInfo.value.name = nameWithoutExt.replace(/[-_]/g, ' ')
  }
}

const removeFile = () => {
  uploadedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const generateSkill = async () => {
  if (!uploadedFile.value || !skillInfo.value.name) return

  isGenerating.value = true
  generationProgress.value = 0
  generationComplete.value = false
  error.value = null

  try {
    // Create FormData
    const formData = new FormData()
    formData.append('file', uploadedFile.value)
    formData.append('name', skillInfo.value.name)
    formData.append('description', skillInfo.value.description)
    formData.append('category', skillInfo.value.category)
    formData.append('tags', skillInfo.value.tags)

    // Simulate progress stages
    generationStatus.value = 'Uploading template file...'
    generationProgress.value = 10

    // Upload and generate
    const response = await api.post('/skills/create-from-template', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        const uploadPercent = Math.round((progressEvent.loaded * 30) / progressEvent.total)
        generationProgress.value = 10 + uploadPercent
      }
    })

    generationStatus.value = 'Analyzing template structure...'
    generationProgress.value = 50

    await new Promise(resolve => setTimeout(resolve, 500))

    generationStatus.value = 'Generating skill configuration...'
    generationProgress.value = 75

    await new Promise(resolve => setTimeout(resolve, 500))

    generationStatus.value = 'Finalizing...'
    generationProgress.value = 100

    await new Promise(resolve => setTimeout(resolve, 300))

    generationComplete.value = true
    isGenerating.value = false

  } catch (e) {
    console.error('Failed to generate skill:', e)
    error.value = e.response?.data?.detail || 'Failed to generate skill. Please try again.'
    isGenerating.value = false
  }
}

const resetForm = () => {
  uploadedFile.value = null
  skillInfo.value = {
    name: '',
    description: '',
    category: '',
    tags: ''
  }
  generationComplete.value = false
  generationProgress.value = 0
  error.value = null
}
</script>

<style scoped>
.border-3 {
  border-width: 3px;
}
</style>
