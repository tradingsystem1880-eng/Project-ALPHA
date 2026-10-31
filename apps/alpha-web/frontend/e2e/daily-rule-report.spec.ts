import { expect, test, type Page, type Route } from '@playwright/test'
import type { DailyRuleEvidence, DailyRuleRole } from '../src/api/dailyRule'
import { preparePage } from './support/workstationHarness'

// Artificial API fixtures exercise presentation and request ownership, never market acceptance.
const STUDY = 'a'.repeat(16)
const BASELINE = 'b'.repeat(16)
const CONTROL = 'c'.repeat(16)
const times = [946684800, 946771200, 946857600]
const runSummary = { starting_equity: 1000, final_equity: 990, orders: 2, fills: 2,
  rejected: 0, n_trades: 0, gross_pnl: -8, net_pnl: -10, fees_total: 2 }

function evidence(role: DailyRuleRole, offset: number): DailyRuleEvidence {
  return { schema: 'DailyRuleEvidenceV1', run_id: STUDY, available: true,
    outcome: 'exploratory_complete',
    watermark: 'Artificial daily study fixture only', claim_scope: 'exploratory', data_origin: 'artificial',
    roles: { baseline: { ...runSummary, run_id: BASELINE }, control: { ...runSummary, run_id: CONTROL } },
    provenance: { query_sha256: 'fixture-query', canonical_chart_snapshot_id: 'fixture-snapshot',
      quantity_unit: 'BTC', currency: 'USDT', historical_point_in_time: false },
    accounting: { role, total: 101, rows: [{ ts: '2000-01-01T00:00:00Z',
      event: `${role}-page-${offset}`, cash: role === 'baseline' ? 990 : 1000,
      cash_free: 990, position_units: 0, currency: 'USDT', commission: 2,
      fees_total: 2, fill_sequence_id: 1 }], has_more: offset === 0, next_offset: offset === 0 ? 100 : null },
    selectors: { baseline: BASELINE, control: CONTROL }, artifact_sha256: { 'economics.json': 'd'.repeat(64) } }
}

async function setup(page: Page, reply?: (route: Route) => Promise<void>) {
  await preparePage(page, { runs: [{ run_id: STUDY, kind: 'runs', display_name: 'Artificial daily report' }] })
  for (const runId of [STUDY, BASELINE, CONTROL]) {
    await page.route(`**/api/runs/${runId}`, route => route.fulfill({ json: {
      run_id: runId, kind: 'runs', display_name: 'Artificial daily report',
      manifest: { command: runId === STUDY ? 'research_daily_rule_native_v1' : 'research_daily_rule_projection_v1' },
      has_equity: true, has_trades: true, has_tearsheet: false,
      run_context_watermark: 'Artificial fixture only', research_gate_watermark: null,
    } }))
    await page.route(`**/api/runs/${runId}/figures`, route => route.fulfill({ json: {
      run_id: runId, kind: 'runs', renderer_version: 1, items: [],
    } }))
    await page.route(`**/api/runs/${runId}/trades`, route => route.fulfill({ json: [] }))
    await page.route(`**/api/runs/${runId}/equity`, route => route.fulfill({ json: {
      ts: times, equity: [1000, 995, 990], drawdown: [0, -0.005, -0.01],
    } }))
    await page.route(`**/api/runs/${runId}/native-tearsheet?*`, route => route.fulfill({ json: {
      available: true, benchmark: times.map(ts => ({ ts, available: true, benchmark_equity: 1000 })),
      exposure_turnover: times.map(end_ts => ({ end_ts, exposure_available: true, gross_exposure: 0.1 })),
      rolling: [], bounds: {}, provenance: { run_id: runId },
    } }))
    await page.route(`**/api/runs/${runId}/chart-bundle?*`, route => route.fulfill({ json: {
      run_id: runId, bars_status: 'available', trace_status: 'available',
      bars: times.map((t, i) => ({ t, o: 10 + i, h: 12 + i, l: 9 + i, c: 11 + i, v: 100 })),
      provenance: { symbol: 'ARTIFICIAL', snapshot_id: 'fixture-snapshot', timezone: 'UTC', price_unit: 'native_quote',
        command: 'research_daily_rule_projection_v1', artifact_sha256: {} },
      trace: [], decisions: [], orders: [], fills: [], trades: [], indicators: [], annotations: [], folds: [],
      equity: { ts: times, equity: [1000, 995, 990], drawdown: [0, -0.005, -0.01] }, forecast: null,
      truncated: {},
    } }))
  }
  await page.route(`**/api/runs/${STUDY}/daily-rule-evidence?*`, reply ?? (route => {
    const params = new URL(route.request().url()).searchParams
    return route.fulfill({ json: evidence(params.get('role') as DailyRuleRole, Number(params.get('offset'))) })
  }))
}

async function openDaily(page: Page) {
  await page.goto(`/#run=${STUDY}`)
  await page.getByRole('tree', { name: 'Report sections' }).getByRole('button', { name: 'Daily rule and control', exact: true }).click()
}

test('daily rule report shows artificial comparison, linked charts and paged evidence', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await setup(page)
  await openDaily(page)
  await expect(page.getByRole('region', { name: 'Daily rule comparison' })).toContainText('Artificial daily study fixture only')
  await expect(page.getByRole('table', { name: /Recorded baseline and control/ })).toContainText('-10')
  await expect(page.locator('.daily-rule-report .scientific-series-host')).toHaveCount(4)
  await expect(page.locator('.daily-rule-report .price-panel')).toContainText('3 bars')
  await page.getByText('Query, snapshot, clocks and units', { exact: true }).click()
  await expect(page.getByRole('region', { name: 'Daily study evidence inspector' })).toContainText('fixture-query')
  await page.getByRole('button', { name: 'Next accounting page' }).click()
  await expect(page.getByRole('table', { name: 'baseline accounting · offset 100' })).toContainText('baseline-page-100')
  await expect(page.getByRole('button', { name: 'Next accounting page' })).toBeDisabled()
  await page.getByLabel('Daily study role').selectOption('control')
  await expect(page.getByRole('table', { name: 'control accounting · offset 0' })).toContainText('control-page-0')
  await expect(page.getByRole('table', { name: 'baseline accounting · offset 100' })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('daily report hides prior role while loading and rejects a mismatched returned identity', async ({ page }) => {
  let finish!: () => void
  const waiting = new Promise<void>(resolve => { finish = resolve })
  await setup(page, async route => {
    const role = new URL(route.request().url()).searchParams.get('role') as DailyRuleRole
    if (role === 'control') await waiting
    return route.fulfill({ json: role === 'control' ? { ...evidence(role, 0), run_id: 'f'.repeat(16) } : evidence(role, 0) })
  })
  await openDaily(page)
  await expect(page.getByRole('table', { name: 'baseline accounting · offset 0' })).toBeVisible()
  await page.getByLabel('Daily study role').selectOption('control')
  await expect(page.getByText('Loading daily study evidence…', { exact: true })).toBeVisible()
  await expect(page.getByText('baseline-page-0', { exact: true })).toHaveCount(0)
  finish()
  await expect(page.getByRole('alert')).toContainText('belongs to another run or schema')
})

test('rejected zero-fill control remains inconclusive in the daily report', async ({ page }) => {
  await setup(page, route => {
    const recorded = evidence('baseline', 0)
    return route.fulfill({ json: { ...recorded, outcome: 'accounting_rejection_inconclusive',
      roles: { ...recorded.roles, control: { ...recorded.roles.control,
        orders: 1, rejected: 1, fills: 0, n_trades: 0, starting_equity: 1000, final_equity: 1000,
        gross_pnl: 0, net_pnl: 0, fees_total: 0 } } } })
  })
  await openDaily(page)
  await expect(page.getByRole('status', { name: 'Daily study outcome' })).toContainText('Inconclusive: accounting rejection')
  await expect(page.getByRole('region', { name: 'Daily rule comparison' })).toContainText('control: 1 rejected order(s), 0 fills.')
  await page.getByRole('link', { name: 'Inspect rejected-order counts' }).click()
  await expect(page).toHaveURL(new RegExp(`#run=${STUDY}$`))
  await expect(page.locator('#daily-rejected-counts')).toContainText('1')
  await expect(page.getByText('Exploratory recorded results.', { exact: false })).toHaveCount(0)
})
