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
    baseURL: 'http://127.0.0.1:4173/static/app/',
    browserName: 'chromium',
    colorScheme: 'dark',
    contextOptions: { reducedMotion: 'reduce' },
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium-minimum', use: { viewport: { width: 1280, height: 720 } } },
    { name: 'chromium-reference', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'chromium-wide', use: { viewport: { width: 1920, height: 1080 } } },
  ],
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173/static/app/',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
