import { expect, test } from '@playwright/test'
import { preparePage, useCryptoProfile } from './support/workstationHarness'

// Synthetic API responses check presentation only; no market evidence is used.
function asset(name: string, change: number, volumeRatio: number) {
  const series = Array.from({ length: 30 }, (_, index) => 100 + (change * index) / 29)
  return {
    asset: name, last_close: 10 + change, change_1_pct: change / 30, change_7_pct: change / 4, change_window_pct: change,
    last_volume: 1000 * volumeRatio, volume_vs_median: volumeRatio, median_traded_value: 5000, series,
    series_ts: series.map((_, index) => 1_700_000_000 + index * 86_400), last_bar: '2026-11-18T00:00:00+00:00', bar_count: 120,
  }
}
const overview = {
  store: '1D', available_stores: ['1D'], bar_unit: 'day', window: 90, limit: 15, assets_in_store: 6, assets_scanned: 6,
  scan_cap: 200, bars_cap: 400, eligible_assets: 5, data_to: '2026-11-18T00:00:00+00:00',
  assets: [asset('AAA', 1, 1), asset('BBB', 2, 6.5), asset('CCC', 3, 1), asset('DDD', 40, 1), asset('EEE', -9, 1)],
  too_few_bars: [{ asset: 'NEW', bar_count: 12, needed: 90 }], unreadable: [], generated_at: '2026-11-19T10:00:00+00:00',
}

test('Market overview shows small charts, marks the odd one out and sorts the table', async ({ page }) => {
  await preparePage(page)
  await page.route('**/api/market/overview*', route => route.fulfill({ json: overview }))
  await page.goto('/#page=data&pane=MarketOverview')
  await expect(page.getByRole('heading', { name: 'Market', exact: true })).toBeVisible()
  await expect(page.getByText('Market view. Not a test result.', { exact: false })).toBeVisible()
  await expect(page.getByText('Data to: 2026-11-18')).toBeVisible()
  await expect(page.locator('.market-tile')).toHaveCount(5)
  await expect(page.locator('.market-tile[data-differs="true"]')).toHaveAttribute('data-asset', 'DDD')
  await expect(page.getByText('NEW: too few bars (12 of 90 needed)')).toBeVisible()
  await expect(page.getByText('Scale: shared.')).toBeVisible()
  await page.getByRole('combobox', { name: 'Scale' }).selectOption('own')
  await expect(page.getByText('Scale: each its own.')).toBeVisible()
  await page.getByRole('combobox', { name: 'Scale' }).selectOption('shared')
  const tile = await page.locator('.market-tile').first().boundingBox()
  const spark = await page.locator('.market-spark').first().boundingBox()
  expect(tile!.height).toBeGreaterThan(140)
  expect(spark!.height / tile!.height).toBeGreaterThan(0.55)
  await expect(page.locator('.market-axis li')).toHaveCount(4)
  await expect(page.locator('.market-cards li')).toHaveCount(3)
  await expect(page.locator('.market-how')).not.toHaveAttribute('open', '')
  await page.getByText('How this view is built').click()
  await expect(page.getByText('Scanned 6 of 6 assets')).toBeVisible()
  await page.getByRole('button', { name: /^Volume vs usual/ }).click()
  await page.getByRole('button', { name: /^Volume vs usual/ }).click()
  await expect(page.locator('.market-table tbody tr').first()).toHaveAttribute('data-row', 'BBB')
  await page.getByRole('button', { name: 'AAA', exact: true }).first().focus()
  await expect(page.locator('.market-line-hovered')).toHaveCount(1)
  await expect(page.locator('.market-line-dimmed')).toHaveCount(4)
})

test('Market overview says so when the store has no bars, and when the read fails', async ({ page }) => {
  await preparePage(page)
  await page.route('**/api/market/overview*', route => route.fulfill({ json: { ...overview, assets: [], eligible_assets: 0 } }))
  await page.goto('/#page=data&pane=MarketOverview')
  await expect(page.getByText('No stored bars to show', { exact: false })).toBeVisible()
  await page.route('**/api/market/overview*', route => route.fulfill({ status: 409, json: { schema_version: 1, code: 'conflict', message: 'no stored bars in the 1D store', recovery_action: 'Pull data first.', field_errors: [], request_id: 'test' } }))
  await page.reload()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByText('No stored bars to show', { exact: false })).toHaveCount(0)
})

test('Market overview reads the real backend store of synthetic bars', async ({ page }) => {
  await useCryptoProfile(page)
  await page.goto('/#page=data&pane=MarketOverview')
  await expect(page.locator('.market-tile')).toHaveCount(2)
  await expect(page.getByText('Data to: 2021-', { exact: false })).toBeVisible()
  await page.getByRole('combobox', { name: 'Window' }).selectOption('365')
  await expect(page.locator('.market-tile')).toHaveCount(2)
})
