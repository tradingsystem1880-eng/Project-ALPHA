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
      // Pure render-state models are the unit-test authority. React panels and workflows
      // are exercised in the built application by Playwright instead of being diluted
      // into a misleading repository-wide percentage.
      include: [
        'src/context/panelLinkModel.ts',
        'src/panels/chartTableModel.ts',
        'src/panels/codexBenchModel.ts',
        'src/panels/durableJobs.ts',
        'src/panels/jobProgress.ts',
        'src/panels/mlTearsheetModel.ts',
        'src/panels/paperModel.ts',
        'src/panels/portfolioModels.ts',
        'src/panels/researchBacklogModel.ts',
        'src/panels/researchCockpitModel.ts',
        'src/panels/researchDataModel.ts',
        'src/panels/v3Models.ts',
        'src/panels/workspaceModel.ts',
      ],
      exclude: ['src/api/generated.ts', 'src/**/*.test.ts'],
      thresholds: {
        statements: 85,
        branches: 70,
        functions: 85,
        lines: 85,
      },
    },
  },
})
