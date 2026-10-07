import { expect, test } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

test('Data Manager searches listed Binance pairs and labels history availability honestly', async ({ page }) => {
  await preparePage(page)
  await page.route('**/api/crypto-data/market-catalog?*', route => route.fulfill({ json: {
    state: 'available', venue: 'binance', market_type: 'spot', as_of: '2026-08-14T22:02:24Z', stale: true,
    total_matches: 1, next_action: 'Select a pair, then acquire its exact venue and interval history.',
    markets: [{ pair: 'BTC/USDT', provider_symbol: 'BTCUSDT', base_asset: 'BTC', quote_asset: 'USDT', status: 'TRADING' }],
  } }))
  await page.goto('/#page=data&pane=DataManager')
  const symbol = page.getByRole('combobox', { name: 'Download asset' })
  await symbol.fill('BTC')
  const listed = page.getByRole('button', { name: /BTC\/USDT.*Listed spot pair.*history not checked/ })
  await expect(listed).toBeVisible()
  await expect(page.getByText(/stale catalog.*2026-08-14/)).toBeVisible()
  await listed.click()
  await expect(symbol).toHaveValue('BTC/USDT')
})
