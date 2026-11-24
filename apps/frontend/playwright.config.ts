import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  timeout: 70_000,
  fullyParallel: false,
  use: { actionTimeout: 8_000, baseURL: process.env.P7_FRONTEND_URL ?? 'http://127.0.0.1:5173' },
})
