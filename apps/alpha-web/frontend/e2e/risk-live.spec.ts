import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { expect, test, type Page } from '@playwright/test'

const root = process.env.C04_RISK_LIVE_ROOT!
let runs: Record<string, { run_id: string; equity_sha256: string }>
test.beforeAll(() => { runs = JSON.parse(readFileSync(`${root}/synthetic-runs.json`, 'utf8')) })

async function openRisk(page: Page, pane: string, runId: string) {
  await page.goto(`/#page=results&pane=${pane}&run=${runId}`)
  if (pane === 'RunDetail') {
    await page.getByRole('tree', { name: 'Report sections' }).getByRole('button', { name: 'Stress test', exact: true }).click()
  }
}

for (const pane of ['RunDetail', 'RiskMonitor']) {
  test(`${pane}: compiled SPA and real backend preserve/display metric basis`, async ({ page }, testInfo) => {
    const assets: string[] = []
    page.on('response', (response) => { if (/\/static\/app\/assets\/.*\.js$/.test(response.url())) assets.push(response.url()) })
    const responseReady = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/risk/scenario' && r.status() === 200)
    await openRisk(page, pane, runs.later_valuations.run_id)
    const response = await responseReady
    expect(new URL(response.url()).searchParams.get('include_metric_basis')).toBe('true')
    const body = await response.json()
    expect(body.provenance.metric_basis.anchor_value).toBe(900)
    expect(body.provenance.metric_basis.initial_capital_status).toBe('unknown')
    expect(body.provenance.source_artifact_sha256).toBe(runs.later_valuations.equity_sha256)
    const note = page.getByRole('note', { name: 'Scenario metric basis' })
    await expect(note).toContainText('900')
    await expect(note).toContainText('Initial-capital baseline: unknown')
    await expect(note).toContainText('External cash-flow coverage: unknown')
    await expect(note).toContainText('compounded simple returns')
    await expect(note).toContainText('No benchmark adjustment')
    await expect(page.getByText('SYNTHETIC_C04_NO_FIT', { exact: true }).first()).toBeVisible()
    const row = page.getByRole('row').filter({ has: page.getByRole('cell', { name: 'base', exact: true }) })
    await expect(row).toContainText(/11\.1\d?%/)
    expect(assets.length).toBeGreaterThan(0)
    for (const url of assets) {
      const relative = new URL(url).pathname.replace('/static/app/', '')
      const actual = await (await page.request.get(url)).body()
      expect(createHash('sha256').update(actual).digest('hex')).toBe(createHash('sha256').update(readFileSync(`${root}/spa/${relative}`)).digest('hex'))
    }
    await testInfo.attach('actual-risk-response', { body: JSON.stringify(body, null, 2), contentType: 'application/json' })
    await page.screenshot({ path: testInfo.outputPath(`${pane}-live.png`), fullPage: true })
  })

  test(`${pane}: controlled legacy request uses genuine backend payload and unknown fallback`, async ({ page }, testInfo) => {
    // Request negotiation only. No response is fulfilled/mocked and production
    // validation is unchanged; this deliberately exercises the real legacy route.
    await page.route(/\/api\/risk\/scenario(?:\?|$)/, (route) => {
      const url = new URL(route.request().url())
      url.searchParams.delete('include_metric_basis')
      return route.continue({ url: url.toString() })
    })
    const responseReady = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/risk/scenario')
    await openRisk(page, pane, runs.first_loss.run_id)
    const response = await responseReady
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body.provenance.metric_basis).toBeUndefined()
    expect(body.scenarios[0].max_drawdown).toBeCloseTo(-0.1, 12)
    const note = page.getByRole('note', { name: 'Scenario metric basis' })
    await expect(note).toContainText('Legacy response: metric basis unavailable')
    await expect(note).toContainText('are unknown')
    await testInfo.attach('real-legacy-response', { body: JSON.stringify(body, null, 2), contentType: 'application/json' })
  })
}

test('malformed stored source is rejected live; no fabricated metadata response', async ({ page }, testInfo) => {
  const responseReady = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/risk/scenario')
  await openRisk(page, 'RiskMonitor', runs.malformed_source.run_id)
  const response = await responseReady
  expect(response.status()).toBe(422)
  const body = await response.json()
  expect(body.code).toBe('request_invalid')
  expect(body.message).toContain('finite equity')
  await expect(page.getByRole('note', { name: 'Scenario metric basis' })).toHaveCount(0)
  await expect(page.getByText(/finite equity/)).toBeVisible()
  const malformedFlag = await page.request.get(`/api/risk/scenario?run_id=${runs.first_loss.run_id}&include_metric_basis=not-a-bool`)
  expect(malformedFlag.status()).toBe(422)
  await testInfo.attach('real-source-rejection', { body: JSON.stringify(body, null, 2), contentType: 'application/json' })
})

test('compiled opted-in risk view rejects disordered stored clocks', async ({ page }, testInfo) => {
  const responseReady = page.waitForResponse((r) => new URL(r.url()).pathname === '/api/risk/scenario')
  await openRisk(page, 'RiskMonitor', runs.disordered_clocks.run_id)
  const response = await responseReady
  expect(new URL(response.url()).searchParams.get('include_metric_basis')).toBe('true')
  expect(response.status()).toBe(422)
  const body = await response.json()
  expect(body.code).toBe('request_invalid')
  expect(body.message).toContain('strictly increasing')
  expect(body.scenarios).toBeUndefined()
  await expect(page.getByRole('note', { name: 'Scenario metric basis' })).toHaveCount(0)
  await expect(page.getByText(/strictly increasing/)).toBeVisible()
  await testInfo.attach('real-clock-rejection', { body: JSON.stringify(body, null, 2), contentType: 'application/json' })
})
