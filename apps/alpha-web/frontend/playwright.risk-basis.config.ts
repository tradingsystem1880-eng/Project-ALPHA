import { defineConfig } from '@playwright/test'

// Source-only functional checks: Vite transforms these risk consumers, without
// rebuilding or writing the shared production SPA or invoking a model/backend.
export default defineConfig({
  testDir: './e2e',
  testMatch: 'risk-metric-basis.spec.ts',
  workers: 1,
  retries: 0,
  use: { baseURL: 'http://127.0.0.1:8847', browserName: 'chromium', viewport: { width: 1280, height: 720 } },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 8847 --strictPort --base /',
    url: 'http://127.0.0.1:8847/e2e/risk-metric-basis.html',
    reuseExistingServer: false,
  },
})
