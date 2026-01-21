<template>
  <Transition name="toast">
    <div v-if="show" class="fixed top-24 right-6 z-50">
      <div class="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 shadow-lg">
        <div class="w-9 h-9 rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3m0 4h.01M12 3l9 16H3l9-16z" />
          </svg>
        </div>
        <div class="min-w-[180px]">
          <p class="text-sm font-semibold text-amber-800">{{ title }}</p>
          <p v-if="message" class="text-xs text-amber-700 mt-0.5">{{ message }}</p>
        </div>
        <button
          type="button"
          class="text-amber-600 hover:text-amber-800 transition-colors"
          @click="$emit('close')"
          aria-label="Close"
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
