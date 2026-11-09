import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages(/san-signal/)와 로컬 모두에서 동작하도록 상대 경로로 빌드한다.
export default defineConfig({
  base: './',
  plugins: [vue()],
})
