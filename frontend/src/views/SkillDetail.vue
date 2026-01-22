<template>
  <div class="max-w-5xl mx-auto">
    <!-- Back Button -->
    <router-link
      to="/"
      class="inline-flex items-center gap-2 text-dark-50 hover:text-anthropic-orange transition-colors mb-6 group"
    >
      <svg class="w-5 h-5 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
      </svg>
      返回技能列表
    </router-link>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-20">
      <div class="w-12 h-12 border-3 border-warm-300 border-t-anthropic-orange rounded-full animate-spin"></div>
      <p class="text-dark-50 mt-4">正在加载技能详情...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-900/30 rounded-2xl border border-red-500/40 p-8 text-center">
      <div class="w-16 h-16 bg-red-900/40 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <p class="text-red-200 font-medium mb-2">技能加载失败</p>
      <p class="text-red-300 text-sm">{{ error }}</p>
    </div>

    <!-- Skill Content -->
    <template v-else-if="skill">
      <!-- Header -->
      <div class="bg-warm-50 rounded-2xl border border-warm-300 p-8 mb-6">
        <div class="flex items-start gap-6">
          <div class="w-16 h-16 bg-gradient-to-br from-anthropic-orange to-anthropic-orange-dark rounded-2xl flex items-center justify-center shadow-lg flex-shrink-0">
            <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <h1 class="text-2xl font-display font-bold text-dark-300">{{ skill.name }}</h1>
              <span class="text-xs font-medium bg-anthropic-orange-light/20 text-anthropic-orange-dark px-3 py-1 rounded-full">
                {{ skill.category || '文档' }}
              </span>
            </div>
            <p class="text-dark-50 leading-relaxed mb-4">{{ skill.description }}</p>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="tag in skill.tags"
                :key="tag"
                class="text-xs bg-warm-200 text-dark-100 px-3 py-1 rounded-lg"
              >
                {{ tag }}
              </span>
            </div>
          </div>
          <button
            @click="startWriting"
            class="px-6 py-3 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-colors shadow-sm hover:shadow-md flex items-center gap-2 flex-shrink-0"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            开始写作
          </button>
          <button
            @click="confirmDelete"
            class="p-3 bg-warm-100 text-dark-100 rounded-xl hover:bg-red-900/30 hover:text-red-300 transition-colors flex-shrink-0"
            title="删除 Skill"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="bg-warm-50 rounded-2xl border border-warm-300 overflow-hidden">
        <!-- Tab Headers -->
        <div class="flex border-b border-warm-300">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            class="flex-1 px-6 py-4 text-sm font-medium transition-colors relative"
            :class="[
              activeTab === tab.id
                ? 'text-anthropic-orange bg-warm-100'
                : 'text-dark-50 hover:text-dark-300 hover:bg-warm-100/50'
            ]"
          >
            <div class="flex items-center justify-center gap-2">
              <component :is="tab.icon" class="w-5 h-5" />
              {{ tab.label }}
            </div>
            <div
              v-if="activeTab === tab.id"
              class="absolute bottom-0 left-0 right-0 h-0.5 bg-anthropic-orange"
            ></div>
          </button>
        </div>

        <!-- Tab Content -->
        <div class="p-6">
          <!-- Overview Tab -->
          <div v-show="activeTab === 'overview'" class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div class="bg-warm-100 rounded-xl p-5">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-warm-200 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-dark-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
                    </svg>
                  </div>
                  <span class="text-sm font-medium text-dark-100">章节数</span>
                </div>
                <p class="text-2xl font-bold text-dark-300">{{ skill.structure?.length || 0 }}</p>
              </div>
              <div class="bg-warm-100 rounded-xl p-5">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-warm-200 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-dark-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                  </div>
                  <span class="text-sm font-medium text-dark-100">需求字段</span>
                </div>
                <p class="text-2xl font-bold text-dark-300">{{ skill.requirement_fields?.length || 0 }}</p>
              </div>
              <div class="bg-warm-100 rounded-xl p-5">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-warm-200 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-dark-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                  </div>
                  <span class="text-sm font-medium text-dark-100">标签</span>
                </div>
                <p class="text-2xl font-bold text-dark-300">{{ skill.tags?.length || 0 }}</p>
              </div>
            </div>

            <!-- Quick Preview -->
            <div class="bg-warm-100 rounded-xl p-6">
              <h3 class="font-display font-semibold text-dark-300 mb-4">文档结构预览</h3>
              <div class="space-y-2">
                <div
                  v-for="(section, index) in (skill.structure || []).slice(0, 5)"
                  :key="section.id"
                  class="flex items-center gap-3 py-2"
                >
                  <span class="w-6 h-6 bg-anthropic-orange text-white text-xs rounded-lg flex items-center justify-center font-medium">
                    {{ index + 1 }}
                  </span>
                  <span class="text-dark-300">{{ section.title }}</span>
                  <span v-if="section.type === 'optional'" class="text-xs text-warm-400">(可选)</span>
                </div>
                <div v-if="(skill.structure?.length || 0) > 5" class="text-sm text-dark-50 pt-2">
                  还有 {{ skill.structure.length - 5 }} 个章节...
                </div>
              </div>
            </div>
          </div>

          <!-- Structure Tab -->
          <div v-show="activeTab === 'structure'" class="space-y-4">
            <p class="text-dark-50 text-sm mb-4">
              当前 Skill 的文档结构如下，点击章节查看详情。
            </p>
            <div class="space-y-2">
              <div
                v-for="section in skill.structure"
                :key="section.id"
                class="bg-warm-100 rounded-xl overflow-hidden"
              >
                <button
                  @click="toggleSection(section.id)"
                  class="w-full px-5 py-4 flex items-center justify-between hover:bg-warm-200/50 transition-colors"
                >
                  <div class="flex items-center gap-3">
                    <div
                      class="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-medium"
                      :class="section.type === 'required' ? 'bg-anthropic-orange text-white' : 'bg-warm-300 text-dark-100'"
                    >
                      {{ section.level }}
                    </div>
                    <div class="text-left">
                      <span class="font-medium text-dark-300">{{ section.title }}</span>
                      <span v-if="section.type === 'optional'" class="ml-2 text-xs text-warm-400">(可选)</span>
                    </div>
                  </div>
                  <svg
                    class="w-5 h-5 text-dark-50 transition-transform"
                    :class="{ 'rotate-180': expandedSections.has(section.id) }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <div
                  v-show="expandedSections.has(section.id)"
                  class="px-5 pb-4 border-t border-warm-200"
                >
                  <div class="pt-4 space-y-3">
                    <div v-if="section.description">
                      <p class="text-xs font-medium text-dark-50 uppercase tracking-wider mb-1">说明</p>
                      <p class="text-dark-300 text-sm">{{ section.description }}</p>
                    </div>
                    <div v-if="section.writing_guide">
                      <p class="text-xs font-medium text-dark-50 uppercase tracking-wider mb-1">写作指导</p>
                      <p class="text-dark-300 text-sm">{{ section.writing_guide }}</p>
                    </div>
                    <div v-if="section.word_limit" class="flex items-center gap-2">
                      <span class="text-xs font-medium text-dark-50 uppercase tracking-wider">字数范围：</span>
                      <span class="text-sm text-dark-300">{{ section.word_limit[0] }} - {{ section.word_limit[1] }} 字</span>
                    </div>
                    <div v-if="section.evaluation_points?.length > 0">
                      <p class="text-xs font-medium text-dark-50 uppercase tracking-wider mb-2">评审要点</p>
                      <ul class="space-y-1">
                        <li
                          v-for="(point, i) in section.evaluation_points"
                          :key="i"
                          class="text-sm text-dark-300 flex items-start gap-2"
                        >
                          <svg class="w-4 h-4 text-anthropic-orange flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                          </svg>
                          {{ point }}
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Requirements Tab -->
          <div v-show="activeTab === 'requirements'" class="space-y-4">
            <p class="text-dark-50 text-sm mb-4">
              请先填写必填字段，选填与推断字段可提升输出质量。
            </p>
            <div v-if="!hasRequirementFields" class="text-center py-10 text-dark-50">
              <svg class="w-12 h-12 mx-auto mb-3 text-warm-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p>当前 Skill 未配置需求字段。</p>
            </div>
            <div v-else class="space-y-4">
              <div
                v-for="group in requirementGroups"
                :key="group.key"
                class="bg-warm-100 rounded-xl p-5"
              >
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <p class="font-semibold text-dark-300">{{ group.label }}</p>
                    <p class="text-xs text-dark-50">{{ group.description }}</p>
                  </div>
                  <span class="text-xs font-medium px-2.5 py-1 rounded-full" :class="group.badgeClass">
                    {{ group.fields.length }}
                  </span>
                </div>
                <div v-if="group.fields.length === 0" class="text-xs text-warm-400 border border-dashed border-warm-300 rounded-xl py-4 text-center">
                  此分组暂无字段。
                </div>
                <div v-else class="space-y-3">
                  <div
                    v-for="field in group.fields"
                    :key="field.id"
                    class="bg-warm-100 border border-warm-300 rounded-xl p-4"
                  >
                    <div class="flex items-start justify-between mb-2">
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="font-medium text-dark-300">{{ field.name }}</span>
                        <span class="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full" :class="priorityBadgeClass(field)">
                          {{ priorityLabel(field) }}
                        </span>
                        <span v-if="field.collection === 'infer'" class="text-[10px] px-2 py-0.5 rounded-full bg-signal-100 text-signal-700">
                          可推断
                        </span>
                      </div>
                      <span class="text-xs bg-warm-200 text-dark-50 px-2 py-1 rounded-lg">
                        {{ field.field_type }}
                      </span>
                    </div>
                    <p class="text-sm text-dark-50">{{ field.description }}</p>
                    <p v-if="field.example" class="text-xs text-warm-400 mt-2">示例：{{ field.example }}</p>
                    <div v-if="field.options?.length > 0" class="mt-3">
                      <p class="text-xs font-medium text-dark-50 uppercase tracking-wider mb-2">可选项</p>
                      <div class="flex flex-wrap gap-2">
                        <span
                          v-for="option in field.options"
                          :key="option"
                          class="text-xs bg-warm-200 text-dark-100 px-2 py-1 rounded-lg"
                        >
                          {{ option }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Guidelines Tab -->
          <div v-show="activeTab === 'guidelines'">
            <div v-if="skillContent.guidelines" class="prose prose-warm max-w-none">
              <div v-html="renderedGuidelines"></div>
            </div>
            <div v-else class="text-center py-10 text-dark-50">
              <svg class="w-12 h-12 mx-auto mb-3 text-warm-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              <p>该 Skill 暂无写作规范。</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Delete Confirmation Dialog -->
    <div
      v-if="showDeleteDialog"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="cancelDelete"
    >
          <div class="bg-warm-50 rounded-2xl p-6 max-w-md w-full mx-4 shadow-xl border border-warm-300">
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
              确认删除「<span class="font-medium">{{ skill?.name }}</span>」？
              相关文件将被永久移除。
            </p>
            <div class="flex gap-3">
              <button
                @click="cancelDelete"
                class="flex-1 px-4 py-2.5 bg-warm-100 text-dark-100 rounded-xl font-medium hover:bg-warm-200 transition-colors"
                :disabled="deleting"
              >
                取消
              </button>
              <button
                @click="executeDelete"
                class="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-xl font-medium hover:bg-red-500 transition-colors flex items-center justify-center gap-2"
                :disabled="deleting"
              >
            <svg v-if="deleting" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ deleting ? '删除中...' : '删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const skillId = computed(() => route.params.skillId)

// State
const skill = ref(null)
const skillContent = ref({})
const loading = ref(true)
const error = ref(null)
const activeTab = ref('overview')
const expandedSections = reactive(new Set())

// Delete dialog state
const showDeleteDialog = ref(false)
const deleting = ref(false)

// Icon components
const OverviewIcon = {
  render: () => h('svg', { class: 'w-5 h-5', fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z' })
  ])
}

const StructureIcon = {
  render: () => h('svg', { class: 'w-5 h-5', fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 6h16M4 12h16M4 18h7' })
  ])
}

const RequirementsIcon = {
  render: () => h('svg', { class: 'w-5 h-5', fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' })
  ])
}

const GuidelinesIcon = {
  render: () => h('svg', { class: 'w-5 h-5', fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' })
  ])
}

const tabs = [
  { id: 'overview', label: '概览', icon: OverviewIcon },
  { id: 'structure', label: '结构', icon: StructureIcon },
  { id: 'requirements', label: '需求', icon: RequirementsIcon },
  { id: 'guidelines', label: '规范', icon: GuidelinesIcon },
]

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
  if (priority === 1) return 'bg-red-900/30 text-red-300'
  if (priority === 2) return 'bg-yellow-900/30 text-yellow-300'
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
const renderedGuidelines = computed(() => {
  if (!skillContent.value.guidelines) return ''
  return marked(skillContent.value.guidelines)
})

const hasRequirementFields = computed(() => {
  return (skill.value?.requirement_fields?.length || 0) > 0
})

const requirementGroups = computed(() => {
  const fields = skill.value?.requirement_fields || []
  const required = sortFields(fields.filter((field) => getFieldCollection(field) === 'required'))
  const optional = sortFields(fields.filter((field) => getFieldCollection(field) === 'optional'))
  const infer = sortFields(fields.filter((field) => getFieldCollection(field) === 'infer'))

  return [
    {
      key: 'required',
      label: '必填字段',
      description: '生成前必须提供。',
      badgeClass: 'bg-red-900/30 text-red-300',
      fields: required
    },
    {
      key: 'optional',
      label: '选填字段',
      description: '可选填写，有助于提升质量。',
      badgeClass: 'bg-warm-200 text-dark-50',
      fields: optional
    },
    {
      key: 'infer',
      label: '可推断字段',
      description: '优先从材料中抽取。',
      badgeClass: 'bg-signal-100 text-signal-700',
      fields: infer
    }
  ]
})

// Methods
const fetchSkill = async () => {
  loading.value = true
  error.value = null

  try {
    // Fetch basic skill info
    const response = await api.get(`/skills/${skillId.value}`)
    skill.value = response.data

    // Fetch full content
    try {
      const contentResponse = await api.get(`/skills/${skillId.value}/content`)
      skillContent.value = contentResponse.data
    } catch (e) {
      // Content endpoint might not exist, that's okay
      skillContent.value = {}
    }
  } catch (e) {
    console.error('Failed to fetch skill:', e)
    error.value = e.response?.data?.detail || '加载技能详情失败'
  } finally {
    loading.value = false
  }
}

const toggleSection = (sectionId) => {
  if (expandedSections.has(sectionId)) {
    expandedSections.delete(sectionId)
  } else {
    expandedSections.add(sectionId)
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
    // Redirect to home after successful deletion
    router.push('/')
  } catch (e) {
    console.error('Failed to delete skill:', e)
    alert(e.response?.data?.detail || '删除失败，请重试。')
  } finally {
    deleting.value = false
    showDeleteDialog.value = false
  }
}

// Lifecycle
onMounted(() => {
  fetchSkill()
})
</script>

<style scoped>
.border-3 {
  border-width: 3px;
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

.prose :deep(h1),
.prose :deep(h2),
.prose :deep(h3) {
  color: #F8FAFC;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}

.prose :deep(h1) { font-size: 1.5rem; }
.prose :deep(h2) { font-size: 1.25rem; }
.prose :deep(h3) { font-size: 1.125rem; }

.prose :deep(p) {
  margin-bottom: 1rem;
  line-height: 1.75;
}

.prose :deep(ul),
.prose :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

.prose :deep(li) {
  margin-bottom: 0.5rem;
}

.prose :deep(code) {
  background-color: #1B2230;
  padding: 0.125rem 0.375rem;
  border-radius: 0.375rem;
  font-size: 0.875em;
}

.prose :deep(pre) {
  background-color: #0B0F14;
  border-radius: 0.75rem;
  padding: 1rem;
  overflow-x: auto;
}

.prose :deep(blockquote) {
  border-left: 3px solid #E36A3A;
  background-color: #141A21;
  padding: 1rem;
  margin: 1rem 0;
  border-radius: 0 0.5rem 0.5rem 0;
}
</style>
