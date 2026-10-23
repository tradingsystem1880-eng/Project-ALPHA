import { expect, test, type Browser, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import type { Candles } from '../src/api/types'
import { preparePage } from './support/workstationHarness'
import { studySeries, walkBars } from './support/technicalFixture'
import { waitForTechnicalChartWidth } from './support/technicalLayout'

// The StockCharts-grade technical chart (docs/superpowers/plans/2026-10-07-technical-chart-language.md):
// one panel stack with RSI above price + volume and MACD below, all studies served by the
// `alpha chart overlays` stand-in, on an observation-spaced axis.
const BARS = walkBars(260, '2025-10-06', false)
const SHOTS = process.env.ALPHA_TECHNICAL_SHOTS

type PrintfCall = { format: string; labels: string[] }

async function observePrintf(page: Page) {
  await page.addInitScript(() => {
    const calls: PrintfCall[] = [], wrapped = new WeakSet<object>()
    Object.assign(window, { printfCalls: calls, printfOverflow: false })
    // Observe the real models as Bokeh adds its document graph; no application test hook.
    const set = Map.prototype.set
    Map.prototype.set = function(key, value) {
      const result = set.call(this, key, value)
      if (value && typeof value === 'object' && value.type === 'PrintfTickFormatter' && typeof value.doFormat === 'function' && !wrapped.has(value)) {
        wrapped.add(value)
        const format = value.doFormat
        value.doFormat = function(...args: unknown[]) {
          const labels = format.apply(this, args)
          // Relayout repeats calls; retain distinct results without silently truncating them.
          if (!calls.some(call => call.format === this.format && call.labels.length === labels.length && call.labels.every((label, index) => label === labels[index]))) {
            if (calls.length < 100) calls.push({ format: this.format, labels: [...labels] })
            else (window as unknown as { printfOverflow: boolean }).printfOverflow = true
          }
          return labels
        }
      }
      return result
    }
  })
}

async function expectBoundedPrintf(page: Page, notation: 'f' | 'e') {
  const observed = () => page.evaluate(() => (window as unknown as { printfCalls: PrintfCall[] }).printfCalls)
  await expect.poll(async () => (await observed()).some(call => call.format.endsWith(notation) && call.labels.length > 1)).toBe(true)
  for (const { format, labels } of await observed()) {
    expect(format).toMatch(/^%(?:d|\.(?:[0-9]|1[0-2])f|\.(?:[2-9]|1[0-6])e)$/)
    expect(new Set(labels).size).toBe(labels.length)
    expect(labels.every(label => label.length <= 40)).toBe(true)
  }
  expect(await page.evaluate(() => (window as unknown as { printfOverflow: boolean }).printfOverflow)).toBe(false)
}

test('@reference-only ordinary chart uses bounded real Bokeh printf formats', async ({ page }) => {
  await observePrintf(page)
  await openChart(page, 'classic')
  await expectBoundedPrintf(page, 'f')
})

test('@reference-only hostile API marker values stay literal in real Bokeh hover', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message))
  const side = '%.101f %.101e %.101g @y{%.101f} <img data-printf-payload src=x>'
  const bars = BARS.slice(0, 120).map(bar => ({ ...bar, o: 100, h: 101, l: 99, c: 100 }))
  await preparePage(page, { candles: { 'XRP/USDT': bars }, settings: { chartTemplate: 1, overlays: { crypto: { indicators: [], patterns: [] } } } })
  const response: Candles = {
    symbol: 'XRP/USDT', snapshot_id: null, bars,
    provenance: { source: 'synthetic:printf-regression', venue: null, timeframe: '1D', snapshot_id: null,
      provenance_sha256: null, receipt_id: null, knowledge_cutoff: null, quality_status: 'legacy_unqualified' },
    paper_markers: bars.map((bar, sequence) => ({ session_id: 'synthetic-printf', sequence, t: bar.t, exact_ts: bar.t,
      event_type: 'fill', execution_mode: 'local_sandbox', side, quantity: 1, price: bar.c, intent_id: null })),
  }
  await page.route('**/api/candles/**', route => route.fulfill({ json: response }))
  await page.goto('/#page=data&pane=PriceChart')
  const host = page.locator('[data-panel-id=primary] .technical-host')
  await expect(host.locator('canvas').first()).toBeVisible()
  const tag = host.locator('.technical-tag').filter({ hasText: /^100\.00$/ }).first()
  await expect(tag).toBeVisible()
  const box = (await host.boundingBox())!, tagBox = (await tag.boundingBox())!
  const y = tagBox.y + 6
  await page.mouse.move(box.x + box.width / 2, y)
  const cursor = host.locator('.technical-cursor').first()
  await expect(cursor).toBeVisible()
  await page.mouse.move((await cursor.boundingBox())!.x, y)
  await expect(page.locator('.bk-Tooltip').getByText(`P FILL ${side}`, { exact: true })).toBeVisible()
  await expect(page.locator('[data-printf-payload]')).toHaveCount(0)
  expect(errors).toEqual([])
})

for (const scale of [1e-200, 1e200]) {
  test(`@reference-only extreme finite ${scale < 1 ? 'tiny' : 'large'} chart has distinct readable scientific labels`, async ({ page }) => {
    await observePrintf(page)
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.addInitScript(() => {
      const labels: string[] = []
      Object.assign(window, { numericLabels: labels })
      const fill = CanvasRenderingContext2D.prototype.fillText
      CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
        if (/^-?[\d.]+e[+-]\d+$/.test(text)) labels.push(text)
        return fill.call(this, text, ...args)
      }
    })
    const bars = BARS.map(b => ({ ...b, o: b.o * scale, h: b.h * scale, l: b.l * scale, c: b.c * scale }))
    const chart = await openChart(page, 'classic', bars)
    await expect.poll(() => chart.locator('.technical-tag').allTextContents()).toContain(bars.at(-1)!.c.toExponential())
    await expect.poll(() => page.evaluate(() => new Set((window as unknown as { numericLabels: string[] }).numericLabels).size)).toBeGreaterThan(2)
    const host = (await chart.locator('.technical-host').boundingBox())!
    const tag = chart.locator('.technical-tag').filter({ hasText: bars.at(-1)!.c.toExponential() }).first()
    const box = (await tag.boundingBox())!
    expect(box.x + box.width).toBeLessThanOrEqual(host.x + host.width + 1)
    expect(await chart.locator('.technical-header').textContent()).toContain(`Close ${bars.at(-1)!.c.toExponential()}`)
    await expectBoundedPrintf(page, 'e')
    expect(errors).toEqual([])
    await chart.screenshot({ path: test.info().outputPath('extreme-finite-chart.png') })
  })
}

test('@reference-only scientific value tags stay inside a narrow chart host', async ({ page }) => {
  const scale = Number.parseFloat('1e-200')
  const bars = BARS.map(b => ({ ...b, o: b.o * scale, h: b.h * scale, l: b.l * scale, c: b.c * scale }))
  const chart = await openChart(page, 'classic', bars)
  const host = chart.locator('.technical-host')
  const initialHost = (await host.boundingBox())!
  await expect.poll(async () => Math.max(...await chart.locator('canvas').evaluateAll(items => items.map(item => item.getBoundingClientRect().width)))).toBeGreaterThanOrEqual(initialHost.width * 0.98)
  await expect.poll(async () => Math.max(...await chart.locator('canvas').evaluateAll(items => items.map(item => item.getBoundingClientRect().width)))).toBeLessThanOrEqual(initialHost.width + 2)
  await chart.evaluate(element => { element.style.width = '340px'; element.style.maxWidth = '340px' })
  await expect.poll(async () => (await host.boundingBox())?.width).toBeLessThanOrEqual(341)
  await expect.poll(async () => Math.max(...await chart.locator('canvas').evaluateAll(items => items.map(item => item.getBoundingClientRect().width)))).toBeLessThanOrEqual(342)
  const hostBox = (await host.boundingBox())!
  const tag = chart.locator('.technical-tag').filter({ hasText: bars.at(-1)!.c.toExponential() }).first()
  await expect(tag).toBeVisible()
  const tagBox = (await tag.boundingBox())!
  expect(tagBox.x).toBeGreaterThanOrEqual(hostBox.x - 1)
  expect(tagBox.x + tagBox.width).toBeLessThanOrEqual(hostBox.x + hostBox.width + 1)
})

test('@reference-only MACD cancellation noise does not widen the shared chart gutter', async ({ page }) => {
  const bars = Array.from({ length: 60 }, (_, index) => ({
    t: 1_700_000_000 + index * 86400,
    o: 100 + index,
    h: 102 + index,
    l: 99 + index,
    c: 101 + index,
    v: 1000,
  }))
  const chart = await openChart(page, 'classic', bars)
  const geometry = await chart.locator('.technical-host').evaluate(host => {
    const column = host.querySelector('.bk-Column') as HTMLElement | null
    return [...(column?.shadowRoot?.querySelectorAll('[class*="bk-"]') ?? [])]
      .map(element => getComputedStyle(element).gridTemplateColumns.split(/\s+/).map(parseFloat))
      .filter(columns => columns.length === 3)
      .map(columns => columns[2])
  })
  expect(geometry.length).toBeGreaterThan(0)
  expect(Math.max(...geometry)).toBeLessThanOrEqual(80)
  const legend = (await chart.locator('.technical-legend').allTextContents()).join(' ')
  expect(legend).toContain('-0.000')
  expect(legend).not.toMatch(/e[+-]\d+/)
})

test('@reference-only PNG download includes header, calendar dates and study legends', async ({ page }) => {
  const chart = await openChart(page, 'classic')
  const height = (await chart.locator('.technical-host').boundingBox())!.height
  // Maximizing schedules the native Bokeh layout after the host has resized.
  await expect.poll(() => chart.locator('.technical-host canvas').evaluateAll(canvases =>
    Math.max(...canvases.map(canvas => canvas.getBoundingClientRect().bottom)) -
    Math.min(...canvases.map(canvas => canvas.getBoundingClientRect().top)),
  )).toBeGreaterThan(height - 20)
  await page.mouse.move(0, 0)
  const hostBox = (await chart.locator('.technical-host').boundingBox())!
  const swatch = await chart.getByText('Volume', { exact: true }).locator('..').locator('div').first().evaluate(element => {
    const rect = element.getBoundingClientRect()
    const color = getComputedStyle(element).backgroundImage.match(/rgba?\([^)]+\)/)?.[0]
      ?? getComputedStyle(element.firstElementChild!).backgroundColor
    return { x: rect.left, y: rect.top, color }
  })
  await page.evaluate(() => {
    const painted: string[] = []
    Object.assign(window, { exportText: painted })
    const original = CanvasRenderingContext2D.prototype.fillText
    CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
      painted.push(text)
      return original.call(this, text, ...args)
    }
  })
  const downloaded = page.waitForEvent('download')
  await chart.getByRole('button', { name: 'Save PNG' }).click()
  const download = await downloaded
  await download.saveAs(test.info().outputPath('technical-export.png'))
  expect(download.suggestedFilename()).toMatch(/\.png$/)
  const bytes = await readFile((await download.path())!)
  const result = await page.evaluate(async ({ data, hostBox, swatch }) => {
    const image = await createImageBitmap(await (await fetch(`data:image/png;base64,${data}`)).blob())
    const canvas = document.createElement('canvas')
    canvas.width = image.width; canvas.height = image.height
    const context = canvas.getContext('2d')!
    context.drawImage(image, 0, 0)
    const pixels = context.getImageData(0, 0, image.width, 30).data
    const ink = pixels.filter((value, index) => index % 4 !== 3 && value < 180).length
    const scale = image.width / hostBox.width
    const headerHeight = image.height - hostBox.height * scale
    const bars = [1, 4, 6].map(dx => [...context.getImageData(
      Math.floor((swatch.x - hostBox.x + dx) * scale),
      Math.floor(headerHeight + (swatch.y - hostBox.y + 3) * scale), 1, 1,
    ).data])
    context.fillStyle = swatch.color; context.fillRect(0, 0, 1, 1)
    const expected = [...context.getImageData(0, 0, 1, 1).data]
    return { height: image.height, ink, bars, expected, text: (window as unknown as { exportText: string[] }).exportText }
  }, { data: bytes.toString('base64'), hostBox, swatch })
  expect(result.height).toBeGreaterThan(height)
  expect(result.ink).toBeGreaterThan(30)
  for (const bar of result.bars) expect(bar).toEqual(result.expected)
  expect(result.text.join(' ')).toContain('Open')
  for (const label of ['MA(50)', 'MA(200)', 'RSI(14)', 'MACD(12,26,9)']) expect(result.text).toContain(label)
  expect(result.text.some(text => /^202[56]$/.test(text))).toBe(true)
})

async function openChart(page: Page, style: 'classic' | 'default', bars = BARS, outsideAnnotation = false) {
  await preparePage(page, { candles: { 'XRP/USDT': bars }, settings: { chartStyle: style } })
  if (outsideAnnotation) await page.route('**/api/overlays/**', async route => {
    const indicators = ['sma:50', 'sma:200', 'rsi:14', 'macd:12:26:9'].flatMap(id => {
      const result = studySeries(id, bars)
      return 'series' in result ? result.series : []
    })
    await route.fulfill({ json: { symbol: 'XRP/USDT', t: bars.map(bar => bar.t), indicators,
      annotations: [{ annotation_id: 1, decision_sequence_id: null, kind: 'marker', label: 'Outside', unit: 'price', reason: 'outside fixture', anchors: [{ anchor_index: 0, ts: bars[0].t - 86400, value: bars[0].l }] }],
    } })
  })
  await page.goto('/#page=data&pane=PriceChart')
  const chart = page.locator('[data-panel-id=primary] .technical-chart')
  await expect(chart.locator('.technical-host canvas').first()).toBeVisible()
  await page.getByRole('button', { name: 'Maximize panel primary' }).click()
  await expect(chart.getByText('MACD(12,26,9)', { exact: false })).toBeVisible()
  return chart
}

async function touchContext(browser: Browser) {
  const port = process.env.ALPHA_PLAYWRIGHT_PORT ?? '8802'
  return browser.newContext({
    baseURL: `http://localhost:${port}/`,
    viewport: { width: 1280, height: 720 },
    colorScheme: 'dark',
    hasTouch: true,
    isMobile: true,
    reducedMotion: 'reduce',
  })
}

test('@reference-only PNG retains disclosure of annotations outside loaded observations', async ({ page }) => {
  const chart = await openChart(page, 'classic', BARS, true)
  const disclosure = '1 annotation outside the loaded bars not drawn'
  await expect(chart.locator('.technical-skipped')).toHaveText(disclosure)
  await page.evaluate(() => {
    Object.assign(window, { exportText: [] as string[] })
    const original = CanvasRenderingContext2D.prototype.fillText
    CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
      ;(window as unknown as { exportText: string[] }).exportText.push(text)
      return original.call(this, text, ...args)
    }
  })
  const downloaded = page.waitForEvent('download')
  await chart.getByRole('button', { name: 'Save PNG' }).click()
  const download = await downloaded
  expect((await readFile((await download.path())!)).length).toBeGreaterThan(1000)
  expect(await page.evaluate(() => (window as unknown as { exportText: string[] }).exportText.join(' '))).toContain(disclosure)
})

for (const style of ['classic', 'default'] as const) {
  test(`@reference-only technical chart renders the StockCharts ${style} grammar`, async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 1127 })
    const chart = await openChart(page, style)
    await expect(chart).toHaveAttribute('data-chart-style', style)
    for (const label of ['RSI(14)', 'MA(50)', 'MA(200)', 'MACD(12,26,9)', 'Volume']) await expect(chart.getByText(label, { exact: false }).first()).toBeVisible()
    await expect(chart.locator('.technical-date.year, .technical-date.month').first()).toBeVisible()
    await expect(chart.locator('.technical-header')).toContainText(`Close ${BARS.at(-1)!.c.toFixed(2)}`)
    await expect(chart.locator('.technical-gap')).toHaveCount(0)
    await page.mouse.move(0, 0)
    await expect(chart).toHaveScreenshot(`technical-${style}.png`, { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.02 })
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/technical-${style}.png` })
  })
}

test('@reference-only hovering updates the header and legends; x zoom rescales price', async ({ page }) => {
  const chart = await openChart(page, 'classic')
  const host = chart.locator('.technical-host')
  await waitForTechnicalChartWidth(host)
  const box = (await host.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5)
  const header = chart.locator('.technical-ohlc')
  await expect(header).not.toContainText(`Close ${BARS.at(-1)!.c.toFixed(2)}`)
  const hovered = await header.innerText()
  expect(hovered).toMatch(/^\d{4}-\d\d-\d\d {2}Open /)
  const before = JSON.parse((await host.getAttribute('data-visible-range'))!)
  await page.mouse.wheel(0, -600)
  await expect.poll(async () => JSON.parse((await host.getAttribute('data-visible-range'))!).from).toBeGreaterThan(before.from)
  await chart.getByRole('button', { name: 'All data', exact: true }).click()
  await expect.poll(async () => JSON.parse((await host.getAttribute('data-visible-range'))!).from).toBe(BARS[0].t)
})

test('@reference-only keyboard inspection selects exact bars and preserves null studies and provenance', async ({ page }) => {
  const chart = await openChart(page, 'classic')
  await chart.getByRole('button', { name: 'All data', exact: true }).click()
  const host = chart.locator('.technical-host')
  await expect(host).toHaveAttribute('tabindex', '0')
  await host.focus()
  await page.keyboard.press('End')

  const header = chart.locator('.technical-ohlc')
  const last = BARS.at(-1)!
  const study = studySeries('sma:50', BARS)
  if (!('series' in study)) throw new Error('fixture SMA unexpectedly refused its window')
  await expect(header).toContainText(new Date(last.t * 1_000).toISOString().slice(0, 10))
  await expect(header).toContainText(`Close ${last.c.toFixed(2)}`)
  await expect(header).toContainText(`Volume ${last.v.toLocaleString('en-US')}`)
  await expect(chart.locator('.technical-legend').filter({ hasText: 'MA(50)' }).first()).toContainText(study.series[0].values.at(-1)!.toFixed(2))

  await page.keyboard.press('ArrowLeft')
  const previous = BARS.at(-2)!
  await expect(header).toContainText(new Date(previous.t * 1_000).toISOString().slice(0, 10))
  await expect(header).toContainText(`Close ${previous.c.toFixed(2)}`)
  await expect(chart.locator('.technical-legend').filter({ hasText: 'MA(50)' }).first()).toContainText(study.series[0].values.at(-2)!.toFixed(2))

  await page.keyboard.press('Home')
  await expect(header).toContainText(new Date(BARS[0].t * 1_000).toISOString().slice(0, 10))
  await expect(chart.locator('.technical-legend').filter({ hasText: 'MA(50)' }).first()).toContainText('—')
  await expect(page.locator('.price-chart-frame .chart-foot')).toContainText('PRICE · NATIVE QUOTE UNITS')
  await expect(page.locator('.price-chart-frame .chart-foot')).toContainText('TIME · UTC')
  await expect(page.locator('.price-chart-frame .chart-foot')).toContainText('SNAPSHOT · CURRENT STORE')
  await expect(page.locator('.price-toolbar')).toContainText('ccxt:binance')
  await expect(page.locator('.price-toolbar')).toContainText('qualified')

  await page.keyboard.press('Escape')
  await expect(header).toContainText(`Close ${last.c.toFixed(2)}`)
  await expect(host.locator('.technical-cursor').first()).not.toBeVisible()
})

test('@reference-only touch tap inspects the exact candle and aligned backend study', async ({ browser }) => {
  const context = await touchContext(browser)
  try {
    const page = await context.newPage()
    await preparePage(page, { candles: { 'XRP/USDT': BARS } })
    await page.goto('/#page=data&pane=PriceChart')
    const chart = page.locator('[data-panel-id=primary] .technical-chart')
    const host = chart.locator('.technical-host')
    await expect(host.locator('canvas').first()).toBeVisible()
    await expect(chart.locator('.technical-legend').filter({ hasText: 'MA(50)' }).first()).toBeVisible()
    const bounds = (await host.boundingBox())!
    await page.touchscreen.tap(bounds.x + bounds.width * 0.6, bounds.y + bounds.height * 0.55)

    const header = chart.locator('.technical-ohlc')
    await expect(header).not.toContainText(`Close ${BARS.at(-1)!.c.toFixed(2)}`)
    const text = await header.innerText()
    const date = text.match(/^\d{4}-\d\d-\d\d/)?.[0]
    const selected = BARS.find(bar => new Date(bar.t * 1_000).toISOString().startsWith(date ?? '\u0000'))
    expect(selected).toBeDefined()
    await expect(header).toContainText(`Open ${selected!.o.toFixed(2)}`)
    await expect(header).toContainText(`High ${selected!.h.toFixed(2)}`)
    await expect(header).toContainText(`Low ${selected!.l.toFixed(2)}`)
    await expect(header).toContainText(`Close ${selected!.c.toFixed(2)}`)
    const study = studySeries('sma:50', BARS)
    if (!('series' in study)) throw new Error('fixture SMA unexpectedly refused its window')
    const index = BARS.findIndex(bar => bar.t === selected!.t)
    const value = study.series[0].values[index]
    await expect(chart.locator('.technical-legend').filter({ hasText: 'MA(50)' }).first()).toContainText(value === null ? '—' : value.toFixed(2))
    await expect(page.locator('.price-chart-frame .chart-foot')).toContainText('TIME · UTC')
    await expect(page.locator('.price-chart-frame .chart-foot')).toContainText('AS OF ')
    await expect(page.locator('.price-toolbar')).toContainText('ccxt:binance')
  } finally {
    await context.close()
  }
})

test('@reference-only changing a study clears the inspected bar before the new composition', async ({ page }) => {
  const chart = await openChart(page, 'classic')
  await chart.getByRole('button', { name: 'All data', exact: true }).click()
  const host = chart.locator('.technical-host')
  await host.focus()
  await page.keyboard.press('ArrowLeft')
  const header = chart.locator('.technical-ohlc')
  await expect(header).toContainText(new Date(BARS.at(-2)!.t * 1_000).toISOString().slice(0, 10))
  await expect(host.locator('.technical-cursor').first()).toBeVisible()

  const indicators = page.getByRole('button', { name: /^Indicators/ })
  await indicators.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Indicators' })
  const sma50 = dialog.locator('.indicator-choice').filter({ hasText: 'sma:50' }).locator('input[type=checkbox]')
  await sma50.focus()
  await page.keyboard.press('Space')
  await expect(sma50).not.toBeChecked()
  const done = dialog.getByRole('button', { name: 'Done' })
  await done.focus()
  await page.keyboard.press('Enter')

  await expect(header).toContainText(`Close ${BARS.at(-1)!.c.toFixed(2)}`)
  await expect(host.locator('.technical-cursor').first()).not.toBeVisible()
  await expect(chart.locator('.technical-legend').filter({ hasText: 'MA(50)' })).toHaveCount(0)
  await expect(page.locator('.price-chart-frame .chart-foot')).toContainText('TIME · UTC')
  await expect(page.locator('.price-toolbar')).toContainText('ccxt:binance')
  await expect(page.locator('.price-toolbar')).toContainText('qualified')
})

test('@reference-only loading, empty and failed candle states stay explicit', async ({ page }) => {
  await preparePage(page, { candles: { 'XRP/USDT': [] } })
  let release!: () => void
  const suspended = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/candles/**', async route => { await suspended; await route.fallback() })
  await page.goto('/#page=data&pane=PriceChart')
  await expect(page.locator('.price-panel .placeholder')).toContainText('loading…')
  release()
  await expect(page.locator('.price-panel .placeholder')).toContainText('no bars in window')

  let fail = false
  await page.route('**/api/candles/**', async route => {
    if (fail) await route.fulfill({ status: 503, json: { detail: 'fixture candle failure' } })
    else await route.fallback()
  })
  fail = true
  await page.reload()
  await expect(page.locator('.price-panel .placeholder')).toContainText('Error: 503 Service Unavailable')
  await expect(page.locator('.technical-host')).toHaveCount(0)
})

test('@reference-only a window shorter than a study names the skipped study and keeps the rest', async ({ page }) => {
  const chart = await openChart(page, 'classic', BARS.slice(0, 120))
  await expect(chart.locator('.technical-skipped')).toHaveText('MA(200) needs 201 bars (window 120)')
  await expect(chart.getByText('MA(50)', { exact: false }).first()).toBeVisible()
  await expect(page.locator('.chip.fail')).toHaveCount(0)
  // The market renderer has no technical header, so the refusal is disclosed as a status chip.
  await page.keyboard.press('Escape')
  await page.getByLabel('Plot renderer').selectOption('market')
  await expect(page.getByRole('status').filter({ hasText: 'studies skipped' })).toHaveText('studies skipped · MA(200) needs 201 bars (window 120)')
})

test('@reference-only a 24/7 series marks intervals without an observation on the date axis', async ({ page }) => {
  const continuous = walkBars(200, '2025-10-06', false)
  const gapped = [...continuous.slice(0, 120), ...continuous.slice(123)]
  const chart = await openChart(page, 'classic', gapped)
  // one mark per date strip (under price and under MACD)
  await expect(chart.locator('.technical-gap')).toHaveCount(2)
  await expect(chart.locator('.technical-gap').first()).toHaveAttribute('title', /^3 intervals without an observation before /)
})

test('@reference-only toolbar zoom is not re-applied when the chart recomposes', async ({ page }) => {
  const chart = await openChart(page, 'classic')
  await page.keyboard.press('Escape') // restore the panel so the toolbar is reachable
  const host = chart.locator('.technical-host')
  const zoomIn = page.locator('button[aria-label="Zoom in"]:visible').first()
  // Wait for each zoom step to land before reading the window (the attribute is set at mount).
  const initial = await host.getAttribute('data-visible-range')
  await zoomIn.click()
  await expect.poll(() => host.getAttribute('data-visible-range')).not.toBe(initial)
  const once = await host.getAttribute('data-visible-range')
  await zoomIn.click()
  await expect.poll(() => host.getAttribute('data-visible-range')).not.toBe(once)
  const zoomed = await host.getAttribute('data-visible-range')
  // A style change rebuilds the panel stack and restores the window; it must not zoom again.
  await page.getByLabel('Chart style').selectOption('default')
  await expect(page.locator('[data-panel-id=primary] .technical-chart')).toHaveAttribute('data-chart-style', 'default')
  await expect.poll(() => page.locator('[data-panel-id=primary] .technical-host').getAttribute('data-visible-range')).toBe(zoomed)
})
