import { defineConfig } from '@playwright/test'

const rawPort = process.env.ALPHA_PLAYWRIGHT_PORT ?? '8802'
const port = Number(rawPort)
if (!/^[0-9]{4,5}$/.test(rawPort) || port < 1024 || port > 65535 || port === 8801) {
  throw new Error('ALPHA_PLAYWRIGHT_PORT must be 1024..65535, excluding owner port 8801')
}
const baseURL = `http://localhost:${port}/`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  // All viewport projects share one isolated real-backend control store. Serial execution keeps
  // their CLI-backed research writes deterministic instead of contending for the writer lock.
  workers: 1,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  timeout: 30_000,
  snapshotPathTemplate: '{testDir}/{testFileName}-snapshots/{arg}{-projectName}{ext}',
  expect: { timeout: 5_000 },
  use: {
    baseURL,
    browserName: 'chromium',
    colorScheme: 'dark',
    contextOptions: { reducedMotion: 'reduce' },
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium-minimum',
      grepInvert: /@reference-only/,
      use: { viewport: { width: 1280, height: 720 } },
    },
    {
      name: 'chromium-reference',
      grepInvert: /@reference-only/,
      use: { viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'chromium-wide',
      grepInvert: /@reference-only/,
      use: { viewport: { width: 1920, height: 1080 } },
    },
    {
      name: 'chromium-reference-only',
      dependencies: ['chromium-minimum', 'chromium-reference', 'chromium-wide'],
      grep: /@reference-only/,
      use: { viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: 'uv run python scripts/run_playwright_backend.py',
    cwd: '../../..',
    url: baseURL,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
