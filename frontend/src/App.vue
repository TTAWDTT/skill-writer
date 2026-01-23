<template>
  <div
    class="app-shell text-dark-300 min-h-screen"
    :class="isWideLayout ? 'lg:h-screen lg:overflow-hidden' : ''"
  >
    <div class="flex flex-col min-h-screen" :class="isWideLayout ? 'lg:h-full' : ''">
      <!-- Header -->
      <header class="border-b border-white/10 bg-warm-50/60 backdrop-blur supports-[backdrop-filter]:bg-warm-50/40">
        <div class="max-w-6xl mx-auto px-6 py-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <router-link to="/" class="flex items-center space-x-3 group">
            <div class="w-10 h-10 bg-anthropic-orange/90 rounded-xl flex items-center justify-center shadow-sm group-hover:shadow-lg transition-shadow">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
            <div>
              <span class="text-xl font-display font-semibold text-dark-300 tracking-tight">SkillWriter</span>
              <p class="text-xs text-dark-50">多智能体协同写作</p>
            </div>
          </router-link>
          <nav class="flex flex-wrap items-center gap-4 text-sm font-medium">
            <router-link
              to="/"
              class="relative px-1 py-1.5 transition-colors text-dark-100 hover:text-dark-300"
              :class="$route.path === '/' ? 'text-dark-300' : ''"
            >
              <span>技能</span>
              <span v-if="$route.path === '/'" class="absolute left-0 right-0 -bottom-0.5 h-0.5 bg-anthropic-orange rounded-full"></span>
            </router-link>
            <router-link
              to="/documents"
              class="relative px-1 py-1.5 transition-colors text-dark-100 hover:text-dark-300"
              :class="$route.path === '/documents' ? 'text-dark-300' : ''"
            >
              <span>文档</span>
              <span v-if="$route.path === '/documents'" class="absolute left-0 right-0 -bottom-0.5 h-0.5 bg-anthropic-orange rounded-full"></span>
            </router-link>
            <router-link
              to="/settings"
              class="relative px-1 py-1.5 transition-colors flex items-center gap-1.5 text-dark-100 hover:text-dark-300"
              :class="$route.path === '/settings' ? 'text-dark-300' : ''"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              设置
              <span v-if="$route.path === '/settings'" class="absolute left-0 right-0 -bottom-0.5 h-0.5 bg-anthropic-orange rounded-full"></span>
            </router-link>
          </nav>
        </div>
      </header>

      <!-- Main Content -->
      <main
        class="mx-auto px-6 flex-1 min-h-0 flex flex-col"
        :class="[
          isWideLayout ? 'max-w-none w-full py-6 lg:overflow-hidden' : 'max-w-6xl py-10'
        ]"
      >
        <div class="flex flex-col flex-1 min-h-0" :class="isWideLayout ? 'lg:overflow-hidden' : ''">
          <router-view />
        </div>
      </main>

      <!-- Footer -->
      <footer class="border-t border-white/10 bg-warm-50/60 backdrop-blur supports-[backdrop-filter]:bg-warm-50/40">
        <div class="max-w-6xl mx-auto px-6 py-6 text-center text-sm text-dark-50">
          designed by TTAWDTT
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, watchEffect } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isWideLayout = computed(() => route.path.startsWith('/write'))

watchEffect(() => {
  if (typeof document === 'undefined') return
  document.body.classList.toggle('route-write', isWideLayout.value)
  document.documentElement.classList.toggle('route-write', isWideLayout.value)
})
</script>
