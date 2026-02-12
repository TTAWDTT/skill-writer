<template>
  <Transition name="fade">
    <div
      v-if="visible"
      class="selection-menu selection-menu-card fixed z-[80] flex items-center gap-1.5 px-2 py-1.5 bg-warm-50/95 backdrop-blur rounded-xl shadow-lg border border-warm-300 text-dark-200 transform -translate-x-1/2 -translate-y-full mb-2"
      :style="{ top: `${position.top}px`, left: `${position.left}px` }"
      @mousedown.stop
    >
      <button
        type="button"
        @click="$emit('generate', 'infographic')"
        class="menu-action-btn px-3 py-1.5 text-xs font-semibold text-dark-200 hover:bg-warm-200 rounded-lg transition-colors flex items-center gap-2 whitespace-nowrap"
        title="生成信息图风格（PNG）"
      >
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        生成图示
      </button>
      <div class="w-px h-5 bg-warm-300 mx-0.5"></div>
      <button
        type="button"
        @click="$emit('generate', 'technical_route')"
        class="menu-action-btn px-3 py-1.5 text-xs font-medium text-dark-100 hover:bg-warm-200 rounded-lg transition-colors whitespace-nowrap"
      >
        技术路线
      </button>
      <button
        type="button"
        @click="$emit('generate', 'research_framework')"
        class="menu-action-btn px-3 py-1.5 text-xs font-medium text-dark-100 hover:bg-warm-200 rounded-lg transition-colors whitespace-nowrap"
      >
        框架图
      </button>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  visible: Boolean,
  position: {
    type: Object,
    default: () => ({ top: 0, left: 0 })
  }
})

defineEmits(['generate'])
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -90%);
}

.selection-menu-card {
  animation: menu-lift-in 0.16s ease-out;
}

@keyframes menu-lift-in {
  from { opacity: 0; transform: translate(-50%, -86%) scale(0.96); }
  to { opacity: 1; transform: translate(-50%, -100%) scale(1); }
}

.menu-action-btn {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.menu-action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(2, 6, 23, 0.14);
}
</style>
