import { defineConfig } from '@playwright/test'

if (!process.env.C04_RISK_LIVE_ROOT) throw new Error('C04_RISK_LIVE_ROOT must name the disposable build/receipt directory')

export default defineConfig({
  testDir: './e2e', testMatch: 'risk-live.spec.ts', workers: 1, retries: 0,
  timeout: 30_000,
  use: { baseURL: 'http://localhost:8857', browserName: 'chromium', viewport: { width: 1440, height: 900 } },
  webServer: {
    command: 'python scripts/run_c04_risk_live_acceptance.py',
    cwd: '../../..', url: 'http://localhost:8857/healthz', timeout: 30_000, reuseExistingServer: false,
  },
})
