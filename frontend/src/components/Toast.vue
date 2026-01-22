<template>
  <Transition name="toast">
    <div v-if="show" class="fixed top-24 right-6 z-50">
      <div class="flex items-start gap-3 rounded-2xl border border-warm-300 bg-warm-50 px-4 py-3 shadow-lg">
        <div class="w-9 h-9 rounded-xl bg-amber-900/30 text-amber-300 flex items-center justify-center">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3m0 4h.01M12 3l9 16H3l9-16z" />
          </svg>
        </div>
        <div class="min-w-[180px]">
          <p class="text-sm font-semibold text-dark-300">{{ title }}</p>
          <p v-if="message" class="text-xs text-dark-50 mt-0.5">{{ message }}</p>
        </div>
        <button
          type="button"
          class="text-dark-50 hover:text-dark-300 transition-colors"
          @click="$emit('close')"
          aria-label="关闭"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '' },
  message: { type: String, default: '' }
})

defineEmits(['close'])
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}
</style>
