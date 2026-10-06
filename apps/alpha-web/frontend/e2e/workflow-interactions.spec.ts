import { expect, test } from '@playwright/test'
import type { ProviderDefinition } from '../src/api/types'
import { preparePage, openTask } from './support/workstationHarness'

const provider: ProviderDefinition = { asset_classes: ['crypto'], budget_tier: 'public', granted_capabilities: [], last_receipt_id: null, limitations: [], paper_execution: false, recovery_action: '', research_authority: false, timeframes: ['1D'], verified_at: null, id: 'ccxt', label: 'CCXT', installed: true, configured: true, capabilities: ['historical_bars'], credential_env: [], options: {}, network_required: true, verification_state: 'unverified', configuration_state: 'available_without_credentials' }

async function dataPage(page: import('@playwright/test').Page) {
  await openTask(page, 'Data & Assets', 'Data downloads')
}

test('manual download symbols survive clicking directly from the input to Pull', async ({ page }) => {
  const requests: Record<string, unknown>[] = []
  await preparePage(page, { extraGet: { '/api/providers': [provider] }, capturedPost: (path, body) => {
    if (path === '/api/jobs') { requests.push(body); return { job_id: 'download-test', status: 'running' } }
    return undefined
  } })
  await dataPage(page)
  await page.getByRole('combobox', { name: 'Download asset' }).fill('SOL/USDT')
  await page.getByRole('button', { name: '⤓ Pull', exact: true }).click()
  await expect.poll(() => requests.length).toBe(1)
  expect(requests[0].args).toContain('SOL/USDT')
})

test('unavailable bulk storage does not disable ordinary downloads or stored assets', async ({ page }) => {
  await preparePage(page, { extraGet: { '/api/providers': [provider] }, candles: { 'BTC/USDT': [{ t: 1700000000, o: 1, h: 1, l: 1, c: 1, v: 1 }] } })
  await page.route('**/api/crypto-data/storage', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ message: 'Storage offline' }) }))
  await dataPage(page)
  await expect(page.getByRole('combobox', { name: 'Source', exact: true }).locator('option')).not.toHaveCount(0)
  await expect(page.getByRole('button', { name: '⤓ Pull', exact: true })).toBeEnabled()
  await expect(page.getByText('Storage offline', { exact: false })).toBeVisible()
})

test('skip link, profile changes and unavailable local storage preserve a usable shell', async ({ page }) => {
  await preparePage(page)
  await page.locator('.workflow-skip').focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/page=research/)
  await expect(page.locator('#workflow-main')).toBeFocused()
  await page.getByLabel('Market profile').selectOption('equities')
  await expect(page.getByRole('button', { name: 'Symbol, venue and timeframe' })).not.toContainText('XRPUSDT')
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new DOMException('Full', 'QuotaExceededError') } })
  await page.getByLabel('Market profile').selectOption('crypto')
  await expect(page.getByRole('menubar', { name: 'Terminal menu' })).toBeVisible()
  await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
})

test('mounted Builder clears linked and independently selected assets when the market changes', async ({ page }) => {
  const bar = { t: 1700000000, o: 1, h: 1, l: 1, c: 1, v: 1 }
  await preparePage(page, { candles: { 'BTC/USDT': [bar], 'SPY': [bar] } })
  await openTask(page, 'Strategies & Tests', 'Builder')
  const asset = page.getByRole('combobox', { name: 'Test asset' })
  await expect(asset).toHaveValue('XRP/USDT')
  await page.getByLabel('Market profile').selectOption('equities')
  await expect(asset).toHaveValue('')
  await asset.click()
  await page.getByRole('listbox', { name: 'Stored assets' }).getByRole('option', { name: /SPY/ }).click()
  await expect(asset).toHaveValue('SPY')
  await page.getByLabel('Market profile').selectOption('crypto')
  await expect(asset).toHaveValue('')
  await asset.click()
  await page.getByRole('listbox', { name: 'Stored assets' }).getByRole('option', { name: /BTC\/USDT/ }).click()
  await page.getByLabel('Market profile').selectOption('equities')
  await expect(asset).toHaveValue('')
  await expect(page.getByRole('button', { name: 'Test in sandbox' })).toBeDisabled()
})
