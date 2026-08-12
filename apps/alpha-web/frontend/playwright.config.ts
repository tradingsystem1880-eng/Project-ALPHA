import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  timeout: 30_000,
  snapshotPathTemplate: '{testDir}/{testFileName}-snapshots/{arg}{-projectName}{ext}',
  expect: { timeout: 5_000 },
  use: {
    baseURL: 'http://localhost:8802/',
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
    url: 'http://localhost:8802/',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
