import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Relative paths so Electron can load assets via file://
  base: './',
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/ask': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/email': 'http://127.0.0.1:8000',
      '/standup': 'http://127.0.0.1:8000',
      '/jobs': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
