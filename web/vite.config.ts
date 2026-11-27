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
  },
})
