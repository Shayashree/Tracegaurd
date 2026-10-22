import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': 'http://127.0.0.1:8000',
      '/tasks': 'http://127.0.0.1:8000',
      '/benchmarks': 'http://127.0.0.1:8000',
      '/experiments': 'http://127.0.0.1:8000',
      '/diagnostics': 'http://127.0.0.1:8000',
      '/recovery': 'http://127.0.0.1:8000',
      '/runs': 'http://127.0.0.1:8000',
    },
  },
  // @ts-expect-error vitest options
  test: {
    globals: true,
    environment: 'jsdom',
  },
})
