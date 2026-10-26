import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev : `npm run dev`, l'API tourne dans Docker sur 127.0.0.1:8000 (nginx fait le même /api en prod)
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: (p) => p.replace(/^\/api/, '') } },
  },
})
