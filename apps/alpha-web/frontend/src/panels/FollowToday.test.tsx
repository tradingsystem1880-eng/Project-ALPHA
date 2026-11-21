import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { FollowRow, FollowShow, FollowToday as Today } from '../api/types'
import { FollowTodayView, type FollowTodayViewProps } from './FollowToday'

function row(id: string, group: string, extra: Partial<FollowRow> = {}): FollowRow {
  return {
    follow_id: id, group, name: `Idea ${id}`, asset: 'AAA', decision: 'no signal', entry_kind: 'bar', as_of_text: 'as of the close of 2026-11-19; the newest session',
    behind: false, kind: 'rule_test', card_id: '', calendar: 'XNYS', session_date: '2026-11-19', sessions_ago: 0, started_at: '2026-11-09T08:00:00+00:00',
    readings: { 'fast average price': 101.2, 'slow average price': 99.8 }, exits: [], study_labels: [], paper: { open: false, units: 0, entry_price: null, equity: 10000, equity_pct: 0 }, ...extra,
  }
}

const data: Today = {
  as_of: '2026-11-20T01:00:00+00:00', paper: true, followed: 5, behind: 1,
  markets: [{ calendar: 'XNYS', newest_closed_session: '2026-11-19' }],
  groups: [
    { key: 'new_signal', title: 'NEW SIGNAL', count: 1 }, { key: 'open_position', title: 'OPEN PAPER POSITION', count: 1 },
    { key: 'nothing_today', title: 'NOTHING TODAY', count: 0 }, { key: 'late_or_missed', title: 'LATE OR MISSED', count: 2 }, { key: 'waiting', title: 'WAITING', count: 1 },
  ],
  rows: [
    row('a1', 'new_signal', { decision: 'would enter at the next open' }),
    row('b2', 'open_position', { asset: 'BBB', decision: 'holding', paper: { open: true, units: 12.5, entry_price: 100, equity: 10150, equity_pct: 1.5 } }),
    row('c3', 'late_or_missed', { behind: true, sessions_ago: 2, session_date: '2026-11-17', paper: { open: false, equity_pct: -0.4 } }),
    row('d4', 'late_or_missed', { entry_kind: 'late', decision: 'late: the bar of this session was not stored when it was due. No decision.' }),
    row('e5', 'waiting', { session_date: null, sessions_ago: null, readings: {}, decision: 'waiting for its first new bar' }),
  ],
  notice: 'Paper only. Forward use; not research. Not advice.',
}

const show: FollowShow = {
  record: {
    follow_id: 'b2', kind: 'rule_test', source_id: 'b'.repeat(16), assets: ['BBB'], card_id: '', paper_account_percent: 10, started_at: '2026-11-09T08:00:00Z',
    version: 1, spec_sha256: 'f'.repeat(64), supersedes: '',
  },
  state: 'active', entries: { bar: 3, start: 1 }, head: 'h'.repeat(64), reading: 'open paper position', long_at_start: false, waiting_for_first_bar: false, stop_reason: '',
  recent: [
    { session: '2026-11-17', kind: 'bar', words: 'holding', fills: [], readings: {}, equity_pct: 0.5, replay_agrees: true },
    { session: '2026-11-18', kind: 'bar', words: 'holding', fills: [], readings: {}, equity_pct: 1.2, replay_agrees: true },
    { session: '2026-11-19', kind: 'bar', words: 'holding', fills: [], readings: {}, equity_pct: -1.5, replay_agrees: true },
  ],
  paper: { start: 10000, equity: 9850, equity_pct: -1.5 }, replay: { agrees: true, checked: 3, differences: [] },
}

function render(overrides: Partial<FollowTodayViewProps> = {}): string {
  return renderToStaticMarkup(
    <FollowTodayView data={data} error={null} loading={false} selected={null} detail={null} detailError={null} detailLoading={false}
      onSelect={() => undefined} onRefresh={() => undefined} onOpenChart={() => undefined} {...overrides} />,
  )
}

describe('Today screen', () => {
  it('shows the exits of a setup follow in plain words', () => {
    const exits = ['Stop-loss: 5 %', 'Profit target: 10 %', 'Time limit: 3 trading days']
    const html = render({ data: { ...data, rows: [row('s1', 'open_position', { kind: 'setup_trade', exits })] } })
    expect(html).toContain('Exits: Stop-loss: 5 %; Profit target: 10 %; Time limit: 3 trading days')
    expect(html).not.toContain('fast_sma')
  })
  it('has the header, the as-of time, the closed session, the behind count and the fixed line', () => {
    const html = render()
    expect(html).toContain('Followed on paper')
    expect(html).toContain('20 Nov 2026, 01:00 UTC')
    expect(html).toContain('Newest closed session: XNYS 2026-11-19')
    expect(html).toContain('1 of 5 behind')
    expect(html).toContain('Paper only. Forward use; not research. Not advice.')
  })

  it('shows the groups in order with their counts', () => {
    const html = render()
    const at = (title: string) => html.indexOf(`${title} (`)
    expect(at('NEW SIGNAL')).toBeGreaterThan(-1)
    expect(at('NEW SIGNAL')).toBeLessThan(at('OPEN PAPER POSITION'))
    expect(at('OPEN PAPER POSITION')).toBeLessThan(at('NOTHING TODAY'))
    expect(at('NOTHING TODAY')).toBeLessThan(at('LATE OR MISSED'))
    expect(at('LATE OR MISSED')).toBeLessThan(at('WAITING'))
    expect(html).toContain('LATE OR MISSED (2)')
    expect(html).toContain('NEW SIGNAL (1)')
  })

  it('collapses an empty group to one muted line and draws no card for it', () => {
    const html = render()
    expect(html).toContain('NOTHING TODAY (0)')
    expect(html.match(/class="muted follow-group-empty"/g)).toHaveLength(1)
    expect(html.match(/class="follow-card"/g)).toHaveLength(5)
  })

  it('puts the idea name, asset, decision, readings, paper figures and session on each card', () => {
    const html = render()
    expect(html).toContain('Idea a1')
    expect(html).toContain('would enter at the next open')
    expect(html).toContain('fast average price')
    expect(html).toContain('101.20')
    expect(html).toContain('Paper position open: 12.5 units from 100.00')
    expect(html).toContain('+1.50%')
    expect(html).toContain('Session 2026-11-17, 2 sessions ago')
    expect(html).toContain('No session recorded yet')
  })

  it('marks a behind or late card with an icon and words, and only those', () => {
    const html = render()
    expect(html.match(/class="follow-marker"/g)).toHaveLength(2)
    expect(html).toContain('Behind: 2 sessions without an entry')
    expect(html).toContain('Late: the bar was not stored when due')
    expect(html).toMatch(/data-id="c3"[^>]*data-flag="true"/)
  })

  it('shows direction by mark and attribute, never colour alone', () => {
    const html = render()
    expect(html).toContain('▲')
    expect(html).toContain('▼')
    expect(html).toContain('data-dir="up"')
    expect(html).toContain('data-dir="down"')
  })

  it('reaches every card by keyboard and says which one is open', () => {
    const html = render({ selected: 'b2', detail: show })
    expect(html.match(/<button[^>]*class="follow-card"/g)).toHaveLength(5)
    expect(html).toMatch(/data-id="b2"[^>]*aria-pressed="true"/)
    expect(html).toMatch(/data-id="a1"[^>]*aria-pressed="false"/)
  })

  it('opens the detail area for the selected card', () => {
    const html = render({ selected: 'b2', detail: show })
    expect(html).toContain('Paper equity path')
    expect(html).toContain('class="follow-chart"')
    expect(html).toContain('follow-zero')
    expect(html).toContain('Last entries')
    expect(html.match(/data-entry="/g)).toHaveLength(3)
    expect(html).toContain('Replay check: agrees (3 sessions compared)')
    expect(html).toContain('What is followed')
    expect(html).toContain('rule test bbbbbbbbbbbbbbbb')
    expect(html).toContain('10% of a paper account')
    expect(html).toContain('Open the chart for BBB')
  })

  it('gives the detail a text alternative with the numbers', () => {
    const html = render({ selected: 'b2', detail: show })
    expect(html).toContain('role="img"')
    expect(html).toContain('0.50%')
  })

  it('shows no detail until a card is picked, and plain words while it loads or fails', () => {
    expect(render()).not.toContain('Paper equity path')
    expect(render({ selected: 'b2', detailLoading: true })).toContain('Loading this follow')
    const failed = render({ selected: 'b2', detailError: 'Unknown follow id' })
    expect(failed).toContain('role="alert"')
    expect(failed).toContain('Unknown follow id')
  })

  it('says how to start a follow when there are none', () => {
    const html = render({ data: { ...data, followed: 0, behind: 0, rows: [], groups: [], markets: [] } })
    expect(html).toContain('alpha follow start --test &lt;run id&gt;')
    expect(html).toContain('alpha results list')
    expect(html).toContain('Nothing is followed yet.')
    expect(html).not.toContain('follow-card')
  })

  it('shows plain-word loading and error states', () => {
    expect(render({ data: null, loading: true })).toContain('Loading the followed ideas')
    const error = render({ data: null, error: 'alpha follow today timed out' })
    expect(error).toContain('role="alert"')
    expect(error).toContain('alpha follow today timed out')
    expect(error).not.toContain('Nothing is followed yet.')
  })

  it('has no order buttons, no advice and no profit words', () => {
    const html = render({ selected: 'b2', detail: show })
    const buttons = [...html.matchAll(/<button[\s\S]*?<\/button>/g)].map(m => m[0]).join(' ')
    expect(buttons).not.toMatch(/\b(buy|sell|order|trade)\b/i)
    expect(html).not.toMatch(/profit|should|recommend/i)
  })

  it('never shows NaN or undefined', () => {
    const html = render({ data: { ...data, rows: [row('q1', 'late_or_missed', { entry_kind: 'broken', paper: {}, readings: {}, session_date: null, sessions_ago: null, calendar: null })] } })
    expect(html).not.toMatch(/NaN|undefined/)
    expect(html).toContain('Journal cannot be read')
  })
})
