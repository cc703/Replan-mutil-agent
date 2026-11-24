import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

const proxy = { '/api/v1': process.env.P7_SPRING_URL ?? 'http://127.0.0.1:8080' }
export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', proxy },
  preview: { host: '127.0.0.1', proxy },
  test: { include: ['tests/**/*.test.ts'], environment: 'jsdom' },
})
