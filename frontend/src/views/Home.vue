<template>
  <div class="space-y-10">
    <!-- Header -->
    <section class="space-y-4">
      <div class="text-xs uppercase tracking-[0.2em] text-dark-50">多智能体写作系统</div>
      <h1 class="text-3xl md:text-4xl font-display font-semibold text-dark-300">SkillWriter</h1>
      <p class="text-sm md:text-base text-dark-50 max-w-2xl">
        Skill 定义结构与需求，Agent 负责信息收集、分段撰写、质量审查与必要修订。
      </p>
      <div class="flex flex-wrap gap-3">
        <router-link
          to="/create-skill"
          class="px-5 py-2.5 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-colors"
        >
          新建 Skill
        </router-link>
        <router-link
          to="/documents"
          class="px-5 py-2.5 bg-warm-100 text-dark-100 rounded-xl font-medium hover:bg-warm-200 transition-colors border border-warm-300"
        >
          查看文档
        </router-link>
      </div>
    </section>

    <!-- Architecture -->
    <section class="grid gap-4 lg:grid-cols-2">
      <div class="rounded-2xl border border-warm-300 bg-warm-100 p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-dark-300">架构概览</h2>
          <span class="text-xs bg-warm-200 text-dark-50 px-2 py-0.5 rounded-full">工作流</span>
        </div>
        <ul class="text-sm text-dark-50 space-y-2">
          <li>Skill 定义文档结构、需求字段与评审标准。</li>
          <li>会话先收集需求，再进入写作与审查循环。</li>
          <li>文档与 Skill 元数据一起保存，便于复用。</li>
        </ul>
        <div class="grid grid-cols-3 gap-3 text-xs">
          <div class="rounded-xl border border-warm-300 bg-warm-50 p-3">
            <p class="text-dark-50">可用技能</p>
            <p class="text-base font-semibold text-dark-300 mt-1">{{ loading ? '--' : skills.length }}</p>
          </div>
          <div class="rounded-xl border border-warm-300 bg-warm-50 p-3">
            <p class="text-dark-50">Agent 阶段</p>
            <p class="text-base font-semibold text-dark-300 mt-1">{{ agentStages.length }}</p>
          </div>
          <div class="rounded-xl border border-warm-300 bg-warm-50 p-3">
            <p class="text-dark-50">会话覆盖</p>
            <p class="text-base font-semibold text-dark-300 mt-1">会话级</p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2 text-xs text-dark-50">
          <span
            v-for="stage in agentStages"
            :key="stage.id"
            class="px-2 py-1 rounded-full border border-warm-300 bg-warm-50"
          >
            {{ stage.label }}
          </span>
        </div>
      </div>

      <div class="rounded-2xl border border-warm-300 bg-warm-100 p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-dark-300">Skill-Fixer 覆盖</h2>
          <span class="text-xs bg-signal-200 text-dark-300 px-2 py-0.5 rounded-full">仅本会话</span>
        </div>
        <p class="text-sm text-dark-50">
          会话内上传的材料可生成补充规范、写作准则与章节提示，不改变原始 Skill。
        </p>
        <div class="space-y-2">
          <div
            v-for="item in overlayHighlights"
            :key="item.title"
            class="rounded-xl border border-warm-300 bg-warm-50 p-3"
          >
            <div class="flex items-center justify-between">
              <p class="text-sm font-medium text-dark-300">{{ item.title }}</p>
              <span class="text-xs font-medium px-2 py-0.5 rounded-full" :class="item.tagClass">{{ item.tag }}</span>
            </div>
            <p class="text-xs text-dark-50 mt-2">{{ item.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Skills Grid -->
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-dark-50 uppercase tracking-wider">
          技能列表
        </h2>
        <router-link
          to="/create-skill"
          class="text-sm font-medium text-dark-100 hover:text-anthropic-orange transition-colors"
        >
          新建 Skill ->
        </router-link>
      </div>

      <!-- Loading Skeleton -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div
          v-for="i in 4"
          :key="`skeleton-${i}`"
          class="bg-warm-100 rounded-2xl border border-warm-300 p-6 animate-pulse"
        >
          <div class="flex items-start justify-between mb-4">
            <div class="w-12 h-12 bg-warm-200 rounded-xl"></div>
            <div class="w-20 h-6 bg-warm-200 rounded-full"></div>
          </div>
          <div class="h-6 bg-warm-200 rounded w-3/4 mb-2"></div>
          <div class="h-4 bg-warm-200 rounded w-full mb-1"></div>
          <div class="h-4 bg-warm-200 rounded w-2/3 mb-4"></div>
          <div class="flex gap-2 mb-5">
            <div class="h-6 w-16 bg-warm-200 rounded-lg"></div>
            <div class="h-6 w-16 bg-warm-200 rounded-lg"></div>
          </div>
          <div class="h-10 bg-warm-200 rounded-xl"></div>
        </div>
      </div>

      <!-- Actual Skills Grid -->
      <TransitionGroup
        v-else
        name="card"
        tag="div"
        class="grid grid-cols-1 md:grid-cols-2 gap-6"
      >
        <!-- Skill Cards -->
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="group bg-warm-100 rounded-2xl border border-warm-300 p-6 hover:border-anthropic-orange hover:shadow-lg transition-all duration-300 gpu-accelerate"
        >
          <div class="flex items-start justify-between mb-4">
            <div class="w-12 h-12 bg-gradient-to-br from-anthropic-orange to-anthropic-orange-dark rounded-xl flex items-center justify-center shadow-sm group-hover:scale-110 transition-transform duration-300">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span class="text-xs font-medium bg-warm-200 text-dark-50 px-3 py-1 rounded-full">
              {{ skill.category || '文档' }}
            </span>
          </div>

          <h3 class="text-xl font-display font-semibold text-dark-300 mb-2 group-hover:text-anthropic-orange transition-colors duration-200">
            {{ skill.name }}
          </h3>
          <p class="text-dark-50 text-sm mb-4 line-clamp-2">
            {{ skill.description }}
          </p>

          <div class="flex flex-wrap gap-2 mb-5">
            <span
              v-for="(tag, tagIndex) in (skill.tags || []).slice(0, 3)"
              :key="`${skill.id}-tag-${tagIndex}`"
              class="text-xs bg-warm-200 text-dark-100 px-2 py-1 rounded-lg"
            >
              {{ tag }}
            </span>
          </div>

          <!-- Action Buttons -->
          <div class="flex items-center gap-3 pt-4 border-t border-warm-200">
            <button
              @click="viewSkillDetails(skill)"
              class="flex-1 px-4 py-2.5 bg-warm-100 text-dark-100 rounded-xl font-medium hover:bg-warm-200 transition-all duration-200 flex items-center justify-center gap-2 text-sm active:scale-95"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              查看详情
            </button>
            <button
              @click="selectSkill(skill)"
              class="flex-1 px-4 py-2.5 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-all duration-200 flex items-center justify-center gap-2 text-sm shadow-sm active:scale-95"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              开始写作
            </button>
            <button
              @click.stop="confirmDeleteSkill(skill)"
              class="p-2.5 bg-warm-100 text-dark-100 rounded-xl hover:bg-red-900/30 hover:text-red-300 transition-all duration-200 active:scale-95"
              title="删除 Skill"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Create New Skill Card -->
        <div
          key="create-new"
          class="group bg-warm-100 rounded-2xl border-2 border-dashed border-warm-300 p-6 flex flex-col items-center justify-center min-h-[220px] hover:border-anthropic-orange-light hover:bg-warm-200 transition-all duration-300 cursor-pointer gpu-accelerate"
          @click="createNewSkill"
        >
          <div class="w-12 h-12 bg-warm-200 rounded-xl flex items-center justify-center mb-4 group-hover:bg-anthropic-orange-light group-hover:scale-110 transition-all duration-300">
            <svg class="w-6 h-6 text-warm-400 group-hover:text-white transition-colors duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </div>
          <span class="text-dark-100 font-medium mb-1">新建 Skill</span>
          <span class="text-sm text-warm-400">从模板生成新的技能</span>
        </div>
      </TransitionGroup>
    </div>

    <!-- Error State -->
    <Transition name="fade">
      <div v-if="error" class="flex flex-col items-center justify-center py-20">
        <div class="w-16 h-16 bg-red-900/40 rounded-full flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <p class="text-dark-100 font-medium mb-2">技能加载失败</p>
        <p class="text-dark-50 text-sm mb-4">{{ error }}</p>
        <button
          @click="fetchSkills"
          class="px-6 py-2.5 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-all duration-200 shadow-sm hover:shadow-md active:scale-95"
        >
          重新加载
        </button>
      </div>
    </Transition>

    <!-- Empty State -->
    <Transition name="fade">
      <div v-if="!loading && !error && skills.length === 0" class="flex flex-col items-center justify-center py-20">
        <div class="w-16 h-16 bg-warm-200 rounded-full flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <p class="text-dark-100 font-medium mb-2">暂无技能</p>
        <p class="text-dark-50 text-sm">先创建一个写作技能开始使用</p>
      </div>
    </Transition>

    <!-- Delete Confirmation Dialog -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showDeleteDialog"
          class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
          @click.self="cancelDelete"
        >
          <div class="bg-warm-50 rounded-2xl p-6 max-w-md w-full mx-4 shadow-xl modal-content border border-warm-300">
            <div class="flex items-center gap-4 mb-4">
              <div class="w-12 h-12 bg-red-900/40 rounded-full flex items-center justify-center flex-shrink-0">
                <svg class="w-6 h-6 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h3 class="text-lg font-semibold text-dark-300">删除 Skill</h3>
                <p class="text-sm text-dark-50">此操作不可撤销</p>
              </div>
            </div>
            <p class="text-dark-100 mb-6">
              确认删除「<span class="font-medium">{{ skillToDelete?.name }}</span>」？
              相关文件将被永久移除。
            </p>
            <div class="flex gap-3">
              <button
                @click="cancelDelete"
                class="flex-1 px-4 py-2.5 bg-warm-100 text-dark-100 rounded-xl font-medium hover:bg-warm-200 transition-all duration-200 active:scale-95"
                :disabled="deleting"
              >
                取消
              </button>
              <button
                @click="executeDelete"
                class="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-xl font-medium hover:bg-red-500 transition-all duration-200 flex items-center justify-center gap-2 active:scale-95"
                :disabled="deleting"
              >
                <svg v-if="deleting" class="w-4 h-4 spinner" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ deleting ? '删除中...' : '删除' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
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

const agentStages = [
  {
    id: 'requirement',
    label: '需求收集'
  },
  {
    id: 'writer',
    label: '内容写作'
  },
  {
    id: 'reviewer',
    label: '质量审查'
  },
  {
    id: 'revision',
    label: '修订完善'
  }
]

const overlayHighlights = [
  {
    title: '材料抽取',
    tag: '输入',
    tagClass: 'bg-signal-200 text-dark-300',
    description: '从上传材料中抽取事实与必填字段。'
  },
  {
    title: 'Skill-Fixer',
    tag: '覆盖',
    tagClass: 'bg-anthropic-orange/15 text-anthropic-orange-light',
    description: '为本次会话补充规范、准则与章节提示。'
  },
  {
    title: '提示词合并',
    tag: '运行时',
    tagClass: 'bg-warm-200 text-dark-100',
    description: '在不修改基础 Skill 的前提下进行增强。'
  }
]

// Delete dialog state
const showDeleteDialog = ref(false)
const skillToDelete = ref(null)
const deleting = ref(false)

// Filter out the skill creator from the list (it's a system tool, not a writing skill)
const skills = computed(() => {
  return allSkills.value.filter(skill => !['writer-skill-creator', 'base_writing'].includes(skill.id))
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

const createNewSkill = () => {
  router.push('/create-skill')
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
    // Remove from local list
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
/* GPU Acceleration */
.gpu-accelerate {
  transform: translateZ(0);
  will-change: transform;
  backface-visibility: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.border-3 {
  border-width: 3px;
}

/* Spinner */
.spinner {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Card animations */
.card-enter-active {
  animation: card-in 0.3s ease-out;
}

.card-leave-active {
  animation: card-out 0.2s ease-in;
}

.card-move {
  transition: transform 0.3s ease;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes card-out {
  from {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  to {
    opacity: 0;
    transform: translateY(-10px) scale(0.95);
  }
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Modal transition */
.modal-enter-active {
  transition: opacity 0.2s ease;
}

.modal-leave-active {
  transition: opacity 0.15s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content {
  animation: modal-in 0.25s ease-out;
}

.modal-leave-active .modal-content {
  animation: modal-out 0.15s ease-in;
}

@keyframes modal-in {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

@keyframes modal-out {
  from {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
  to {
    opacity: 0;
    transform: scale(0.9) translateY(20px);
  }
}

/* Skeleton animation */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.animate-pulse {
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>
