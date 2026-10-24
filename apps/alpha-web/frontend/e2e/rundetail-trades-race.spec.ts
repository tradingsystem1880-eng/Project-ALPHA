import { expect, test, type Page, type Route } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

declare global {
  interface Window {
    __runDetailOwnershipObserver?: MutationObserver
    __staleRunDetailSummary?: boolean
    __staleRunDetailCatalogue?: boolean
  }
}

const RUN_A = 'a'.repeat(16)
const RUN_B = 'b'.repeat(16)
const RUN_EMPTY = 'c'.repeat(16)
const A_INSTRUMENT = 'RUN_A_ONLY'
const B_INSTRUMENT = 'RUN_B_ONLY'
const A_FIGURE_ID = 'RUN_A_ONLY_FIGURE'

const A_TRADE = {
  instrument_id: A_INSTRUMENT,
  side: 'long',
  quantity: 1,
  entry_price: 10,
  exit_price: 11,
  realized_pnl: 1,
  realized_return: 0.1,
  entry_ts: '2025-01-01T00:00:00Z',
  exit_ts: '2025-01-02T00:00:00Z',
}

const B_TRADE = { ...A_TRADE, instrument_id: B_INSTRUMENT }

type TradeReply = { status: number; body: unknown }

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function runDetail(runId: string, symbol: string) {
  return {
    run_id: runId,
    kind: 'runs',
    mtime: 1,
    display_name: `Synthetic ${symbol} report`,
    manifest: { command: 'backtest_run', symbol, schema_version: 3 },
    has_equity: false,
    has_trades: true,
    has_tearsheet: false,
    has_forecast: false,
    has_nulls: false,
    has_trials: false,
    has_forecast_paths: false,
    has_propfirm_paths: false,
    has_origins: false,
  }
}

async function prepareReports(page: Page, bTrades: (route: Route) => Promise<void>): Promise<void> {
  await preparePage(page, {
    runs: [RUN_A, RUN_B, RUN_EMPTY].map((runId) => ({
      run_id: runId,
      kind: 'runs',
      display_name: `Synthetic run ${runId.slice(0, 1)}`,
    })),
  })

  for (const [runId, symbol] of [[RUN_A, 'SYMBOL_A'], [RUN_B, 'SYMBOL_B'], [RUN_EMPTY, 'SYMBOL_EMPTY']]) {
    await page.route(`**/api/runs/${runId}`, (route) => route.fulfill({ json: runDetail(runId, symbol) }))
    await page.route(`**/api/runs/${runId}/figures`, (route) => route.fulfill({
      json: { run_id: runId, kind: 'runs', renderer_version: 1, items: [] },
    }))
  }

  await page.route(`**/api/runs/${RUN_A}/trades`, (route) => route.fulfill({ json: [A_TRADE] }))
  await page.route(`**/api/runs/${RUN_B}/trades`, bTrades)
  await page.route(`**/api/runs/${RUN_EMPTY}/trades`, (route) => route.fulfill({ json: [] }))
}

type OwnershipHandlers = {
  run?: (runId: string, route: Route) => Promise<void>
  figures?: (runId: string, route: Route) => Promise<void>
}

function figureCatalogue(runId: string, figureId?: string) {
  return {
    run_id: runId,
    kind: 'runs',
    renderer_version: 1,
    items: figureId ? [{
      figure_id: figureId,
      available: true,
      title: figureId,
      label: figureId,
      question: `Question for ${figureId}`,
      uncertainty: 'Synthetic fixture only',
      caveat: 'No research meaning',
    }] : [],
  }
}

async function prepareOwnershipReports(page: Page, handlers: OwnershipHandlers = {}): Promise<void> {
  await preparePage(page, {
    runs: [RUN_A, RUN_B].map((runId) => ({
      run_id: runId,
      kind: 'runs',
      display_name: `Synthetic run ${runId.slice(0, 1)}`,
    })),
  })

  for (const [runId, symbol] of [[RUN_A, 'SYMBOL_A'], [RUN_B, 'SYMBOL_B']]) {
    await page.route(`**/api/runs/${runId}`, async (route) => {
      if (handlers.run) return handlers.run(runId, route)
      return route.fulfill({ json: runDetail(runId, symbol) })
    })
    await page.route(`**/api/runs/${runId}/figures`, async (route) => {
      if (handlers.figures) return handlers.figures(runId, route)
      return route.fulfill({ json: figureCatalogue(runId, runId === RUN_A ? A_FIGURE_ID : undefined) })
    })
    await page.route(`**/api/runs/${runId}/trades`, (route) => route.fulfill({ json: [] }))
  }
  await page.route('**/api/runs/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith(`/figures/${A_FIGURE_ID}`)) {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=',
          'base64',
        ),
      })
    }
    return route.fallback()
  })
}

async function selectRun(page: Page, runId: string): Promise<void> {
  await page.evaluate((id) => { window.location.hash = `#run=${id}` }, runId)
}

async function selectTrades(page: Page): Promise<void> {
  await page.getByRole('tree', { name: 'Report sections' })
    .getByRole('button', { name: /List of trades/ })
    .click()
}

function tradesCountButton(page: Page, label: string) {
  return page.getByRole('tree', { name: 'Report sections' })
    .getByRole('button', { name: label, exact: true })
}

async function csvDownload(page: Page, runId: string, expected: string): Promise<void> {
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(`${runId.slice(0, 8)}-trades.csv`)
  const stream = await download.createReadStream()
  if (!stream) throw new Error('CSV download stream was not available')
  const chunks: Buffer[] = []
  for await (const chunk of stream) chunks.push(Buffer.from(chunk))
  expect(Buffer.concat(chunks).toString('utf8')).toBe(expected)
}

test('RunDetail never shows or exports previous-run trades while the selected run is loading', async ({ page }) => {
  const bStarted = deferred<void>()
  const bReply = deferred<TradeReply>()
  const bResponded = deferred<void>()

  await prepareReports(page, async (route) => {
    bStarted.resolve()
    const reply = await bReply.promise
    await route.fulfill({ status: reply.status, json: reply.body })
    bResponded.resolve()
  })
  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
  await selectTrades(page)
  await expect(tradesCountButton(page, 'List of trades (1)')).toBeVisible()
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toBeVisible()
  await csvDownload(
    page,
    RUN_A,
    'instrument_id,side,quantity,entry_price,exit_price,realized_pnl,realized_return,entry_ts,exit_ts\nRUN_A_ONLY,long,1,10,11,1,0.1,2025-01-01T00:00:00Z,2025-01-02T00:00:00Z',
  )

  await selectRun(page, RUN_B)
  await bStarted.promise
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_B')
  await selectTrades(page)
  await expect(tradesCountButton(page, 'List of trades')).toBeVisible()
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toHaveCount(0)
  await expect(page.getByRole('toolbar', { name: 'Report toolbar' }).getByRole('status')).toContainText('Loading trades')
  await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled()

  bReply.resolve({ status: 200, body: [B_TRADE] })
  await bResponded.promise
  await expect(tradesCountButton(page, 'List of trades (1)')).toBeVisible()
  await expect(page.getByText(B_INSTRUMENT, { exact: true })).toBeVisible()
  await csvDownload(
    page,
    RUN_B,
    'instrument_id,side,quantity,entry_price,exit_price,realized_pnl,realized_return,entry_ts,exit_ts\nRUN_B_ONLY,long,1,10,11,1,0.1,2025-01-01T00:00:00Z,2025-01-02T00:00:00Z',
  )
})

test('a late B trade success cannot replace A after rapid A to B to A selection', async ({ page }) => {
  const bStarted = deferred<void>()
  const bReply = deferred<TradeReply>()
  const bResponded = deferred<void>()
  await prepareReports(page, async (route) => {
    bStarted.resolve()
    const reply = await bReply.promise
    await route.fulfill({ status: reply.status, json: reply.body })
    bResponded.resolve()
  })

  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
  await selectTrades(page)
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toBeVisible()
  await selectRun(page, RUN_B)
  await bStarted.promise
  await selectRun(page, RUN_A)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await selectTrades(page)
  await expect(tradesCountButton(page, 'List of trades (1)')).toBeVisible()
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toBeVisible()

  const response = page.waitForResponse((item) => item.url().endsWith(`/api/runs/${RUN_B}/trades`))
  bReply.resolve({ status: 200, body: [B_TRADE] })
  await Promise.all([response, bResponded.promise])
  await expect(tradesCountButton(page, 'List of trades (1)')).toBeVisible()
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toBeVisible()
  await expect(page.getByText(B_INSTRUMENT, { exact: true })).toHaveCount(0)
})

test('trade request errors stay distinct from a legitimate empty trades projection', async ({ page }) => {
  await prepareReports(page, (route) => route.fulfill({
    status: 503,
    json: { detail: 'Synthetic trades service unavailable' },
  }))
  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
  await selectRun(page, RUN_B)
  await expect(page.getByRole('toolbar', { name: 'Report toolbar' }).getByRole('alert'))
    .toContainText('Trades unavailable')
  await expect(tradesCountButton(page, 'List of trades')).toBeVisible()
  await selectTrades(page)
  await expect(page.getByText(/Could not load trades/i)).toBeVisible()
  await expect(page.getByText(/No discrete trades recorded/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled()

  await selectRun(page, RUN_EMPTY)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_EMPTY')
  await selectTrades(page)
  await expect(tradesCountButton(page, 'List of trades (0)')).toBeVisible()
  await expect(page.getByText(/No discrete trades recorded/)).toBeVisible()
  await expect(page.getByRole('toolbar', { name: 'Report toolbar' }).getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled()
})

test('a stale trade error after returning to A does not replace A with an error', async ({ page }) => {
  const bStarted = deferred<void>()
  const bReply = deferred<TradeReply>()
  const bResponded = deferred<void>()
  await prepareReports(page, async (route) => {
    bStarted.resolve()
    const reply = await bReply.promise
    await route.fulfill({ status: reply.status, json: reply.body })
    bResponded.resolve()
  })

  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toBeVisible()
  await selectTrades(page)
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toBeVisible()
  await selectRun(page, RUN_B)
  await bStarted.promise
  await selectRun(page, RUN_A)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await selectTrades(page)

  const response = page.waitForResponse((item) => item.url().endsWith(`/api/runs/${RUN_B}/trades`))
  bReply.resolve({ status: 503, body: { detail: 'Synthetic stale failure' } })
  await Promise.all([response, bResponded.promise])
  await expect(tradesCountButton(page, 'List of trades (1)')).toBeVisible()
  await expect(page.getByText(A_INSTRUMENT, { exact: true })).toBeVisible()
  await expect(page.getByRole('toolbar', { name: 'Report toolbar' }).getByRole('alert')).toHaveCount(0)
})

test('RunDetail hides A summary and figures while B detail and catalogue are pending', async ({ page }) => {
  const bRunStarted = deferred<void>()
  const bRunReply = deferred<TradeReply>()
  const bFiguresStarted = deferred<void>()
  const bFiguresReply = deferred<TradeReply>()

  await prepareOwnershipReports(page, {
    run: async (runId, route) => {
      if (runId !== RUN_B) return route.fulfill({ json: runDetail(runId, 'SYMBOL_A') })
      bRunStarted.resolve()
      const reply = await bRunReply.promise
      return route.fulfill({ status: reply.status, json: reply.body })
    },
    figures: async (runId, route) => {
      if (runId !== RUN_B) return route.fulfill({ json: figureCatalogue(runId, 'RUN_A_ONLY_FIGURE') })
      bFiguresStarted.resolve()
      const reply = await bFiguresReply.promise
      return route.fulfill({ status: reply.status, json: reply.body })
    },
  })

  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await expect(page.locator('.report-summary-figures')).toContainText('RUN_A_ONLY_FIGURE')
  await page.evaluate(() => {
    window.__staleRunDetailSummary = false
    window.__staleRunDetailCatalogue = false
    const scan = () => {
      if (!window.location.hash.includes('run=bbbbbbbbbbbbbbbb')) return
      const summary = document.querySelector('table.summary-table')?.textContent ?? ''
      const figures = document.querySelector('.report-summary-figures')?.textContent ?? ''
      if (summary.includes('SYMBOL_A')) window.__staleRunDetailSummary = true
      if (figures.includes('RUN_A_ONLY_FIGURE')) window.__staleRunDetailCatalogue = true
    }
    const observer = new MutationObserver(scan)
    observer.observe(document.body, { attributes: true, childList: true, characterData: true, subtree: true })
    window.__runDetailOwnershipObserver = observer
    scan()
  })

  await selectRun(page, RUN_B)
  await Promise.all([bRunStarted.promise, bFiguresStarted.promise])
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  }))
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toHaveCount(0)
  await expect(page.locator('.report-summary-figures')).toHaveCount(0)
  const staleOwnership = await page.evaluate(() => {
    window.__runDetailOwnershipObserver?.disconnect()
    return {
      summary: window.__staleRunDetailSummary ?? false,
      catalogue: window.__staleRunDetailCatalogue ?? false,
    }
  })
  expect(staleOwnership).toEqual({ summary: false, catalogue: false })

  bRunReply.resolve({ status: 200, body: runDetail(RUN_B, 'SYMBOL_B') })
  bFiguresReply.resolve({ status: 200, body: figureCatalogue(RUN_B) })
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_B')
})

test('a late B detail error after rapid A to B to A leaves A summary and figures intact', async ({ page }) => {
  const bRunStarted = deferred<void>()
  const bRunReply = deferred<TradeReply>()
  const bFiguresStarted = deferred<void>()
  const bFiguresReply = deferred<TradeReply>()

  await prepareOwnershipReports(page, {
    run: async (runId, route) => {
      if (runId !== RUN_B) return route.fulfill({ json: runDetail(runId, 'SYMBOL_A') })
      bRunStarted.resolve()
      const reply = await bRunReply.promise
      return route.fulfill({ status: reply.status, json: reply.body })
    },
    figures: async (runId, route) => {
      if (runId !== RUN_B) return route.fulfill({ json: figureCatalogue(runId, 'RUN_A_ONLY_FIGURE') })
      bFiguresStarted.resolve()
      const reply = await bFiguresReply.promise
      return route.fulfill({ status: reply.status, json: reply.body })
    },
  })

  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await expect(page.locator('.report-summary-figures')).toContainText('RUN_A_ONLY_FIGURE')
  await selectRun(page, RUN_B)
  await Promise.all([bRunStarted.promise, bFiguresStarted.promise])
  await selectRun(page, RUN_A)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await expect(page.locator('.report-summary-figures')).toContainText('RUN_A_ONLY_FIGURE')

  const runResponse = page.waitForResponse((item) => item.url().endsWith(`/api/runs/${RUN_B}`))
  const figuresResponse = page.waitForResponse((item) => item.url().endsWith(`/api/runs/${RUN_B}/figures`))
  bRunReply.resolve({ status: 503, body: { detail: 'Synthetic stale detail failure' } })
  bFiguresReply.resolve({ status: 200, body: figureCatalogue(RUN_B) })
  await Promise.all([runResponse, figuresResponse])
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await expect(page.locator('.report-summary-figures')).toContainText('RUN_A_ONLY_FIGURE')
  await expect(page.getByText(/Could not load this run/i)).toHaveCount(0)
})

test('late B detail and catalogue completions after report unmount do not restore RunDetail', async ({ page }) => {
  const bRunStarted = deferred<void>()
  const bRunReply = deferred<TradeReply>()
  const bFiguresStarted = deferred<void>()
  const bFiguresReply = deferred<TradeReply>()

  await prepareOwnershipReports(page, {
    run: async (runId, route) => {
      if (runId !== RUN_B) return route.fulfill({ json: runDetail(runId, 'SYMBOL_A') })
      bRunStarted.resolve()
      const reply = await bRunReply.promise
      return route.fulfill({ status: reply.status, json: reply.body })
    },
    figures: async (runId, route) => {
      if (runId !== RUN_B) return route.fulfill({ json: figureCatalogue(runId, 'RUN_A_ONLY_FIGURE') })
      bFiguresStarted.resolve()
      const reply = await bFiguresReply.promise
      return route.fulfill({ status: reply.status, json: reply.body })
    },
  })
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto(`/#run=${RUN_A}`)
  await expect(page.getByRole('table', { name: 'Summary — what this run recorded' })).toContainText('SYMBOL_A')
  await selectRun(page, RUN_B)
  await Promise.all([bRunStarted.promise, bFiguresStarted.promise])
  await page.evaluate(() => { window.location.hash = '#page=overview' })
  await expect(page.locator('.report-document')).toHaveCount(0)

  const runResponse = page.waitForResponse((item) => item.url().endsWith(`/api/runs/${RUN_B}`))
  const figuresResponse = page.waitForResponse((item) => item.url().endsWith(`/api/runs/${RUN_B}/figures`))
  bRunReply.resolve({ status: 200, body: runDetail(RUN_B, 'SYMBOL_B') })
  bFiguresReply.resolve({ status: 200, body: figureCatalogue(RUN_B) })
  await Promise.all([runResponse, figuresResponse])
  await expect(page.locator('.report-document')).toHaveCount(0)
  expect(pageErrors).toEqual([])
})
