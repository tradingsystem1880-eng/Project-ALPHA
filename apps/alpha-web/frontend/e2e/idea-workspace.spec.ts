import { expect, test, type Page } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

// Synthetic API responses check presentation only; no market evidence is used.
const CARD = '0f1aabc8218c'
const RUN_A = 'a'.repeat(16)
const RUN_B = 'b'.repeat(16)
const FIGURE = 'equity_underwater'
const PIXEL = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='

const reading = (sentence: string) => ({
  sentence, evidence: { word: 'too little to read', because: ['12 closed trades (fewer than 30 make too few to judge).'] }, measures: [],
  checks: [{ name: 'data-health', state: 'sound', detail: 'the data health check is clean' }],
  counts: { trial_n: 3, family_trials: 1, variants_tried: 2, best_of: 3, family_id: 'spine:ma_cross' }, aim: { source: 'default', basis: null, rows: [] },
})
const tested = (asset: string) => ({
  asset, rule: 'ma_cross (fast=5, slow=20)', data_from: '2020-01-02', data_to: '2024-06-28', scored_from: '2022-01-03', scored_to: '2024-06-28',
  held_back: 'This test saw the reserved period.', assets: [],
})
const runRow = (id: string, day: string, asset: string, sentence: string) => ({
  kind: 'rule test', id, recorded_at: `${day}T10:00:00+00:00`, word: 'too little to read', sentence, reading: reading(sentence), tested: tested(asset),
  aim: { measure: 'out-of-sample Sharpe', observed: 0.75, aim: 0.78, relation: 'within the uncertainty of the aim' }, figures_available: [FIGURE], labels: ['exploratory'],
  checks: id === RUN_A ? [{ tool: 'costs.break_even', word: 'exploratory', reading: 'Costs would have to reach 14 basis points a side.', file: 'diagnostics/x.json', labels: ['exploratory'] }] : [],
  studies: [], totals: {}, problem: null,
})
const file = {
  card: { id: CARD, claim: 'Quiet weeks lead to a bigger move.', mechanism: 'Traders under-react to calm.', source: 'a library record', baseline: 'Buy and hold.' },
  map: [], follows: [], readings_total: 3, readings_shown_from: 0,
  readings: [
    { kind: 'setup find', id: 'f1', recorded_at: '2026-11-18T09:00:00+00:00', tested: { assets: ['SPY'] }, totals: { accepted: 12, pending: 1, set_aside: 3 },
      studies: [{ id: 's1', reading: 'Too few occurrences (12) to judge.', labels: [] }], checks: [], figures_available: [], labels: [], problem: null },
    runRow(RUN_A, '2026-11-19', 'SPY', 'First run sentence.'), runRow(RUN_B, '2026-11-20', 'QQQ', 'Second run sentence.'),
  ],
  counts: {}, open_points: { not_stated: ['what would disprove it'], map_not_yet: ['held-back confirmation'], too_little_to_read: [RUN_A], next_steps: [] },
}
const meta = (runId: string) => ({
  figure_id: FIGURE, title: 'Equity and drawdown', subtitle: `run ${runId.slice(0, 8)}`, caption: 'caption', alt_text: 'A synthetic drawdown figure', question: 'How deep were the losses?',
  plain_language_answer: 'Answer', uncertainty: 'Synthetic fixture only', caveat: 'No research meaning', cache_key: 'k'.repeat(8), etag: 'e', format: 'svg', height_in: 5, width_in: 11,
  image_url: `/api/runs/${runId}/figures/${FIGURE}/image`, panels: [], renderer_version: 1, source_artifacts: [], truncation_note: null, x_label: 'date',
})

async function mock(page: Page, list: unknown[] = [{ id: CARD, claim: file.card.claim, tested: true, not_stated: [], tests_linked: 3, saved_at: '2026-11-20T00:00:00+00:00' }]): Promise<void> {
  await preparePage(page, { runs: [RUN_A, RUN_B].map(run_id => ({ run_id, kind: 'runs', display_name: `Run ${run_id.slice(0, 1)}` })) })
  await page.route('**/api/ideas', route => route.fulfill({ json: { cards: list, total: list.length, truncated: false } }))
  await page.route(`**/api/ideas/${CARD}`, route => route.fulfill({ json: file }))
  for (const id of [RUN_A, RUN_B]) {
    await page.route(`**/api/runs/${id}`, route => route.fulfill({ json: { run_id: id, kind: 'runs', display_name: 'Run', manifest: {}, has_trades: false } }))
    await page.route(`**/api/runs/${id}/figures`, route => route.fulfill({ json: { run_id: id, kind: 'runs', renderer_version: 1, items: [
      { figure_id: FIGURE, available: true, title: 'Equity and drawdown', summary: 'How deep the losses went.', section: 'risk', panel_count: 1, unavailable_reason: null }] } }))
    await page.route(`**/api/runs/${id}/figures/${FIGURE}?*`, route => route.fulfill({ json: meta(id) }))
    await page.route(`**/api/runs/${id}/figures/${FIGURE}`, route => route.fulfill({ json: meta(id) }))
    await page.route(`**/api/runs/${id}/figures/${FIGURE}/image*`, route => route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from(PIXEL, 'base64') }))
  }
}

test('the list opens one page that tells the whole story, and a click on a test changes the charts', async ({ page }) => {
  await mock(page)
  await page.goto('/#page=research&pane=IdeaWorkspace')
  await expect(page.getByRole('heading', { name: 'Ideas', exact: true })).toBeVisible()
  await page.locator(`.idea-card[data-card="${CARD}"]`).click()
  await expect(page.getByRole('heading', { name: 'Quiet weeks lead to a bigger move.' })).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'Steps of this idea' })
  await expect(nav.locator('.idea-nav-item')).toHaveCount(11)
  await expect(nav.getByRole('button', { name: /9 RD-Agent steps: not built yet/ })).toBeVisible()
  await expect(page.getByText('No RD-Agent work is linked to this idea yet.')).toBeVisible()
  await expect(page.getByText('The rule is ma cross, with fast 5, slow 20 on QQQ.')).toBeVisible()
  await page.getByText('See the exact spec').click()
  await expect(page.getByLabel('The rule exactly as stored')).toContainText('ma_cross (fast=5, slow=20)')
  await expect(page.getByText('2020-01-02 to 2024-06-28').first()).toBeVisible()
  await expect(page.locator('.idea-t-row')).toHaveCount(3)
  await expect(page.locator(`.idea-t-row[data-run="${RUN_B}"]`)).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: `Charts for run ${RUN_B.slice(0, 8)}` })).toBeVisible()
  await expect(page.getByText('How deep the losses went.')).toBeVisible()
  await expect(page.getByRole('img', { name: 'A synthetic drawdown figure' })).toBeVisible()
  await page.locator(`.idea-t-row[data-run="${RUN_A}"]`).click()
  await expect(page.getByRole('heading', { name: `Charts for run ${RUN_A.slice(0, 8)}` })).toBeVisible()
  await expect(page.getByRole('heading', { name: `Checks for run ${RUN_A.slice(0, 8)}` })).toBeVisible()
  await expect(page.getByText('Costs would have to reach 14 basis points a side.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Expand', exact: true })).toBeVisible()
  await expect(page.locator('.idea-story')).not.toContainText(/\b(supported|rejected|verdict|profit)\b/i)
})

test('a figure opens full screen and nothing on the page sticks out at phone width', async ({ page }) => {
  await mock(page)
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto(`/#page=research&pane=IdeaWorkspace&idea=${CARD}`)
  await expect(page.getByRole('heading', { name: 'Quiet weeks lead to a bigger move.' })).toBeVisible()
  await page.getByRole('button', { name: 'Expand', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  // The shell chrome is outside this page; the idea page itself must fit its own box.
  const overflow = await page.evaluate(() => {
    const root = document.querySelector('.idea-root')
    const wide = [...document.querySelectorAll('.idea-root *')].filter(el => el.getBoundingClientRect().right > (root?.getBoundingClientRect().right ?? 0) + 1)
    return wide.filter(el => !el.closest('.idea-nav')).map(el => `${el.tagName}.${el.className}`).join(' | ')
  })
  expect(overflow).toBe('')
})

test('an empty store and a failed read are said in words', async ({ page }) => {
  await mock(page, [])
  await page.goto('/#page=research&pane=IdeaWorkspace')
  await expect(page.getByText('No idea card is written yet.')).toBeVisible()
  await page.unroute('**/api/ideas')
  await page.route('**/api/ideas', route => route.fulfill({ status: 409, json: { code: 'conflict', message: 'The idea list could not be read.', recovery_action: 'retry', field_errors: [], request_id: 'r' } }))
  await page.reload()
  await expect(page.getByRole('alert')).toBeVisible()
})

test('the research front screen shows the idea cards when there are no research cases', async ({ page }) => {
  await mock(page)
  await page.route('**/api/research/cases*', route => route.fulfill({ json: { items: [], next_cursor: null } }))
  await page.goto('/#page=research&pane=ResearchBacklog')
  await expect(page.getByText('NO RESEARCH CASES YET')).toBeVisible()
  await expect(page.getByText('1 idea card written.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Open Ideas' })).toHaveAttribute('href', '#page=research&pane=IdeaWorkspace')
})
