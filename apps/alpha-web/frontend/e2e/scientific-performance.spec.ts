import { expect, test } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import { heavyChartBundle, HEAVY_LIBRARY_RUN, openHeavyPrice, preparePage } from './support/workstationHarness'

// Continuous JPEG capture changes the canvas workload; retain DOM/action tracing.
test.use({ trace: { mode: 'retain-on-failure', screenshots: false } })

test('@reference-only @perf-budget four scientific 25k-bar panels preserve resize and cursor performance', async ({ page }) => {
  await preparePage(page, { chartBundle: heavyChartBundle(), runs: [HEAVY_LIBRARY_RUN] })
  await openHeavyPrice(page)
  await page.getByLabel('Plot renderer').selectOption('scientific')
  await page.getByLabel('Line (closes)', { exact: true }).click()
  await expect(page.locator('.price-panel .count')).toHaveText('25000 bars')
  await page.getByLabel('Analytical layout').selectOption('grid')
  await expect(page.locator('.price-panel .count')).toHaveCount(4)
  for (const count of await page.locator('.price-panel .count').all()) await expect(count).toHaveText('25000 bars')
  const hosts = page.locator('.scientific-market-price .scientific-series-host')
  await expect(hosts).toHaveCount(4)
  for (const host of await hosts.all()) await expect(host.locator('.bk-events')).toBeVisible()
  await page.getByText('Panels', { exact: true }).click()
  await page.getByLabel('Link UTC cursors').check()
  await page.getByLabel('Link UTC ranges').check()
  await page.getByText('Panels', { exact: true }).click()

  // Native browser input proves the actual Bokeh hit surface consumes cursor and wheel input.
  const surface = hosts.first().locator('.bk-events')
  const rect = await surface.boundingBox()
  expect(rect).not.toBeNull()
  await page.mouse.move(rect!.x + rect!.width * .55, rect!.y + rect!.height * .55)
  for (const readout of await page.locator('.scientific-market-price .plot-readout').all()) await expect(readout).not.toContainText('Cursor —')
  const beforeWheel = await hosts.first().getAttribute('data-visible-range')
  await page.mouse.wheel(0, -24)
  await expect.poll(() => hosts.first().getAttribute('data-visible-range')).not.toBe(beforeWheel)
  for (const host of await hosts.all()) await expect.poll(() => host.getAttribute('data-visible-range')).toBe(await hosts.first().getAttribute('data-visible-range'))
  // Preflight zoom propagation and native LOD repaint are initialization, not an idle baseline.
  for (const host of await hosts.all()) await expect(host).toHaveAttribute('data-native-lod', 'idle')
  await page.evaluate(async () => { await document.fonts.ready; await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))) })

  const profiler = process.env.ALPHA_SCIENTIFIC_PROFILE ? await page.context().newCDPSession(page) : null
  let cpuProfile: unknown
  if (profiler) {
    await profiler.send('Profiler.enable')
    await page.exposeBinding('__alphaScientificCPUStart', async () => { await profiler.send('Profiler.start') })
    await page.exposeBinding('__alphaScientificCPUStop', async () => { cpuProfile = (await profiler.send('Profiler.stop')).profile })
  }

  const timing = await page.locator('.analytical-workspace').evaluate(async element => {
    const deep = (root: ParentNode): Element[] => [...root.querySelectorAll('*')].flatMap(node => [node, ...(node.shadowRoot ? deep(node.shadowRoot) : [])])
    const hosts = [...element.querySelectorAll<HTMLElement>('.scientific-market-price .scientific-series-host')]
    const surfaces = hosts.map(host => deep(host).find(node => node.classList.contains('bk-events')) as HTMLElement)
    const canvases = hosts.map(host => deep(host).filter((node): node is HTMLCanvasElement => node instanceof HTMLCanvasElement))
    if (hosts.length !== 4 || surfaces.some(surface => !surface) || canvases.some(group => !group.length)) throw new Error('Four populated scientific plot surfaces required')
    const rendered = () => canvases.map(group => group.some(canvas => {
      const ctx = canvas.getContext('2d')
      if (!ctx || !canvas.width || !canvas.height) return false
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      let blue = 0
      for (let n = 0; n < pixels.length; n += 4) if (pixels[n + 2] > pixels[n] + 30 && pixels[n + 1] > pixels[n] + 20 && pixels[n + 3] > 100) blue++
      return blue > 20
    }))
    let plotted = rendered()
    const paintDeadline = performance.now() + 5000
    while (plotted.some(value => !value) && performance.now() < paintDeadline) {
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      plotted = rendered()
    }
    if (plotted.some(value => !value)) throw new Error(`A scientific panel has no rendered blue research series: ${JSON.stringify(plotted)}`)
    const readouts = [...element.querySelectorAll<HTMLElement>('.scientific-market-price .plot-readout')]
    const cursorBefore = readouts.map(node => node.textContent)
    const rangeBefore = hosts.map(host => host.dataset.visibleRange)
    // Input positions remain inside each surface through the 0.5% resize. Cache them
    // so the benchmark does not force an extra layout read from its own harness every frame.
    const inputBounds = surfaces.map(surface => surface.getBoundingClientRect())
    const measure = async (mode: 'idle' | 'all' | 'cursor' | 'wheel' | 'resize') => {
      const started = performance.now()
      const intervals: number[] = []; let previous = performance.now()
      for (let frame = 0; frame <= 60; frame++) await new Promise<void>(resolve => requestAnimationFrame(timestamp => {
        intervals.push(timestamp - previous); previous = timestamp
        if (mode !== 'idle') {
          const surface = surfaces[frame % surfaces.length], rect = inputBounds[frame % surfaces.length]
          const clientX = rect.left + rect.width * (.35 + (frame % 20) / 100), clientY = rect.top + rect.height * .55
          if (mode === 'all' || mode === 'cursor') surface.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, composed: true, pointerType: 'mouse', pointerId: 1, isPrimary: true, clientX, clientY }))
          if (mode === 'all' || mode === 'wheel') surface.dispatchEvent(new WheelEvent('wheel', { bubbles: true, composed: true, cancelable: true, clientX, clientY, deltaY: frame % 2 ? 24 : -24 }))
          // Include the 80ms quiet-period axes redraw before accepted timing ends.
          if (mode === 'all' || mode === 'resize') {
            if (frame < 32) (element as HTMLElement).style.width = frame % 2 ? '100%' : '99.5%'
            else if (frame === 32) (element as HTMLElement).style.width = '99.5%'
          }
        }
        resolve()
      }))
      const measured = intervals.slice(1).sort((a, b) => a - b)
      return { raw: intervals.slice(1), samples: measured.length, median: measured[Math.floor(measured.length / 2)], p99: measured[Math.floor(measured.length * .99)], over: measured.filter(n => n > 20).length / measured.length, started, ended: performance.now() }
    }
    const profile = window as typeof window & { __alphaScientificCPUStart?: () => Promise<void>; __alphaScientificCPUStop?: () => Promise<void> }
    const baseline = await measure('idle')
    const initialWidths = canvases.map(group => group[0].getBoundingClientRect().width)
    await profile.__alphaScientificCPUStart?.()
    const interactive = await measure('all')
    await profile.__alphaScientificCPUStop?.()
    const settledDuringMeasurement = hosts.every((host, i) => Math.abs(Math.max(250, host.clientWidth) - canvases[i][0].getBoundingClientRect().width) <= 2)
    const resizedDuringMeasurement = canvases.every((group, i) => Math.abs(group[0].getBoundingClientRect().width - initialWidths[i]) > 1)
    const diagnostics = { cursor: await measure('cursor'), wheel: await measure('wheel'), resize: await measure('resize') }
    ;(element as HTMLElement).style.width = '100%'
    return { baseline, interactive, diagnostics, settledDuringMeasurement, resizedDuringMeasurement, plotted, sameCanvases: canvases.flat().every(canvas => canvas.isConnected), cursorChanged: readouts.some((node, i) => node.textContent !== cursorBefore[i]), rangeChanged: hosts.some((host, i) => host.dataset.visibleRange !== rangeBefore[i]) }
  })
  if (profiler) {
    const path = test.info().outputPath('scientific-cpu.cpuprofile')
    await writeFile(path, JSON.stringify(cpuProfile))
    await test.info().attach('scientific-cpu.cpuprofile', { path, contentType: 'application/json' })
    await profiler.detach()
  }
  console.log('Scientific four-panel 25k performance', JSON.stringify(timing))
  await test.info().attach('scientific-performance.json', { body: JSON.stringify(timing, null, 2), contentType: 'application/json' })
  expect(timing.baseline.samples).toBe(60)
  expect(timing.interactive.samples).toBe(60)
  expect(timing.sameCanvases).toBe(true)
  expect(timing.settledDuringMeasurement).toBe(true)
  expect(timing.resizedDuringMeasurement).toBe(true)
  expect(timing.cursorChanged).toBe(true)
  expect(timing.rangeChanged).toBe(true)
  const settledRanges = await hosts.evaluateAll(nodes => nodes.map(node => (node as HTMLElement).dataset.visibleRange))
  await page.getByRole('separator', { name: 'vertical panel splitter' }).focus()
  await page.keyboard.press('ArrowLeft')
  await expect(page.getByRole('separator', { name: 'vertical panel splitter' })).toHaveAttribute('aria-valuenow', '45')
  // Coalescing may defer expensive Bokeh axes layout, but it must ultimately honor every host.
  for (const host of await hosts.all()) await expect.poll(async () => {
    const hostWidth = await host.evaluate(node => Math.max(250, (node as HTMLElement).clientWidth))
    const canvasWidth = await host.locator('canvas').first().evaluate(node => node.getBoundingClientRect().width)
    return Math.abs(hostWidth - canvasWidth)
  }).toBeLessThanOrEqual(2)
  expect(await hosts.evaluateAll(nodes => nodes.map(node => (node as HTMLElement).dataset.visibleRange))).toEqual(settledRanges)
  await test.info().attach('scientific-settled.png', { body: await page.screenshot(), contentType: 'image/png' })
  expect(timing.interactive.median).toBeLessThanOrEqual(18)
  expect(timing.interactive.p99).toBeLessThanOrEqual(34)
  expect(timing.interactive.over).toBeLessThanOrEqual(timing.baseline.over + .05)
})
