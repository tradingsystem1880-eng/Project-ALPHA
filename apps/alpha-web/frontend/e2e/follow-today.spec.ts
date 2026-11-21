import { expect, test } from '@playwright/test'
import { preparePage } from './support/workstationHarness'

// Synthetic API responses check presentation only; nothing here is a market or research result.
const READINGS = { fast_sma: 101.2, slow_sma: 99.8 }
const FLAT = { open: false, units: 0, entry_price: null, equity: 10000, equity_pct: 0 }
function row(id: string, group: string, asset: string, extra: Record<string, unknown> = {}) {
  return {
    follow_id: id, group, name: `Idea ${id}`, kind: 'rule_test', card_id: '', asset, decision: 'no signal', entry_kind: 'bar',
    readings: READINGS, paper: FLAT, session_date: '2026-11-19', sessions_ago: 0, as_of_text: 'as of the close of 2026-11-19; the newest session',
    behind: false, calendar: 'XNYS', started_at: '2026-11-09T08:00:00+00:00', ...extra,
  }
}
const today = {
  as_of: '2026-11-20T01:00:00+00:00', paper: true, followed: 5, behind: 1,
  markets: [{ calendar: 'XNYS', newest_closed_session: '2026-11-19' }],
  groups: [
    { key: 'new_signal', title: 'NEW SIGNAL', count: 1 }, { key: 'open_position', title: 'OPEN PAPER POSITION', count: 1 },
    { key: 'nothing_today', title: 'NOTHING TODAY', count: 0 }, { key: 'late_or_missed', title: 'LATE OR MISSED', count: 2 }, { key: 'waiting', title: 'WAITING', count: 1 },
  ],
  rows: [
    row('aaaa11112222', 'new_signal', 'AAA', { decision: 'would enter at the next open' }),
    row('bbbb11112222', 'open_position', 'BBB', { decision: 'holding', paper: { open: true, units: 12.5, entry_price: 100, equity: 10150, equity_pct: 1.5 } }),
    row('cccc11112222', 'late_or_missed', 'CCC', { behind: true, sessions_ago: 2, session_date: '2026-11-17' }),
    row('dddd11112222', 'late_or_missed', 'DDD', { entry_kind: 'late', decision: 'late: the bar of this session was not stored when it was due. No decision.' }),
    row('eeee11112222', 'waiting', 'EEE', { session_date: null, sessions_ago: null, readings: {}, decision: 'waiting for its first new bar' }),
  ],
  notice: 'Paper only. Forward use; not research. Not advice.',
}
const entry = (session: string, pct: number) => ({ session, kind: 'bar', words: 'holding', fills: [], readings: READINGS, equity_pct: pct, replay_agrees: true })
const show = {
  record: {
    follow_id: 'bbbb11112222', kind: 'rule_test', source_id: 'b'.repeat(16), assets: ['BBB'], card_id: '', paper_account_percent: 10,
    started_at: '2026-11-09T08:00:00Z', version: 1, spec_sha256: 'f'.repeat(64), supersedes: '', schema: 'AlphaFollowV1',
  },
  state: 'active', entries: { bar: 5, start: 1 }, head: 'h'.repeat(64), reading: 'open paper position', long_at_start: false, waiting_for_first_bar: false, stop_reason: '',
  recent: [entry('2026-11-13', -0.3), entry('2026-11-16', 0.8), entry('2026-11-17', 1.2), entry('2026-11-18', 0.9), entry('2026-11-19', 1.5)],
  paper: { start: 10000, equity: 10150, equity_pct: 1.5 }, replay: { agrees: true, checked: 3, differences: [] },
}

test('Today shows the groups in order, flags a late card, and opens the detail of a card', async ({ page }) => {
  await preparePage(page)
  await page.route('**/api/market/overview*', route => route.fulfill({ json: { assets: [] } }))
  await page.route('**/api/follow/today*', route => route.fulfill({ json: today }))
  await page.route('**/api/follow/bbbb11112222*', route => route.fulfill({ json: show }))
  await page.goto('/#page=research&pane=FollowToday')
  await expect(page.getByRole('heading', { name: 'Followed on paper', exact: true })).toBeVisible()
  await expect(page.getByText('Paper only. Forward use; not research. Not advice.')).toBeVisible()
  await expect(page.getByText('Newest closed session: XNYS 2026-11-19')).toBeVisible()
  await expect(page.getByText('1 of 5 behind')).toBeVisible()
  await expect(page.locator('.follow-group h3')).toHaveText(['NEW SIGNAL (1)', 'OPEN PAPER POSITION (1)', 'LATE OR MISSED (2)', 'WAITING (1)'])
  await expect(page.getByText('NOTHING TODAY (0): none')).toBeVisible()
  await expect(page.locator('.follow-card')).toHaveCount(5)
  await expect(page.locator('.follow-marker')).toHaveText([/Behind: 2 sessions without an entry/, /Late: the bar was not stored when due/])
  await expect(page.locator('.follow-detail')).toHaveCount(0)
  await page.locator('.follow-card[data-id="bbbb11112222"]').focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.follow-card[data-id="bbbb11112222"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: 'Paper equity path' })).toBeVisible()
  await expect(page.locator('.follow-chart polyline')).toHaveCount(1)
  await expect(page.locator('.follow-zero')).toHaveCount(1)
  await expect(page.locator('.follow-table tbody tr')).toHaveCount(5)
  await expect(page.locator('.follow-table tbody tr').first()).toHaveAttribute('data-entry', '2026-11-19')
  await expect(page.getByText('Replay check: agrees (3 sessions compared)')).toBeVisible()
  await expect(page.getByText('10% of a paper account')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open the chart for BBB' })).toBeVisible()
  const chart = await page.locator('.follow-chart').boundingBox()
  expect(chart!.width).toBeGreaterThan(300)
  expect(chart!.height).toBeGreaterThan(120)
  await page.getByRole('button', { name: 'Open the chart for BBB' }).click()
  await expect(page).toHaveURL(/page=data/)
})

test('Today says so in words when the read fails', async ({ page }) => {
  await preparePage(page)
  await page.route('**/api/market/overview*', route => route.fulfill({ json: { assets: [] } }))
  await page.route('**/api/follow/today*', route => route.fulfill({ status: 409, json: { schema_version: 1, code: 'conflict', message: 'alpha follow today could not run', recovery_action: 'Try again.', field_errors: [], request_id: 'test' } }))
  await page.goto('/#page=research&pane=FollowToday')
  await expect(page.getByRole('alert')).toContainText('alpha follow today could not run')
  await expect(page.getByText('Nothing is followed yet.')).toHaveCount(0)
})

test('Today on an empty home says how to start a follow', async ({ page }) => {
  await page.goto('/#page=research&pane=FollowToday')
  await expect(page.getByText('Nothing is followed yet.')).toBeVisible()
  await expect(page.getByText('alpha follow start --test <run id>')).toBeVisible()
  await expect(page.getByText('alpha results list')).toBeVisible()
  await expect(page.locator('.follow-card')).toHaveCount(0)
})
