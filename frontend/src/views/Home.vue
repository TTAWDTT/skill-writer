<template>
  <div class="space-y-8">
    <section class="ui-panel p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.2em] text-dark-50">SkillWriter</p>
          <h1 class="mt-2 text-3xl font-display font-semibold text-dark-300">技能与会话入口</h1>
          <p class="mt-2 text-sm text-dark-50">需求收集后会强制生成三元 guideline，再进入分章节写作。</p>
        </div>
        <div class="flex gap-3">
          <router-link to="/create-skill" class="ui-btn">
            新建 Skill
          </router-link>
          <router-link to="/documents" class="ui-btn">
            查看文档
          </router-link>
        </div>
      </div>
    </section>

    <section class="grid gap-4 md:grid-cols-2">
      <div class="ui-panel p-5">
        <h2 class="text-sm font-semibold text-dark-300">当前流程</h2>
        <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div
            v-for="step in workflowSteps"
            :key="step.id"
            class="ui-card px-3 py-2"
          >
            <p class="text-dark-100">{{ step.label }}</p>
            <p class="mt-1 text-dark-50">{{ step.detail }}</p>
          </div>
        </div>
      </div>

      <div class="ui-panel p-5">
        <h2 class="text-sm font-semibold text-dark-300">概览</h2>
        <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
          <div class="ui-card px-3 py-3">
            <p class="text-dark-50">可用技能</p>
            <p class="mt-1 text-lg font-semibold text-dark-300">{{ loading ? '--' : skills.length }}</p>
          </div>
          <div class="ui-card px-3 py-3">
            <p class="text-dark-50">会话增强</p>
            <p class="mt-1 text-lg font-semibold text-dark-300">Guideline + Overlay</p>
          </div>
        </div>
      </div>
    </section>

    <section class="ui-panel p-5">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-dark-300">技能列表</h2>
        <router-link to="/create-skill" class="text-sm text-dark-100 hover:text-dark-300">创建新 Skill</router-link>
      </div>

      <div v-if="loading" class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div v-for="i in 4" :key="`loading-${i}`" class="ui-card p-4">
          <div class="h-4 w-2/3 animate-pulse rounded bg-warm-200"></div>
          <div class="mt-2 h-3 w-full animate-pulse rounded bg-warm-200"></div>
        </div>
      </div>

      <div v-else-if="error" class="ui-card border-signal-200 bg-signal-50 p-4 text-sm text-dark-300">
        {{ error }}
      </div>

      <div v-else-if="skills.length === 0" class="ui-card border-dashed p-8 text-center text-sm text-dark-50">
        暂无技能，先创建一个写作 Skill。
      </div>

      <div v-else class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <article v-for="skill in skills" :key="skill.id" class="ui-card p-4 hover:border-signal-400 transition-colors">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="truncate text-base font-semibold text-dark-300">{{ skill.name }}</h3>
              <p class="mt-1 line-clamp-2 text-sm text-dark-50">{{ skill.description }}</p>
            </div>
            <span class="ui-chip shrink-0">{{ skill.category || '文档' }}</span>
          </div>

          <div class="mt-3 flex flex-wrap gap-2">
            <span v-for="(tag, idx) in (skill.tags || []).slice(0, 4)" :key="`${skill.id}-${idx}`" class="ui-chip">
              {{ tag }}
            </span>
          </div>

          <div class="mt-4 flex gap-2">
            <button @click="viewSkillDetails(skill)" class="ui-btn px-3 py-1.5 text-xs">
              查看
            </button>
            <button @click="selectSkill(skill)" class="ui-btn px-3 py-1.5 text-xs">
              写作
            </button>
            <button @click.stop="confirmDeleteSkill(skill)" class="ui-btn-danger px-3 py-1.5 text-xs">
              删除
            </button>
          </div>
        </article>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="showDeleteDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
        @click.self="cancelDelete"
      >
        <div class="ui-panel w-full max-w-md p-5">
          <h3 class="text-lg font-semibold text-dark-300">删除 Skill</h3>
          <p class="mt-2 text-sm text-dark-50">确认删除「{{ skillToDelete?.name }}」？该操作不可撤销。</p>
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
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const allSkills = ref([])
const loading = ref(true)
const error = ref(null)

const workflowSteps = [
  { id: 'requirement', label: '1. 需求收集', detail: '补齐关键信息与材料。' },
  { id: 'guideline', label: '2. Triadic Guideline', detail: '生成 need -> content -> goal 映射。' },
  { id: 'writing', label: '3. 分段写作', detail: 'outline / draft / review / revise。' },
  { id: 'finish', label: '4. 文档产出', detail: '统一润色与导出。' },
]

const showDeleteDialog = ref(false)
const skillToDelete = ref(null)
const deleting = ref(false)

const skills = computed(() => {
  return allSkills.value.filter(skill => skill.role === 'document' && skill.user_invocable !== false)
})

const fetchSkills = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/skills/')
    allSkills.value = response.data
  } catch (e) {
    error.value = '请确认后端服务已在 8000 端口运行'
    console.error('Failed to fetch skills:', e)
  } finally {
    loading.value = false
  }
}

const selectSkill = (skill) => {
  router.push(`/write/${skill.id}`)
}

const viewSkillDetails = (skill) => {
  router.push(`/skill/${skill.id}`)
}

const confirmDeleteSkill = (skill) => {
  skillToDelete.value = skill
  showDeleteDialog.value = true
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  skillToDelete.value = null
}

const executeDelete = async () => {
  if (!skillToDelete.value) return

  deleting.value = true
  try {
    await api.delete(`/skills/${skillToDelete.value.id}`)
    allSkills.value = allSkills.value.filter(s => s.id !== skillToDelete.value.id)
    showDeleteDialog.value = false
    skillToDelete.value = null
  } catch (e) {
    console.error('Failed to delete skill:', e)
    alert(e.response?.data?.detail || '删除失败，请重试。')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  fetchSkills()
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>


