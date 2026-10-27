import { expect, test } from '@playwright/test'

import { openDocument, preparePage } from './support/workstationHarness'

test('ML model selection relays Linear estimator and exposes dependency blockers', async ({ page }) => {
  await preparePage(page)
  // Choose a project through the existing Research Case route before opening ML.
  await page.getByLabel('Project context', { exact: true }).selectOption({ label: 'SPY double bottom' })
  await page.route('**/api/ml/experiments/preflight?*', async (route) => {
    await route.fulfill({ json: {
      schema_version: 1, project_id: 'project-1', experiment_id: `ex_${'a'.repeat(64)}`,
      snapshot_id: 'snapshot-1', universe_count: 20, aligned_sessions: 756,
      active_job_id: null, ready: true, checks: [],
    } })
  })
  let generated: unknown = null
  await page.route('**/api/ml/experiments', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({ json: { items: [], limit: 50, offset: 0, has_more: false } })
      return
    }
    generated = route.request().postDataJSON()
    await route.fulfill({ status: 202, json: {
      job_id: 'tabular-test-job', status: 'queued', action: 'generate-experiment',
      project_id: 'project-1', experiment_id: `ex_${'a'.repeat(64)}`,
      input_bundle_id: 'b'.repeat(32), exchange_id: 'c'.repeat(32),
    } })
  })
  await page.route('**/api/development/jobs/tabular-test-job?*', async (route) => {
    await route.fulfill({ json: { status: 'running' } })
  })
  await openDocument(page, 'Machine learning')
  const generate = page.getByRole('button', { name: 'Generate preflighted ML experiment' })
  await page.getByLabel('ML model', { exact: true }).selectOption('catboost')
  await expect(page.getByLabel('Selected ML backend capability')).toContainText('catboost is not installed')
  await expect(generate).toBeDisabled()
  await page.getByLabel('ML model', { exact: true }).selectOption('xgboost')
  await expect(page.getByLabel('Selected ML backend capability')).toContainText('unsupported xgboost version')
  await expect(generate).toBeDisabled()
  await page.getByLabel('ML model', { exact: true }).selectOption('linear')
  await page.getByLabel('Linear estimator').selectOption('lasso')
  await expect(generate).toBeEnabled()
  await generate.click()
  await expect.poll(() => generated).toMatchObject({ model: 'linear', parameters: { estimator: 'lasso' } })
})

test('ML generation keeps the experiment recipe by default', async ({ page }) => {
  await preparePage(page)
  await page.getByLabel('Project context', { exact: true }).selectOption({ label: 'SPY double bottom' })
  await page.route('**/api/ml/experiments/preflight?*', async (route) => {
    await route.fulfill({ json: {
      schema_version: 1, project_id: 'project-1', experiment_id: `ex_${'a'.repeat(64)}`,
      snapshot_id: 'snapshot-1', universe_count: 20, aligned_sessions: 756,
      active_job_id: null, ready: true, checks: [],
    } })
  })
  let generated: unknown = null
  await page.route('**/api/ml/experiments', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({ json: { items: [], limit: 50, offset: 0, has_more: false } })
      return
    }
    generated = route.request().postDataJSON()
    await route.fulfill({ status: 202, json: {
      job_id: 'recipe-test-job', status: 'queued', action: 'generate-experiment',
      project_id: 'project-1', experiment_id: `ex_${'a'.repeat(64)}`,
      input_bundle_id: 'b'.repeat(32), exchange_id: 'c'.repeat(32),
    } })
  })
  await page.route('**/api/development/jobs/recipe-test-job?*', async (route) => {
    await route.fulfill({ json: { status: 'running' } })
  })
  await openDocument(page, 'Machine learning')
  await expect(page.getByLabel('ML model', { exact: true })).toHaveValue('experiment_recipe')
  await expect(page.getByLabel('Selected ML backend capability')).toContainText('No model override')
  await page.getByRole('button', { name: 'Generate preflighted ML experiment' }).click()
  await expect.poll(() => generated && Object.keys(generated).sort()).toEqual(['project_id'])
})

for (const scoreStatus of ['degenerate', 'ties_present'] as const) {
  test(`ML diagnostics explain ${scoreStatus} score grouping`, async ({ page }) => {
    await preparePage(page, { mlDiagnostics: true })
    const reason = scoreStatus === 'degenerate'
      ? 'All model scores are identical; quantile grouping is unavailable.'
      : 'Cross-sections with tied scores are omitted from quantile grouping.'
    await page.route('**/api/ml/exchanges/*/tear-sheet?*', async (route) => {
      await route.fulfill({ json: {
        available: true, exchange_id: 'a'.repeat(32), authority: 'qlib_diagnostic_only',
        label: 'Predictive diagnostics only', membership_status: 'current_membership_warning',
        counterfactual_refit: false, model_backend: 'linear', versions: null,
        feature_recipe: null, label_recipe: null, score_distribution: null, ic: null,
        quantile_returns: [], portfolio: null, feature_importance: [],
        feature_importance_truncated: false, folds: [], timeline_total: 0,
        timeline_offset: 0, timeline_limit: 500, timeline_has_more: false,
        diagnostic_state: {
          score_status: scoreStatus, reason, degenerate_cross_sections: 1,
          tied_cross_sections: 2, quantile_cross_sections: 0,
        },
      } })
    })
    await page.evaluate(() => { window.location.hash = '#page=results&pane=MlDiagnostics' })
    await expect(page.getByLabel('Model score diagnostic state')).toContainText(reason)
    await expect(page.getByLabel('Model score diagnostic state')).toContainText('QUANTILE 0')
    await expect(page.getByText('QUANTILE RETURNS NOT EMITTED', { exact: false })).toBeVisible()
  })
}


test('ML experiment list separates prepared inputs, predictions and recorded replay', async ({ page }) => {
  await preparePage(page)
  await page.route('**/api/ml/experiments', async (route) => {
    const base = {
      project_id: null, universe_size: 20, aligned_sessions: 756,
      feature_recipe: 'alpha158', model: 'linear', folds: 1,
      snapshot_hash: 'b'.repeat(64), config_hash: 'c'.repeat(64),
      diagnostic_only: true, counterfactual_refit: false,
      metrics: { ic: null, rank_ic: null, turnover: null, costed_return: null },
    }
    await route.fulfill({ json: {
      items: [
        { ...base, experiment_id: 'a'.repeat(32), status: 'prepared', replay_run_id: null },
        { ...base, experiment_id: 'b'.repeat(32), status: 'trained', replay_run_id: null },
        { ...base, experiment_id: 'c'.repeat(32), status: 'replay_handoff_prepared', replay_run_id: '0123456789abcdef' },
      ], limit: 50, offset: 0, has_more: false,
    } })
  })
  await openDocument(page, 'Machine learning')
  await expect(page.locator('.ml-experiment .ml-validation-label')).toHaveText([
    'INPUT PREPARED — MODEL NOT TRAINED',
    'OOS PREDICTIONS — CANONICAL REPLAY PENDING',
    'CANONICAL REPLAY RECORDED — COUNTERFACTUAL REFIT PENDING',
  ])
})
