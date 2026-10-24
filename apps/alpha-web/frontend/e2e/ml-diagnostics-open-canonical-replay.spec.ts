import { expect, test, type Page } from '@playwright/test'

import { preparePage } from './support/workstationHarness'

const PRIOR_RUN_ID = 'aaaaaaaaaaaaaaaa'
const CANONICAL_REPLAY_ID = '0123456789abcdef'
const EXPERIMENT_ID = 'a'.repeat(32)

async function mockRunUnavailable(page: Page, runId: string): Promise<void> {
  await page.route(`**/api/runs/${runId}**`, async (route) => {
    await route.fulfill({ status: 404, json: { detail: 'Run is unavailable in this fixture' } })
  })
}

test('ML diagnostics opens the exact canonical replay report', async ({ page }) => {
  await preparePage(page, { mlDiagnostics: true })
  await mockRunUnavailable(page, PRIOR_RUN_ID)
  let canonicalRunRequests = 0
  await page.route(`**/api/runs/${CANONICAL_REPLAY_ID}`, async (route) => {
    canonicalRunRequests += 1
    await route.fulfill({
      json: {
        run_id: CANONICAL_REPLAY_ID,
        kind: 'portfolio',
        mtime: 1,
        display_name: 'canonical replay fixture',
        market: 'unknown',
        manifest: { command: 'backtest_portfolio', symbols: ['SPY'] },
        research_gate_watermark: null,
        run_context_kind: 'standalone_sandbox',
        run_context_project_id: null,
        run_context_watermark: null,
        has_equity: false,
        has_trades: false,
        has_tearsheet: false,
        has_forecast: false,
        has_nulls: false,
        has_trials: false,
        has_forecast_paths: false,
        has_propfirm_paths: false,
        has_origins: false,
        has_portfolio_analytics: false,
      },
    })
  })
  await page.route(`**/api/runs/${CANONICAL_REPLAY_ID}/**`, async (route) => {
    await route.fulfill({ status: 404, json: { detail: 'Optional report data is unavailable in this fixture' } })
  })
  await page.route('**/api/ml/experiments', async (route) => {
    await route.fulfill({
      json: {
        items: [{
          experiment_id: EXPERIMENT_ID,
          project_id: null,
          status: 'trained',
          universe_size: 20,
          aligned_sessions: 756,
          feature_recipe: 'alpha158',
          model: 'lightgbm',
          folds: 1,
          snapshot_hash: 'b'.repeat(64),
          config_hash: 'c'.repeat(64),
          replay_run_id: CANONICAL_REPLAY_ID,
          diagnostic_only: true,
          counterfactual_refit: false,
          metrics: { ic: 0.042, rank_ic: 0.051, turnover: 0.08, costed_return: 0.11 },
        }],
        limit: 50,
        offset: 0,
        has_more: false,
      },
    })
  })
  await page.evaluate((priorRunId) => {
    window.location.hash = `#page=results&pane=MlDiagnostics&run=${priorRunId}`
  }, PRIOR_RUN_ID)

  await expect(page.getByLabel('ML diagnostic experiment')).toHaveValue(EXPERIMENT_ID)
  await expect(page.getByText(/OOS replay validated/)).toBeVisible()
  await page.getByRole('button', { name: 'Open canonical replay' }).click()

  await expect.poll(() => page.evaluate(() => window.location.hash)).toBe(
    `#page=results&pane=RunDetail&run=${CANONICAL_REPLAY_ID}`,
  )
  await expect.poll(() => canonicalRunRequests).toBeGreaterThan(0)
  await expect(page.locator('.document-tabs').getByRole('tab', { name: /^Report(?: ·|$)/ }))
    .toHaveAttribute('aria-selected', 'true')
})

test('ML diagnostics opens the exact replay route when the replay report is unavailable', async ({ page }) => {
  await preparePage(page, { mlDiagnostics: true })
  await mockRunUnavailable(page, PRIOR_RUN_ID)
  let unavailableReplayRequests = 0
  await page.route(`**/api/runs/${CANONICAL_REPLAY_ID}**`, async (route) => {
    unavailableReplayRequests += 1
    await route.fulfill({ status: 404, json: { detail: 'Run is unavailable in this fixture' } })
  })
  await page.route('**/api/ml/experiments', async (route) => {
    await route.fulfill({
      json: {
        items: [{
          experiment_id: EXPERIMENT_ID,
          project_id: null,
          status: 'trained',
          universe_size: 20,
          aligned_sessions: 756,
          feature_recipe: 'alpha158',
          model: 'lightgbm',
          folds: 1,
          snapshot_hash: 'b'.repeat(64),
          config_hash: 'c'.repeat(64),
          replay_run_id: CANONICAL_REPLAY_ID,
          diagnostic_only: true,
          counterfactual_refit: false,
          metrics: { ic: 0.042, rank_ic: 0.051, turnover: 0.08, costed_return: 0.11 },
        }],
        limit: 50,
        offset: 0,
        has_more: false,
      },
    })
  })
  await page.evaluate((priorRunId) => {
    window.location.hash = `#page=results&pane=MlDiagnostics&run=${priorRunId}`
  }, PRIOR_RUN_ID)

  await expect(page.getByLabel('ML diagnostic experiment')).toHaveValue(EXPERIMENT_ID)
  await expect(page.getByText(/OOS replay validated/)).toBeVisible()
  await page.getByRole('button', { name: 'Open canonical replay' }).click()

  await expect.poll(() => page.evaluate(() => window.location.hash)).toBe(
    `#page=results&pane=RunDetail&run=${CANONICAL_REPLAY_ID}`,
  )
  await expect.poll(() => unavailableReplayRequests).toBeGreaterThan(0)
  await expect(page.locator('.document-tabs').getByRole('tab', { name: /^Report(?: ·|$)/ }))
    .toHaveAttribute('aria-selected', 'true')
})

test('ML diagnostics keeps the current route when no canonical replay is available', async ({ page }) => {
  await preparePage(page, { mlDiagnostics: true })
  await mockRunUnavailable(page, PRIOR_RUN_ID)
  await page.evaluate((priorRunId) => {
    window.location.hash = `#page=results&pane=MlDiagnostics&run=${priorRunId}`
  }, PRIOR_RUN_ID)

  await expect(page.getByLabel('ML diagnostic experiment')).toHaveValue(EXPERIMENT_ID)
  await expect(page.getByText(/OOS replay validated/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open canonical replay' })).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => window.location.hash)).toBe(
    `#page=results&pane=MlDiagnostics&run=${PRIOR_RUN_ID}`,
  )
})
