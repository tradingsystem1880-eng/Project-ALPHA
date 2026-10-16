import { expect, test } from '@playwright/test'
import { preparePage } from './support/workstationHarness'
import { acceptNextDialog } from './support/dialogCompletion'

test('@reference-only recorded-series native Save includes the displayed value tag', async ({ page }) => {
  await preparePage(page)
  const run = 'd'.repeat(16)
  const rolling = Array.from({ length: 30 }, (_, i) => ({ ts: 1700000000 + i * 86400, window: 20, sharpe: i / 10, volatility: .2 }))
  await page.route('**/api/runs?limit=100', route => route.fulfill({ json: { items: [{ run_id: run, display_name: 'Recorded export fixture' }] } }))
  await page.route(`**/api/runs/${run}`, route => route.fulfill({ json: { run_id: run, display_name: 'Recorded export fixture', kind: 'backtests', manifest: {}, has_equity: false, has_trades: false, has_tearsheet: false } }))
  await page.route(`**/api/runs/${run}/native-tearsheet?*`, route => route.fulfill({ json: { rolling, provenance: { run_id: run } } }))
  await page.goto('/#page=data&pane=PriceChart')
  await page.getByLabel('Replace panel primary').selectOption('sharpe')
  await page.getByRole('button', { name: 'Source', exact: true }).click()
  await page.getByLabel('Panel recorded run').selectOption(run)
  const host = page.locator('[data-panel-id=primary] .scientific-series-host')
  const tag = host.locator('.technical-tag')
  await expect(tag).toBeVisible()
  const value = (await tag.textContent())!
  await page.evaluate(() => {
    Object.assign(window, { recordedExportText: [] as string[] })
    const original = CanvasRenderingContext2D.prototype.fillText
    CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
      ;(window as unknown as { recordedExportText: string[] }).recordedExportText.push(text)
      return original.call(this, text, ...args)
    }
  })
  await host.hover()
  const pending = page.waitForEvent('download')
  const [, , download] = await Promise.all([
    acceptNextDialog(page), host.locator('[title="Save"]').click(), pending,
  ])
  const stream = await download.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk))
  expect(Buffer.concat(chunks).subarray(0, 8)).toEqual(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  expect(await page.evaluate(() => (window as unknown as { recordedExportText: string[] }).recordedExportText)).toContain(value)
})
