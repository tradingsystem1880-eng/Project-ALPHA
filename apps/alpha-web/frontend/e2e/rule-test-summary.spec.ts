import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

test('the rule result opens first and its setup and checks expand independently', async ({ page }) => {
  const runId = 'c'.repeat(16)
  await preparePage(page, { runs: [{ run_id: runId, kind: 'runs', display_name: 'Synthetic rule' }] })
  await page.route(`**/api/runs/${runId}`, route => route.fulfill({ json: {
    run_id: runId, kind: 'runs', display_name: 'Synthetic rule', manifest: {}, has_trades: false,
    rule_test: { idea: null, rule_sentence: 'Hold after a new high', symbol: 'TEST', rule_params: {}, labels: [],
      diagnostics: null, diagnostics_reason: 'No diagnostic file.' },
  } }))
  await page.route(`**/api/runs/${runId}/checks`, route => route.fulfill({ json: { run_id: runId, checks: [] } }))
  await page.route(`**/api/runs/${runId}/figures`, route => route.fulfill({ json: { run_id: runId, items: [] } }))
  await page.route(`**/api/runs/${runId}/series**`, route => route.fulfill({ status: 404, json: { detail: 'no series' } }))
  await page.goto(`/#run=${runId}`)
  const summary = page.getByRole('region', { name: 'Rule test', exact: true })
  await expect(summary.getByRole('heading', { name: /Hold after a new high/ })).toBeVisible()
  for (const period of ['Whole period the rule could trade', 'Scored test periods only']) {
    const row = summary.getByRole('region', { name: period, exact: true })
    await expect(row.getByRole('heading', { name: period })).toBeVisible()
    await expect(row.getByText('Charts: not recorded')).toBeVisible()
  }
  await expect(summary.getByRole('region', { name: 'Checks run on this test' })).toContainText('No checks have been run on this test yet.')
  const setup = summary.locator('details').filter({ has: page.locator('summary', { hasText: 'What was tested' }) })
  const checks = summary.locator('details').filter({ has: page.locator('summary', { hasText: 'Checks on the test itself' }) })
  await expect(setup).toHaveJSProperty('open', false)
  await expect(checks).toHaveJSProperty('open', false)
  await setup.locator('summary').click()
  await expect(setup.getByText('no idea text was saved with this run')).toBeVisible()
  await expect(checks).toHaveJSProperty('open', false)
  await checks.locator('summary').click()
  await expect(checks.getByText('No diagnostic file.')).toBeVisible()
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toHaveCount(0)
})

const DAY = 86400
const T0 = Date.UTC(2021, 0, 4) / 1000
const DAYS = 60

function seriesBody(runId: string, price: { status: string; ts: number[]; close: number[] }) {
  const ts = Array.from({ length: DAYS }, (_, i) => T0 + i * DAY)
  const equity = ts.map((_, i) => 1 + 0.004 * i - (i > 30 && i < 40 ? 0.08 : 0))
  let peak = 0
  const drawdown = equity.map(v => { peak = Math.max(peak, v); return v / peak - 1 })
  return {
    run_id: runId, ts, equity, drawdown, benchmark: ts.map((_, i) => 1 + 0.003 * i), exposure: null,
    trades: [{ entry_ts: ts[5], exit_ts: ts[20], side: 'long', entry_price: 105, exit_price: 120, realized_return: 0.14 }],
    bands: {
      tradable: { first_ts: new Date(ts[3] * 1000).toISOString(), last_ts: new Date(ts[DAYS - 1] * 1000).toISOString() },
      scored: { first_ts: new Date(ts[10] * 1000).toISOString(), last_ts: new Date(ts[DAYS - 1] * 1000).toISOString() },
      folds: [{ index: 0, start_ts: new Date(ts[10] * 1000).toISOString(), end_ts: new Date(ts[30] * 1000).toISOString() }],
    },
    price,
    bounds: { points: { original: DAYS, returned: DAYS, truncated: false, sampling: 'all' }, trades: { original: 1, returned: 1, truncated: false, cap: 2000 } },
    provenance: { artifact_sha256: {} },
  }
}

async function openRuleTest(page: Page, runId: string, body: unknown) {
  await preparePage(page, { runs: [{ run_id: runId, kind: 'runs', display_name: 'Synthetic rule' }] })
  await page.route(`**/api/runs/${runId}`, route => route.fulfill({ json: {
    run_id: runId, kind: 'runs', display_name: 'Synthetic rule', manifest: {}, has_trades: false,
    rule_test: { idea: null, rule_sentence: 'Hold after a new high', symbol: 'TEST', rule_params: {}, labels: [],
      diagnostics: null, diagnostics_reason: 'No diagnostic file.' },
  } }))
  await page.route(`**/api/runs/${runId}/checks`, route => route.fulfill({ json: { run_id: runId, checks: [] } }))
  await page.route(`**/api/runs/${runId}/figures`, route => route.fulfill({ json: { run_id: runId, items: [] } }))
  await page.route(`**/api/runs/${runId}/series**`, route => route.fulfill({ json: body }))
  await page.goto(`/#run=${runId}`)
}

test('the rule-test summary opens with one interactive price, equity and drawdown chart', async ({ page }) => {
  const runId = 'd'.repeat(16)
  const ts = Array.from({ length: DAYS }, (_, i) => T0 + i * DAY)
  await openRuleTest(page, runId, seriesBody(runId, { status: 'available', ts, close: ts.map((_, i) => 100 + i) }))
  const summary = page.getByRole('region', { name: 'Rule test', exact: true })
  const stack = summary.getByTestId('tear-sheet-stack')
  await expect(stack).toBeVisible()
  const chart = stack.getByRole('img')
  await expect(chart).toHaveAttribute('aria-label', /60 days.*1 trade.*walk-forward.*price pane with entry and exit markers/)
  await expect(stack.locator('.bk-Canvas').first()).toBeVisible()
  await expect(stack.getByText('Walk-forward test 1')).toBeVisible()
  await expect(stack.getByTestId('tear-sheet-price-reason')).toHaveCount(0)
  const box = await chart.boundingBox()
  await page.mouse.move(box!.x + box!.width / 2, box!.y + 40)
  await expect(stack.locator('.tear-sheet-readout')).toContainText(/Close .* · Equity .* · Buy and hold .* · Drawdown .* · In market (yes|no)/)
  await stack.getByLabel('Log').check()
  await expect(stack.locator('.bk-Canvas').first()).toBeVisible()
  // the saved images stay, with their new name
  await expect(summary.getByRole('heading', { name: /Hold after a new high/ })).toBeVisible()
})

test('the chart says in plain words why the price pane is missing', async ({ page }) => {
  const runId = 'e'.repeat(16)
  await openRuleTest(page, runId, seriesBody(runId, { status: 'bars_changed_since_run', ts: [], close: [] }))
  const stack = page.getByTestId('tear-sheet-stack')
  await expect(stack.getByTestId('tear-sheet-price-reason')).toContainText('changed since this run')
  await expect(stack.getByRole('img')).toHaveAttribute('aria-label', /price pane not shown/)
  await expect(stack.locator('.bk-Canvas').first()).toBeVisible()
})

test('the chart shows an error when the series cannot be read', async ({ page }) => {
  const runId = 'f'.repeat(16)
  await preparePage(page, { runs: [{ run_id: runId, kind: 'runs', display_name: 'Synthetic rule' }] })
  await page.route(`**/api/runs/${runId}`, route => route.fulfill({ json: {
    run_id: runId, kind: 'runs', display_name: 'Synthetic rule', manifest: {}, has_trades: false,
    rule_test: { idea: null, rule_sentence: 'Hold', symbol: 'TEST', rule_params: {}, labels: [], diagnostics: null, diagnostics_reason: 'x' },
  } }))
  await page.route(`**/api/runs/${runId}/checks`, route => route.fulfill({ json: { run_id: runId, checks: [] } }))
  await page.route(`**/api/runs/${runId}/figures`, route => route.fulfill({ json: { run_id: runId, items: [] } }))
  await page.route(`**/api/runs/${runId}/series**`, route => route.fulfill({ status: 500, json: { detail: 'broken' } }))
  await page.goto(`/#run=${runId}`)
  await expect(page.getByTestId('tear-sheet-stack').getByRole('alert')).toContainText('Could not load the chart series')
})
