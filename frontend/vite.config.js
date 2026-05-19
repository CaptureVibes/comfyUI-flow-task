import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/echo-matrix/',
  server: {
    port: 5173,
    host: true,
    origin: 'http://localhost:5173/echo-matrix/',
    allowedHosts: ['echoootx.top', 'www.echoootx.top']
  },
  build: {
    // 生成 sourcemap 方便调试
    sourcemap: true,
    // 提高 chunk 限制警告
    chunkSizeWarningLimit: 1000
  }
})
