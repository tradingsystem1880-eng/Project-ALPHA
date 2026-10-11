import { expect, test } from '@playwright/test'
import { openTask, preparePage } from './support/workstationHarness'

const id = 'b'.repeat(32)
const saved = {
  id, run_id: 'abcdef0123456789', question: 'Why did losses concentrate?', cutoff: '2020-01-02',
  parent_id: null, status: 'completed', error: null, active_job_id: null,
  requests_remaining: 9, turns_remaining: 3, can_resume: false, can_followup: true,
  comparison_draft: null, acquisition_status: 'not_started', comparison_child_id: null,
  progress: [], receipts: [{id: 'receipt-1', status: 'succeeded', authority: 'none'}],
  report: {findings: [{observation: 'Losses occurred in a bounded episode.', receipt_ids: ['receipt-1']}],
    hypotheses: ['Market exposure may contribute.'], next_tests: ['Compare verified proxy prices.'], limitations: ['Causation not established.']},
}

test('recorded investigation restores evidence and requires explicit acquisition preview', async ({page}) => {
  await preparePage(page, {runs: [{run_id: 'abcdef0123456789', kind: 'runs', command: 'backtest run',
    display_name: 'Recorded SPY research run', market: 'unknown', label: 'SPY', symbol: 'SPY',
    strategy: 'ts_momentum', mtime: 1700000000, passed: null, verdict: null}]})
  let drafts = 0
  let showReads = 0
  let acquisitions = 0
  await page.route('**/api/investigations**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.includes('/eligibility/')) return route.fulfill({json: {eligible: true, cutoff: '2020-01-02'}})
    if (path.endsWith('/comparison-plan')) {
      drafts++
      expect(route.request().postDataJSON()).toEqual({series: [{symbol: 'SPY', asset_class: 'etf', role: 'market'}]})
      return route.fulfill({json: {plan_sha256: 'a'.repeat(64), start: '2020-01-01', end: '2020-01-02', provider: 'tiingo', series: [{symbol: 'SPY', asset_class: 'etf', role: 'market'}], currency: 'USD', venue: 'US', calendar: 'XNYS'}})
    }
    if (path.endsWith(id) && ++showReads === 1) return route.fulfill({status: 503, json: {detail: 'Temporary session lock'}})
    if (path.endsWith('/comparisons')) { acquisitions++; return route.fulfill({json: {job_id: 'acquisition-job', status: 'running'}}) }
    return route.fulfill({json: path.endsWith(id) ? saved : [saved]})
  })
  await page.goto('')
  await openTask(page, 'Results', 'Run library')
  await page.getByRole('tree', {name: 'Navigator'}).locator('.tree-leaf').filter({hasText: 'Recorded SPY research run'}).first().click()
  await page.getByRole('button', {name: 'Investigate this run', exact: true}).click()
  const panel = page.getByRole('region', {name: 'Run investigation'})
  await expect(panel.getByText('Losses occurred in a bounded episode.', {exact: false})).toBeVisible()
  await expect(panel.getByRole('heading', {name: 'Hypotheses to test'})).toBeVisible()
  await expect(panel.getByText('Status temporarily unavailable; retrying.', {exact: false})).toBeVisible()
  await expect(panel.getByText('Status temporarily unavailable; retrying.', {exact: false})).toHaveCount(0)
  await expect(panel.getByText('3 model turns and 9 tool requests remaining', {exact: false})).toBeVisible()
  await panel.getByText('Acquire comparison evidence', {exact: true}).click()
  await expect(panel.getByRole('button', {name: 'Acquire this comparison plan'})).toHaveCount(0)
  await panel.getByRole('button', {name: 'Preview acquisition plan'}).click()
  await expect(panel.getByRole('button', {name: 'Acquire this comparison plan'})).toBeVisible()
  await expect(panel.getByRole('region', {name: 'Comparison acquisition preview'})).toContainText('SPY · ETF · market')
  await expect(panel.getByText('a'.repeat(64), {exact: false})).toHaveCount(0)
  expect(drafts).toBe(1); expect(acquisitions).toBe(0)
  await panel.getByLabel('Comparison symbol 1').fill('QQQ')
  await expect(panel.getByRole('button', {name: 'Acquire this comparison plan'})).toHaveCount(0)
})


test('opening an acquired comparison child leaves resume enabled', async ({page}) => {
  const childId = 'c'.repeat(32)
  await preparePage(page, {runs: [{run_id: 'abcdef0123456789', kind: 'runs', command: 'backtest run',
    display_name: 'Recorded SPY research run', market: 'unknown', label: 'SPY', symbol: 'SPY',
    strategy: 'ts_momentum', mtime: 1700000000, passed: null, verdict: null}]})
  await page.route('**/api/investigations**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.includes('/eligibility/')) return route.fulfill({json: {eligible: true, cutoff: '2020-01-02'}})
    const parent = {...saved, acquisition_status: 'succeeded', comparison_child_id: childId}
    const child = {...saved, id: childId, parent_id: id, status: 'ready', question: 'Compare acquired evidence',
      can_resume: true, can_followup: false, report: null}
    return route.fulfill({json: path.endsWith(childId) ? child : path.endsWith(id) ? parent : [parent]})
  })
  await page.goto('')
  await openTask(page, 'Results', 'Run library')
  await page.getByRole('tree', {name: 'Navigator'}).locator('.tree-leaf').filter({hasText: 'Recorded SPY research run'}).click()
  await page.getByRole('button', {name: 'Investigate this run', exact: true}).click()
  const panel = page.getByRole('region', {name: 'Run investigation'})
  await panel.getByText('Acquire comparison evidence', {exact: true}).click()
  await panel.getByRole('button', {name: 'Open comparison investigation'}).click()
  await expect(panel.getByRole('button', {name: 'Resume investigation'})).toBeEnabled()
  await expect(panel.getByLabel('Saved investigations')).toHaveValue(childId)
})


test('completed acquisition can finish its cached comparison handoff', async ({page}) => {
  await preparePage(page, {runs: [{run_id: 'abcdef0123456789', kind: 'runs', command: 'backtest run',
    display_name: 'Recorded SPY research run', market: 'unknown', label: 'SPY', symbol: 'SPY',
    strategy: 'ts_momentum', mtime: 1700000000, passed: null, verdict: null}]})
  let acquiredHash: string | null = null
  await page.route('**/api/investigations**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.includes('/eligibility/')) return route.fulfill({json: {eligible: true, cutoff: '2020-01-02'}})
    if (path.endsWith('/comparisons')) {
      acquiredHash = route.request().postDataJSON().plan_sha256
      return route.fulfill({json: {job_id: 'recovery-job', status: 'running'}})
    }
    const parent = {...saved, acquisition_status: 'succeeded', comparison_draft: {
      plan_sha256: 'd'.repeat(64), start: '2020-01-01', end: '2020-01-02', provider: 'tiingo',
      currency: 'USD', venue: 'US', calendar: 'XNYS', series: [{symbol: 'SPY', asset_class: 'etf', role: 'market'}]}}
    return route.fulfill({json: path.endsWith(id) ? parent : [parent]})
  })
  await page.goto('')
  await openTask(page, 'Results', 'Run library')
  await page.getByRole('tree', {name: 'Navigator'}).locator('.tree-leaf').filter({hasText: 'Recorded SPY research run'}).click()
  await page.getByRole('button', {name: 'Investigate this run', exact: true}).click()
  const panel = page.getByRole('region', {name: 'Run investigation'})
  await panel.getByText('Acquire comparison evidence', {exact: true}).click()
  await expect(panel.getByRole('button', {name: 'Acquire this comparison plan'})).toBeDisabled()
  await panel.getByRole('button', {name: 'Finish comparison handoff'}).click()
  await expect.poll(() => acquiredHash).toBe('d'.repeat(64))
})


test('missing web job after restart releases controls from durable case state', async ({page}) => {
  await preparePage(page, {runs: [{run_id: 'abcdef0123456789', kind: 'runs', command: 'backtest run',
    display_name: 'Recorded SPY research run', market: 'unknown', label: 'SPY', symbol: 'SPY',
    strategy: 'ts_momentum', mtime: 1700000000, passed: null, verdict: null}]})
  let submitted = false
  await page.route('**/api/jobs/lost-job', route => route.fulfill({status: 404, json: {detail: 'Unknown job'}}))
  await page.route('**/api/investigations**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.includes('/eligibility/')) return route.fulfill({json: {eligible: true, cutoff: '2020-01-02'}})
    if (path.endsWith('/turns')) { submitted = true; return route.fulfill({json: {job_id: 'lost-job', status: 'running'}}) }
    const value = submitted ? {...saved, status: 'interrupted', can_resume: true} : saved
    return route.fulfill({json: path.endsWith(id) ? value : [value]})
  })
  await page.goto('')
  await openTask(page, 'Results', 'Run library')
  await page.getByRole('tree', {name: 'Navigator'}).locator('.tree-leaf').filter({hasText: 'Recorded SPY research run'}).click()
  await page.getByRole('button', {name: 'Investigate this run', exact: true}).click()
  const panel = page.getByRole('region', {name: 'Run investigation'})
  await panel.getByLabel('Investigation follow-up').fill('Check terminal state')
  await panel.getByRole('button', {name: 'Ask follow-up'}).click()
  await expect(panel.getByRole('button', {name: 'Resume investigation'})).toBeEnabled()
  await expect(panel.getByRole('button', {name: 'Cancel investigation'})).toHaveCount(0)
})
