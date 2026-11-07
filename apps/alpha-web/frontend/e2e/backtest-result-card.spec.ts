import { expect, test, type Page } from '@playwright/test'
import { openDocument, preparePage } from './support/workstationHarness'

const A = 'a'.repeat(16)
const B = 'b'.repeat(16)
const hash = 'c'.repeat(64)

async function prepare(page: Page, enabled = true, manifestPatch = {}) {
  await preparePage(page, { settings: { backtestResultCard: enabled }, runs: [A, B].map(run_id => ({ run_id, kind: 'runs', display_name: `Fixture ${run_id}` })) })
  for (const runId of [A, B]) {
    await page.route(`**/api/runs/${runId}`, route => route.fulfill({ json: {
      run_id: runId, kind: 'runs', display_name: '<img src=x onerror=alert(1)>', mtime: 1,
      manifest: { command: 'backtest_run', symbol: 'FIXTURE', run_id: runId, schema_version: 3,
        run_identity_version: 3, artifact_contract_version: 3,
        artifacts: { 'equity_curve.parquet': { sha256: hash } }, ...manifestPatch },
      has_equity: true, has_trades: false, has_tearsheet: false,
    } }))
    await page.route(`**/api/runs/${runId}/figures`, route => route.fulfill({ json: { run_id: runId, kind: 'runs', items: [] } }))
    await page.route(`**/api/runs/${runId}/equity`, route => route.fulfill({ json: {
      ts: [0, 60], equity: [100, 75], drawdown: [0, -0.25],
    } }))
  }
}
const card = (page: Page) => page.getByRole('region', { name: 'Backtest result card' })

test('backtest card is opt-in and its explicit units and provenance are explicit', async ({ page }) => {
  await prepare(page, false)
  await page.goto(`/#run=${A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
  await expect(card(page)).toHaveCount(0)
  await openDocument(page, 'Governance')
  await page.getByRole('checkbox', { name: 'Backtest result card', exact: true }).check()
  await page.evaluate(id => { window.location.hash = `#run=${id}` }, A)
  await expect(card(page)).toContainText('Historical simulation')
  await expect(card(page).getByRole('row', { name: 'Final drawdown -0.25 fraction of running peak equity', exact: true })).toBeVisible()
  await expect(card(page)).toContainText('UTC Unix seconds')
  await expect(card(page)).toContainText('Curve observations')
  await card(page).getByText('Source', { exact: true }).click()
  await expect(card(page)).toContainText(hash)
  await expect(card(page)).toContainText(A)
  await expect(card(page).locator('img')).toHaveCount(0)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toHaveCount(0)
  // Rollback restores the existing summary immediately.
  await openDocument(page, 'Governance')
  await page.getByRole('checkbox', { name: 'Backtest result card', exact: true }).uncheck()
  await page.evaluate(id => { window.location.hash = `#run=${id}` }, A)
  await expect(card(page)).toHaveCount(0)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
})

test('enabled malformed evidence renders unavailable without the old summary', async ({ page }) => {
  await prepare(page)
  await page.route(`**/api/runs/${A}/equity`, route => route.fulfill({ json: { ts: [0], equity: [0], drawdown: [0] } }))
  await page.goto(`/#run=${A}`)
  await expect(card(page)).toContainText('Summary unavailable')
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toHaveCount(0)
})

test('enabled legacy or unlisted evidence is unavailable', async ({ page }) => {
  await prepare(page, true, { artifacts: {} })
  await page.goto(`/#run=${A}`)
  await expect(card(page)).toContainText('Summary unavailable')
})

test('enabled failed evidence is unavailable', async ({ page }) => {
  await prepare(page)
  await page.route(`**/api/runs/${A}/equity`, route => route.fulfill({ status: 500, json: { detail: 'artifact mismatch' } }))
  await page.goto(`/#run=${A}`)
  await expect(card(page)).toContainText('Summary unavailable')
})

test('a delayed prior-run equity response cannot enter the selected card', async ({ page }) => {
  await prepare(page)
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  let responded!: () => void
  const responseDone = new Promise<void>(resolve => { responded = resolve })
  let started!: () => void
  const request = new Promise<void>(resolve => { started = resolve })
  await page.route(`**/api/runs/${A}/equity`, async route => {
    started(); await wait
    await route.fulfill({ json: { ts: [0, 111], equity: [100, 11], drawdown: [0, -0.89] } })
    responded()
  })
  await page.goto(`/#run=${A}`)
  await request
  await expect(card(page)).toContainText('Loading recorded evidence')
  await page.evaluate(id => { window.location.hash = `#run=${id}` }, B)
  await expect(card(page)).toContainText('-0.25')
  release()
  await responseDone
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
  await expect(card(page)).not.toContainText('-0.89')
  await card(page).getByText('Source', { exact: true }).click()
  await expect(card(page)).toContainText(B)
  await expect(card(page)).not.toContainText(A)
})

for (const command of ['forecast', 'validate']) {
  test(`enabled backtest setting preserves the ${command} summary`, async ({ page }) => {
    await prepare(page, true, { command })
    await page.goto(`/#run=${A}`)
    await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
    await expect(card(page)).toHaveCount(0)
  })
}

test('enabled backtest setting preserves unrelated run loading errors', async ({ page }) => {
  await prepare(page)
  await page.route(`**/api/runs/${A}`, route => route.fulfill({ status: 500, json: { detail: 'load failed' } }))
  await page.goto(`/#run=${A}`)
  await expect(page.getByText('Could not load this run', { exact: true })).toBeVisible()
  await expect(page.getByText('Summary unavailable', { exact: true })).toHaveCount(0)
})

test('fractional UTC time is readable with display precision disclosed and exact seconds retained', async ({ page }) => {
  await prepare(page)
  await page.route(`**/api/runs/${A}/equity`, route => route.fulfill({ json: {
    ts: [0, 60.123456], equity: [100, 75], drawdown: [0, -0.25],
  } }))
  await page.goto(`/#run=${A}`)
  await expect(card(page).getByRole('row', { name: 'Final observation time 1970-01-01 00:01:00 UTC UTC (whole seconds)', exact: true })).toBeVisible()
  await expect(card(page)).toContainText('fractional seconds are omitted')
  await card(page).getByText('Source', { exact: true }).click()
  await expect(card(page).getByText('60.123456', { exact: true })).toBeVisible()
})

test('unsupported UTC time fails safely and preserves the run and known source', async ({ page }) => {
  await prepare(page)
  await page.route(`**/api/runs/${A}/equity`, route => route.fulfill({ json: {
    ts: [253402300800], equity: [100], drawdown: [0],
  } }))
  await page.goto(`/#run=${A}`)
  await expect(card(page)).toContainText('Summary unavailable')
  await expect(card(page)).toContainText(A)
  await expect(card(page)).toContainText(hash)
})

for (const native of [
  { pane: 'NativeQlibDemo', label: 'Native Qlib synthetic result', summary: 'Scores and constructed targets · 16 rows', table: 'Native scores and synthetic targets', rows: 17 },
  { pane: 'NativeNautilusDemo', label: 'Native Nautilus synthetic result', summary: 'All 31 account events · equal timestamps preserved', table: 'Native account balance events', rows: 32 },
]) {
  test(`enabled backtest card coexists with ${native.pane} saved results`, async ({ page }) => {
    await prepare(page)
    await page.goto(`/#run=${A}`)
    await expect(card(page)).toContainText('-0.25')
    await page.evaluate(pane => { window.location.hash = `#page=results&pane=${pane}` }, native.pane)
    const result = page.locator(`[aria-label="${native.label}"]`)
    await expect(result).toBeVisible()
    await expect(result).toContainText('Synthetic')
    await expect(card(page)).toHaveCount(0)
    await expect(page.getByText('Summary unavailable', { exact: true })).toHaveCount(0)
    await result.getByText(native.summary, { exact: true }).click()
    await expect(result.getByRole('table', { name: native.table }).getByRole('row')).toHaveCount(native.rows)
    await page.evaluate(id => { window.location.hash = `#run=${id}` }, A)
    await expect(card(page)).toContainText('-0.25')
    await expect(card(page)).toContainText('1970-01-01 00:01:00 UTC')
  })
}
