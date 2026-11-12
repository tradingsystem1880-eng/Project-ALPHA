import { defineConfig } from '@playwright/test'
// Dedicated real-backend fixture supplied by test_native_result_web.py. No default seeder.
export default defineConfig({
  testDir: './e2e', testMatch: 'native-result-real.spec.ts', workers: 1, retries: 0,
  reporter: 'list', timeout: 120_000,
  expect: { timeout: 15_000 },
  outputDir: process.env.ALPHA_NATIVE_WEB_OUTPUT,
  use: { browserName: 'chromium', actionTimeout: 10_000, navigationTimeout: 20_000, viewport: { width: 1280, height: 900 }, trace: 'retain-on-failure' },
})
