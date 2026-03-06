<template>
  <div class="mx-auto max-w-5xl space-y-5">
    <router-link to="/" class="inline-flex items-center gap-2 text-sm text-dark-50 hover:underline">
      返回技能列表
    </router-link>

    <div v-if="loading" class="ui-panel p-8 text-center text-sm text-dark-50">
      正在加载技能详情...
    </div>

    <div v-else-if="error" class="ui-card border-signal-200 bg-signal-50 p-5 text-sm text-dark-300">
      {{ error }}
    </div>

    <template v-else-if="skill">
      <section class="ui-panel p-6">
        <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <h1 class="truncate text-2xl font-display font-semibold text-dark-300">{{ skill.name }}</h1>
              <span class="ui-chip">{{ skill.category || '文档' }}</span>
              <span v-if="skill.role && skill.role !== 'document'" class="ui-chip">{{ skill.role }}</span>
            </div>
            <p class="mt-2 text-sm text-dark-50">{{ skill.description }}</p>
            <div class="mt-3 flex flex-wrap gap-2">
              <span v-for="tag in (skill.tags || [])" :key="tag" class="ui-chip">
                {{ tag }}
              </span>
            </div>
          </div>

          <div v-if="canWrite || canDelete" class="flex shrink-0 gap-2">
            <button
              v-if="canWrite"
              @click="startWriting"
              class="ui-btn"
            >
              开始写作
            </button>
            <button
              v-if="canDelete"
              @click="confirmDelete"
              class="ui-btn-danger"
            >
              删除 Skill
            </button>
          </div>
        </div>
      </section>

      <section class="ui-panel p-4">
        <div class="mb-4 flex flex-wrap gap-2">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            class="rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
            :class="activeTab === tab.id ? 'border-anthropic-orange bg-signal-100 text-dark-300' : 'border-warm-300 text-dark-50 hover:border-signal-400 hover:text-dark-300 hover:bg-signal-50'"
          >
            {{ tab.label }}
          </button>
        </div>

        <div v-show="activeTab === 'overview'" class="grid gap-3 md:grid-cols-3">
          <div class="ui-card p-4">
            <p class="text-xs text-dark-50">章节数</p>
            <p class="mt-1 text-xl font-semibold text-dark-300">{{ skill.structure?.length || 0 }}</p>
          </div>
          <div class="ui-card p-4">
            <p class="text-xs text-dark-50">需求字段</p>
            <p class="mt-1 text-xl font-semibold text-dark-300">{{ skill.requirement_fields?.length || 0 }}</p>
          </div>
          <div class="ui-card p-4">
            <p class="text-xs text-dark-50">标签</p>
            <p class="mt-1 text-xl font-semibold text-dark-300">{{ skill.tags?.length || 0 }}</p>
          </div>
        </div>

        <div v-show="activeTab === 'structure'" class="space-y-2">
          <div
            v-for="section in (skill.structure || [])"
            :key="section.id"
            class="ui-card p-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="font-medium text-dark-300">{{ section.title }}</p>
                <p class="mt-1 text-xs text-dark-50">level {{ section.level }} · {{ section.type || 'required' }}</p>
              </div>
              <span v-if="section.word_limit" class="text-xs text-dark-50">{{ section.word_limit[0] }}-{{ section.word_limit[1] }} 字</span>
            </div>
            <p v-if="section.description" class="mt-2 text-sm text-dark-50">{{ section.description }}</p>
            <p v-if="section.writing_guide" class="mt-1 text-xs text-dark-50">写作指导：{{ section.writing_guide }}</p>
          </div>
        </div>

        <div v-show="activeTab === 'requirements'" class="space-y-2">
          <div
            v-for="field in sortedRequirementFields"
            :key="field.id"
            class="ui-card p-4"
          >
            <div class="flex items-center justify-between gap-3">
              <p class="font-medium text-dark-300">{{ field.name }}</p>
              <span class="text-xs text-dark-50">{{ field.collection || (field.required ? 'required' : 'optional') }} · P{{ field.priority || 3 }}</span>
            </div>
            <p class="mt-2 text-sm text-dark-50">{{ field.description }}</p>
            <p v-if="field.example" class="mt-1 text-xs text-dark-50">示例：{{ field.example }}</p>
          </div>
          <div v-if="sortedRequirementFields.length === 0" class="ui-card border-dashed p-8 text-center text-sm text-dark-50">
            当前 Skill 未配置需求字段。
          </div>
        </div>

        <div v-show="activeTab === 'guidelines'">
          <div v-if="skillContent.guidelines" class="markdown-content prose prose-pure max-w-none" v-html="renderedGuidelines"></div>
          <div v-else class="ui-card border-dashed p-8 text-center text-sm text-dark-50">
            该 Skill 暂无写作规范。
          </div>
        </div>
      </section>
    </template>

    <div
      v-if="showDeleteDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      @click.self="cancelDelete"
    >
      <div class="ui-panel w-full max-w-md p-5">
        <h3 class="text-lg font-semibold text-dark-300">删除 Skill</h3>
        <p class="mt-2 text-sm text-dark-50">确认删除「{{ skill?.name }}」？该操作不可撤销。</p>
        <div class="mt-5 flex gap-3">
          <button
            @click="cancelDelete"
            class="ui-btn flex-1"
            :disabled="deleting"
          >
            取消
          </button>
          <button
            @click="executeDelete"
            class="ui-btn-danger flex-1"
            :disabled="deleting"
          >
            {{ deleting ? '删除中...' : '删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const skillId = computed(() => route.params.skillId)

const skill = ref(null)
const skillContent = ref({})
const loading = ref(true)
const error = ref(null)
const activeTab = ref('overview')

const showDeleteDialog = ref(false)
const deleting = ref(false)

const tabs = [
  { id: 'overview', label: '概览' },
  { id: 'structure', label: '结构' },
  { id: 'requirements', label: '需求' },
  { id: 'guidelines', label: '规范' },
]

const renderedGuidelines = computed(() => {
  if (!skillContent.value.guidelines) return ''
  return marked(skillContent.value.guidelines)
})

const canWrite = computed(() => {
  return skill.value?.role === 'document' && skill.value?.user_invocable !== false
})

const canDelete = computed(() => {
  return skill.value?.role === 'document' && skill.value?.user_invocable !== false
})

const sortedRequirementFields = computed(() => {
  const fields = skill.value?.requirement_fields || []
  return [...fields].sort((a, b) => {
    const ap = Number(a.priority || 3)
    const bp = Number(b.priority || 3)
    if (ap !== bp) return ap - bp
    return (a.name || '').localeCompare(b.name || '')
  })
})

const fetchSkill = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await api.get(`/skills/${skillId.value}`)
    skill.value = response.data

    try {
      const contentResponse = await api.get(`/skills/${skillId.value}/content`)
      skillContent.value = contentResponse.data
    } catch {
      skillContent.value = {}
    }
  } catch (e) {
    console.error('Failed to fetch skill:', e)
    error.value = e.response?.data?.detail || '加载技能详情失败'
  } finally {
    loading.value = false
  }
}

const startWriting = () => {
  router.push(`/write/${skillId.value}`)
}

const confirmDelete = () => {
  showDeleteDialog.value = true
}

const cancelDelete = () => {
  showDeleteDialog.value = false
}

const executeDelete = async () => {
  deleting.value = true
  try {
    await api.delete(`/skills/${skillId.value}`)
    router.push('/')
  } catch (e) {
    console.error('Failed to delete skill:', e)
    alert(e.response?.data?.detail || '删除失败，请重试。')
  } finally {
    deleting.value = false
    showDeleteDialog.value = false
  }
}

onMounted(() => {
  fetchSkill()
})
</script>

<style scoped>
.prose-pure {
  --tw-prose-body: #303a46;
  --tw-prose-headings: #1d1d1f;
  --tw-prose-links: #0071e3;
  --tw-prose-bold: #1d1d1f;
  --tw-prose-counters: #6e7785;
  --tw-prose-bullets: #6e7785;
  --tw-prose-hr: #d6dae1;
  --tw-prose-quotes: #303a46;
  --tw-prose-quote-borders: #0071e3;
  --tw-prose-code: #1d1d1f;
  --tw-prose-pre-code: #303a46;
  --tw-prose-pre-bg: #f5f5f7;
}

.markdown-content :deep(code) {
  border: 1px solid #d6dae1;
  background: #f0f7ff;
  border-radius: 0.35rem;
  padding: 0.1rem 0.35rem;
}

.markdown-content :deep(pre) {
  border: 1px solid #d6dae1;
  background: #f5f5f7;
  border-radius: 0.75rem;
  padding: 1rem;
}
</style>



