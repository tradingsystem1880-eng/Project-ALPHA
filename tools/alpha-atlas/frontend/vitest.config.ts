import { defineConfig } from 'vitest/config'

// Pure model tests only — node environment, no jsdom, no component tests.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
