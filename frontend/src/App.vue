<template>
  <div class="app-shell min-h-screen text-dark-300">
    <div class="flex min-h-screen flex-col">
      <!-- Header -->
      <header class="border-b border-warm-300 bg-warm-50">
        <div class="max-w-6xl mx-auto px-6 py-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <router-link to="/" class="flex items-center space-x-3 group">
            <div class="w-10 h-10 bg-gradient-to-br from-anthropic-orange to-anthropic-orange-dark rounded-xl flex items-center justify-center shadow-sm group-hover:shadow-lg transition-shadow">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
            <div>
              <span class="text-xl font-display font-semibold text-dark-300 tracking-tight">SkillWriter</span>
              <p class="text-xs text-dark-50">多智能体协同写作</p>
            </div>
          </router-link>
          <nav class="flex flex-wrap items-center gap-2 text-sm font-medium">
            <router-link
              to="/"
              class="px-3 py-1.5 rounded-full transition-colors"
              :class="$route.path === '/' ? 'bg-anthropic-orange/10 text-anthropic-orange-dark' : 'text-dark-100 hover:bg-warm-200/70 hover:text-dark-300'"
            >
              技能
            </router-link>
            <router-link
              to="/documents"
              class="px-3 py-1.5 rounded-full transition-colors"
              :class="$route.path === '/documents' ? 'bg-anthropic-orange/10 text-anthropic-orange-dark' : 'text-dark-100 hover:bg-warm-200/70 hover:text-dark-300'"
            >
              文档
            </router-link>
            <router-link
              to="/settings"
              class="px-3 py-1.5 rounded-full transition-colors flex items-center gap-1.5"
              :class="$route.path === '/settings' ? 'bg-anthropic-orange/10 text-anthropic-orange-dark' : 'text-dark-100 hover:bg-warm-200/70 hover:text-dark-300'"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              设置
            </router-link>
          </nav>
        </div>
      </header>

      <!-- Main Content -->
      <main
        class="mx-auto px-6 py-10 flex-1 min-h-0"
        :class="isWideLayout ? 'max-w-none w-full' : 'max-w-6xl'"
      >
        <router-view />
      </main>

      <!-- Footer -->
      <footer class="border-t border-warm-300 bg-warm-50">
        <div class="max-w-6xl mx-auto px-6 py-6 text-center text-sm text-dark-50">
          由多智能体工作流编排驱动
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isWideLayout = computed(() => route.path.startsWith('/write'))
</script>
