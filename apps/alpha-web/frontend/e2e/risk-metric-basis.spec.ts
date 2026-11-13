import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

import type { RiskReport } from '../src/api/types'

const fixture = JSON.parse(readFileSync(new URL('./fixtures/riskMetricBasis.json', import.meta.url), 'utf8')) as {
  later: { legacy: RiskReport; disclosed: RiskReport }
  loss: { legacy: RiskReport; disclosed: RiskReport }
}
const first = fixture.later.disclosed
const second = fixture.loss.legacy

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (error) => console.error('Risk harness page error:', error.message))
  page.on('console', (message) => { if (message.type() === 'error') console.error('Risk harness console:', message.text()) })
  page.on('response', (response) => { if (response.status() >= 400) console.error('Risk harness HTTP:', response.status(), response.url()) })
})

for (const view of ['detail', 'monitor']) {
  test(`${view}: actual consumer requests and visibly renders the serialized basis`, async ({ page }, testInfo) => {
    const requests: string[] = []
    let releaseSecond!: () => void
    const secondReady = new Promise<void>((resolve) => { releaseSecond = resolve })
    await page.route('**/api/**', async (route) => {
      const url = new URL(route.request().url())
      if (!url.pathname.startsWith('/api/')) return route.continue()
      if (url.pathname === '/api/risk/scenario') {
        requests.push(url.search)
        const next = url.searchParams.get('run_id') === second.run_id
        if (next) await secondReady
        return route.fulfill({ json: next ? second : first })
      }
      if (url.pathname.startsWith('/api/runs/')) {
        return route.fulfill({ json: {
          run_id: url.pathname.split('/').at(-1), kind: 'runs', has_equity: true,
          manifest: { command: 'c04_web_fixture' },
        } })
      }
      return route.fulfill({ json: {} })
    })
    await page.goto(`/e2e/risk-metric-basis.html?view=${view}&run=${first.run_id}`)
    const note = page.getByRole('note', { name: 'Scenario metric basis' })
    await expect(note).toContainText('900')
    await expect(note).toContainText('compounded simple returns')
    await expect(note).toContainText('Initial-capital baseline: unknown')
    await expect(note).toContainText('External cash-flow coverage: unknown')
    await expect(note).toContainText('No benchmark adjustment')
    expect(requests.length).toBeGreaterThan(0)
    expect(requests.every((url) => new URLSearchParams(url).get('include_metric_basis') === 'true')).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`${view}-basis.png`), fullPage: true })
    await page.evaluate((id) => {
      (window as unknown as { c04SetRun(id: string): void }).c04SetRun(id)
    }, second.run_id)
    await expect(note).toHaveCount(0) // no old-run anchor while the next request is pending
    releaseSecond()
    await expect(note).toContainText('Legacy response: metric basis unavailable')
    await expect(note).toContainText('are unknown')
    await expect(note).not.toContainText('900')
  })

  test(`${view}: malformed cached metadata never renders as verified conventions`, async ({ page }) => {
    const malformed = structuredClone(first)
    malformed.provenance.metric_basis!.schema_version = 2
    await page.route('**/api/**', (route) => {
      const url = new URL(route.request().url())
      if (!url.pathname.startsWith('/api/')) return route.continue()
      return route.fulfill({ json: url.pathname === '/api/risk/scenario' ? malformed : {
        run_id: first.run_id, kind: 'runs', has_equity: true, manifest: { command: 'c04_web_fixture' },
      } })
    })
    await page.goto(`/e2e/risk-metric-basis.html?view=${view}&run=${first.run_id}`)
    const note = page.getByRole('note', { name: 'Scenario metric basis' })
    await expect(note).toContainText('Unsupported or invalid metric basis')
    await expect(note).toContainText('are unknown')
    await expect(note).not.toContainText('900')
  })
}
