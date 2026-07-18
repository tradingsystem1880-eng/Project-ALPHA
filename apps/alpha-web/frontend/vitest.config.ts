// Local-only unit tests for pure modules (explanation engine, utils, store reducers).
// Node environment on purpose: no jsdom, no component tests — CI stays Node-free; run
// `npm test` before `npm run build` as part of the pre-commit ritual for frontend changes.

import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/api/generated.ts', 'src/**/*.test.ts'],
      thresholds: {
        statements: 11,
        branches: 14,
        functions: 7,
        lines: 11,
      },
    },
  },
})
