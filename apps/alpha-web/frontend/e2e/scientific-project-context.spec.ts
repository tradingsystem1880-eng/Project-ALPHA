import { expect, test } from '@playwright/test'
import type { components } from '../src/api/generated'
import { preparePage } from './support/workstationHarness'

const project = (id: string, name: string): components['schemas']['ProjectSummary'] => ({
  project_id: id, name, market: 'crypto', hypothesis: 'Test inventory hypothesis', falsification_criterion: 'Test criterion',
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', status: 'active',
  current_experiment_id: null, current_version_id: null, research_gate_state: 'not_required',
})
const bars = [0, 1].map(i => ({ t: 1788220800 + i * 3600, o: 100, h: 110, l: 90, c: 105, v: 1000 }))
const manifest = 'a'.repeat(64)
const dataset: components['schemas']['ArchiveChartDataset'] = {
  schema_version: 1, provider: 'bybit', venue: 'bybit', market_type: 'inverse', family: 'derivative_bars',
  instrument: 'BTCUSD', base_asset: 'BTC', quote_asset: 'USD', frequency: '1h', units: 'quote_price', timestamp_convention: 'interval_start_utc',
  manifest_id: manifest, manifest_ids: [manifest], manifest_count: 1, start: '2026-09-01T00:00:00Z', end: '2026-09-01T01:00:00Z',
  row_count: 2, verification: 'metadata_only',
}

test('project inventory follows pages and no-project browsing retains the viewed native archive', async ({ page }) => {
  await preparePage(page, { candles: { 'XRP/USDT': bars } })
  await page.route(/\/api\/projects\/[^/?]+(?:\?.*)?$/, route => route.fulfill({ json: project('second-project', 'Second project') }))
  const offsets: number[] = []
  await page.route('**/api/projects?*', route => {
    const offset = Number(new URL(route.request().url()).searchParams.get('offset'))
    offsets.push(offset)
    return route.fulfill({ json: { items: [project(offset ? 'second-project' : 'first-project', offset ? 'Second project' : 'First project')], offset, limit: 50, has_more: offset === 0 } })
  })
  await page.route('**/api/research/cases?*', route => route.fulfill({ json: { items: [], offset: 0, limit: 50, has_more: false } }))
  await page.route('**/api/chart-datasets', route => route.fulfill({ json: { datasets: [dataset], authority: 'none', state: 'available' } }))
  const archiveRequests: string[] = []
  await page.route('**/api/candles/BTCUSD?*', route => {
    archiveRequests.push(new URL(route.request().url()).searchParams.get('manifest_id') ?? '')
    return route.fulfill({ json: { symbol: 'BTCUSD', snapshot_id: null, paper_markers: [], bars, provenance: {
      source: 'bybit:derivative_bars', venue: 'bybit', timeframe: '1H', snapshot_id: null, provenance_sha256: manifest,
      receipt_id: null, knowledge_cutoff: null, quality_status: 'qualified', manifest_id: manifest, market_type: 'inverse',
      volume_unit: 'quote', history_kind: 'reconstructed_from_verified_archive',
    } } })
  })
  await page.goto('/#page=data&pane=PriceChart')
  await page.reload()
  const selector = page.getByRole('combobox', { name: 'Project context' })
  await expect(selector.locator('option', { hasText: 'Second project' })).toHaveCount(1)
  expect([...new Set(offsets)]).toEqual([0, 50])
  await selector.selectOption('second-project')
  await expect(selector).toHaveValue('second-project')
  await page.getByRole('button', { name: 'External archive…', exact: true }).click()
  await page.getByRole('button', { name: 'Open BTCUSD', exact: true }).click()
  await expect(page.locator('.price-panel .count')).toHaveText('2 bars')
  await selector.selectOption('')
  await expect(selector).toHaveValue('')
  await expect(page.locator('.terminal-titlebar')).toContainText('[BTCUSD,1h]')
  await expect(page.locator('.price-panel .sym-input')).toHaveValue('BTCUSD')
  await expect(page.locator('.price-panel .sym-input')).toHaveAttribute('readonly', '')
  await expect(page.locator('.price-panel .count')).toHaveText('2 bars')
  expect(archiveRequests).toEqual([manifest])
})

test('partial project inventory failure is explicit and retry restores real choices', async ({ page }) => {
  await preparePage(page)
  let fail = true
  await page.route('**/api/projects?*', route => fail ? route.fulfill({ status: 503, json: { message: 'Project inventory temporarily unavailable' } }) : route.fulfill({ json: { items: [project('recovered', 'Recovered project')], offset: 0, limit: 50, has_more: false } }))
  await page.goto('/#page=data&pane=PriceChart')
  await page.reload()
  const selector = page.getByRole('combobox', { name: 'Project context' })
  await expect(selector.locator('option', { hasText: 'SPY double bottom' })).toHaveCount(1)
  await page.getByRole('button', { name: 'Project inventory failed', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Working context' }).getByRole('alert')).toContainText('Project inventory temporarily unavailable')
  fail = false
  await page.getByRole('button', { name: 'Retry project inventory', exact: true }).click()
  await expect(selector.locator('option', { hasText: 'Recovered project' })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Project inventory failed', exact: true })).toHaveCount(0)
})

test('a selected project missing from current inventory can be cleared without losing the market', async ({ page }) => {
  await preparePage(page, { candles: { 'XRP/USDT': bars } })
  await page.route(/\/api\/projects\/[^/?]+(?:\?.*)?$/, route => route.fulfill({ status: 404, json: { message: 'Selected project no longer available' } }))
  await page.route('**/api/projects?*', route => route.fulfill({ json: { items: [project('retired-selection', 'Previously selected project')], offset: 0, limit: 50, has_more: false } }))
  await page.goto('/#page=data&pane=PriceChart')
  await page.reload()
  const selector = page.getByRole('combobox', { name: 'Project context' })
  await selector.selectOption('retired-selection')
  // Refresh inventories through profile changes while retaining the explicit selected ID.
  await page.route('**/api/projects?*', route => route.fulfill({ json: { items: [], offset: 0, limit: 50, has_more: false } }))
  await page.getByRole('combobox', { name: 'Market profile' }).selectOption('equities')
  await page.getByRole('combobox', { name: 'Market profile' }).selectOption('crypto')
  await expect(selector.locator('option', { hasText: 'Selected: retired-selection' })).toHaveCount(1)
  // Pick a canonical market under the project before explicitly leaving it.
  await page.getByRole('button', { name: 'Symbol, venue and timeframe', exact: true }).click()
  await page.getByRole('combobox', { name: 'Active asset' }).click()
  await page.getByRole('option', { name: /XRP\/USDT/ }).click()
  await expect(page.locator('.price-panel .sym-input')).toHaveValue('XRP/USDT')
  await page.getByRole('button', { name: 'Clear project', exact: true }).click()
  await expect(selector).toHaveValue('')
  await expect(page.locator('.price-panel .sym-input')).toHaveValue('XRP/USDT')
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('alpha.workflow.context') ?? '{}').projectId)).toBeNull()
  const context = await page.evaluate(() => JSON.parse(localStorage.getItem('alpha.workflow.context') ?? '{}'))
  expect(context).toMatchObject({ symbol: 'XRP/USDT', projectId: null, versionId: null, runId: null, snapshotId: null })
})
