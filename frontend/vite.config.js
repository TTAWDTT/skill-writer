import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    // Chunk size warning limit
    chunkSizeWarningLimit: 500,
    // Minification
    minify: 'esbuild',
    // Target modern browsers for smaller bundle
    target: 'es2020',
    // Rollup options for code splitting
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        manualChunks: {
          // Vue core in separate chunk
          'vue-vendor': ['vue', 'vue-router'],
          // Markdown parser in separate chunk (lazy loaded)
          'markdown': ['marked'],
        },
        // Asset file naming for better caching
        assetFileNames: 'assets/[name]-[hash][extname]',
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
      }
    },
    // CSS code splitting
    cssCodeSplit: true,
    // Source maps in production (disable for smaller builds)
    sourcemap: false,
  },
  // Optimize dependencies
  optimizeDeps: {
    include: ['vue', 'vue-router', 'axios', 'marked', 'pinia'],
  },
  // CSS optimization
  css: {
    devSourcemap: true,
  },
})
