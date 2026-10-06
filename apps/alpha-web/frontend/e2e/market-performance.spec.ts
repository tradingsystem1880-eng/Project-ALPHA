import { expect, test } from '@playwright/test'
import { preparePage } from './support/workstationHarness'
// Continuous JPEG capture changes the canvas workload; retain DOM/action tracing.
test.use({ trace: { mode: 'retain-on-failure', screenshots: false } })
test('@reference-only @perf-budget four 25k-bar panels retain responsive resize and cursor interaction', async ({ page }) => {
  const { heavyChartBundle, HEAVY_LIBRARY_RUN, openHeavyPrice } = await import('./support/workstationHarness')
  await preparePage(page, { chartBundle: heavyChartBundle(), runs: [HEAVY_LIBRARY_RUN] })
  await openHeavyPrice(page)
  await page.getByLabel('Plot renderer').selectOption('market')
  await expect(page.locator('.price-panel .count')).toHaveText('25000 bars')
  await page.getByLabel('Analytical layout').selectOption('grid')
  await expect(page.locator('.price-panel .count')).toHaveCount(4)
  await expect(page.locator('.price-panel .count').last()).toHaveText('25000 bars')
  await page.getByText('Panels', { exact: true }).click()
  await page.getByLabel('Link UTC cursors').check()
  await page.getByLabel('Link UTC ranges').check()
  await page.getByText('Panels', { exact: true }).click()
  const timing = await page.locator('.analytical-workspace').evaluate(async element => {
    const hosts = [...element.querySelectorAll('.price-host')]
    const canvases = [...element.querySelectorAll('canvas')]
    const inputBounds = hosts.map(host => host.getBoundingClientRect())
    const measure = async (interactive: boolean) => {
      const intervals: number[] = []; let previous = performance.now()
      for (let frame = 0; frame <= 60; frame++) {
        await new Promise<void>(resolve => requestAnimationFrame(timestamp => {
          intervals.push(timestamp - previous); previous = timestamp
          if (interactive) {
            const host = hosts[frame % hosts.length] as HTMLElement
            const rect = inputBounds[frame % hosts.length]
            const surface = host.querySelectorAll('canvas')[1] ?? host
            surface.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: rect.left + 50 + frame, clientY: rect.top + 60 }))
            surface.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, clientX: rect.left + 50 + frame, clientY: rect.top + 60, deltaY: frame % 2 ? 24 : -24 }))
            const resized = element as HTMLElement
            // Include the 80ms quiet-period resize/axes redraw in these same60 samples.
            if (frame < 32) resized.style.width = frame % 2 ? '100%' : '99.5%'
            else if (frame === 32) resized.style.width = '99.5%'
          }
          resolve()
        }))
      }
      const measured = intervals.slice(1).sort((a, b) => a - b)
      return { samples: measured.length, median: measured[Math.floor(measured.length / 2)], p99: measured[Math.floor(measured.length * .99)], over: measured.filter(n => n > 20).length / measured.length }
    }
    const baseline = await measure(false)
    const initialWidths = hosts.map(host => host.querySelector('table')!.getBoundingClientRect().width)
    const interactive = await measure(true)
    const settled = hosts.every(host => Math.abs(host.clientWidth - host.querySelector('table')!.getBoundingClientRect().width) <= 2)
    const resized = hosts.every((host, i) => Math.abs(host.querySelector('table')!.getBoundingClientRect().width - initialWidths[i]) > 1)
    return { baseline, interactive, settled, resized, sameCanvases: canvases.every(c => c.isConnected) }
  })
  console.log('Market four-panel 25k performance', JSON.stringify(timing))
  await test.info().attach('market-performance.json', { body: JSON.stringify(timing, null, 2), contentType: 'application/json' })
  await test.info().attach('market-settled.png', { body: await page.screenshot(), contentType: 'image/png' })
  expect(timing.baseline.samples).toBe(60)
  expect(timing.interactive.samples).toBe(60)
  expect(timing.sameCanvases).toBe(true)
  expect(timing.settled).toBe(true)
  expect(timing.resized).toBe(true)
  expect(timing.interactive.median).toBeLessThanOrEqual(18)
  expect(timing.interactive.p99).toBeLessThanOrEqual(34)
  expect(timing.interactive.over).toBeLessThanOrEqual(timing.baseline.over + .05)
  await page.getByRole('separator', { name: 'vertical panel splitter' }).focus()
  await page.keyboard.press('ArrowLeft')
  await expect(page.getByRole('separator', { name: 'vertical panel splitter' })).toHaveAttribute('aria-valuenow', '45')
})

