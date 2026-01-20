<template>
  <div class="min-h-screen bg-warm-100">
    <!-- Header -->
    <header class="bg-warm-50 border-b border-warm-300">
      <div class="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <router-link to="/" class="flex items-center space-x-3 group">
          <div class="w-9 h-9 bg-anthropic-orange rounded-xl flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </div>
          <span class="text-xl font-semibold text-dark-300">SkillWriter</span>
        </router-link>
        <nav class="flex items-center space-x-8">
          <router-link
            to="/"
            class="text-dark-100 hover:text-anthropic-orange transition-colors font-medium"
            :class="{ 'text-anthropic-orange': $route.path === '/' }"
          >
            Skills
          </router-link>
          <router-link
            to="/documents"
            class="text-dark-100 hover:text-anthropic-orange transition-colors font-medium"
            :class="{ 'text-anthropic-orange': $route.path === '/documents' }"
          >
            Documents
          </router-link>
          <router-link
            to="/settings"
            class="text-dark-100 hover:text-anthropic-orange transition-colors font-medium flex items-center gap-1.5"
            :class="{ 'text-anthropic-orange': $route.path === '/settings' }"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </router-link>
        </nav>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-6xl mx-auto px-6 py-8">
      <router-view />
    </main>

    <!-- Footer -->
    <footer class="border-t border-warm-300 bg-warm-50 mt-auto">
      <div class="max-w-6xl mx-auto px-6 py-6 text-center text-sm text-warm-400">
        Powered by AI
      </div>
    </footer>
  </div>
</template>

<script setup>
</script>

<style>
/* 全局样式 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

/* 平滑滚动 */
html {
  scroll-behavior: smooth;
}

/* 选中文本颜色 */
::selection {
  background-color: rgba(217, 119, 87, 0.2);
}
</style>
