<template>
  <Transition name="fade">
    <div
      v-if="visible"
      class="fixed z-50 flex items-center gap-1 p-1 bg-dark-300 rounded-lg shadow-xl border border-warm-300 transform -translate-x-1/2 -translate-y-full mb-2"
      :style="{ top: `${position.top}px`, left: `${position.left}px` }"
      @mousedown.stop
    >
      <button
        type="button"
        @click="$emit('generate', 'infographic')"
        class="px-3 py-1.5 text-xs font-medium text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-2"
        title="Generate Infographic (SVG)"
      >
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        生成图示
      </button>
      <div class="w-px h-4 bg-white/20 mx-1"></div>
      <button
        type="button"
        @click="$emit('generate', 'technical_route')"
        class="px-3 py-1.5 text-xs font-medium text-white hover:bg-white/10 rounded-md transition-colors"
      >
        技术路线
      </button>
      <button
        type="button"
        @click="$emit('generate', 'research_framework')"
        class="px-3 py-1.5 text-xs font-medium text-white hover:bg-white/10 rounded-md transition-colors"
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
</style>
