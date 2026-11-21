import { describe, expect, it } from 'vitest'
import type { FollowRow, FollowShow, FollowToday } from '../api/types'
import {
  GROUP_ORDER, behindLine, closedSessionLine, detailFacts, equityGeometry, equityPoints, groupSections, kindWords,
  barsBehindLine, paperLine, rankMark, readingPairs, replayLine, rowMarker, sessionLine, tableRows,
} from './followTodayModel'

function row(id: string, group: string, extra: Partial<FollowRow> = {}): FollowRow {
  return {
    follow_id: id, group, name: `Idea ${id}`, asset: 'AAA', decision: 'no signal', entry_kind: 'bar', as_of_text: 'as of the close of 2026-11-19; the newest session',
    behind: false, kind: 'rule_test', card_id: '', calendar: 'XNYS', session_date: '2026-11-19', sessions_ago: 0, started_at: '2026-11-09T08:00:00+00:00',
    readings: { fast_sma: 101.2, slow_sma: 99.8 }, paper: { open: false, units: 0, entry_price: null, equity: 10000, equity_pct: 0 }, ...extra,
  }
}

const today: FollowToday = {
  as_of: '2026-11-20T01:00:00+00:00', paper: true, followed: 5, behind: 1,
  markets: [{ calendar: '', newest_closed_session: '2026-11-19' }, { calendar: 'XNYS', newest_closed_session: '2026-11-19' }],
  groups: [
    { key: 'new_signal', title: 'NEW SIGNAL', count: 1 }, { key: 'open_position', title: 'OPEN PAPER POSITION', count: 1 },
    { key: 'nothing_today', title: 'NOTHING TODAY', count: 0 }, { key: 'late_or_missed', title: 'LATE OR MISSED', count: 2 },
    { key: 'waiting', title: 'WAITING', count: 1 },
  ],
  rows: [row('a1', 'new_signal'), row('b2', 'open_position'), row('c3', 'late_or_missed', { behind: true, sessions_ago: 2 }), row('d4', 'late_or_missed', { entry_kind: 'late' }), row('e5', 'waiting', { session_date: null, sessions_ago: null })],
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
    { session: '2026-11-18', kind: 'late', words: 'late: the bar was not stored', fills: [], readings: {}, equity_pct: null, replay_agrees: null },
    { session: '2026-11-19', kind: 'bar', words: 'holding', fills: [], readings: {}, equity_pct: -1.5, replay_agrees: true },
  ],
  paper: { start: 10000, equity: 9850, equity_pct: -1.5 }, replay: { agrees: true, checked: 3, differences: [] },
}

describe('Today model', () => {
  it('orders the four groups, then waiting, with counts from the rows', () => {
    expect(GROUP_ORDER).toEqual(['new_signal', 'open_position', 'nothing_today', 'late_or_missed', 'waiting'])
    const sections = groupSections(today)
    expect(sections.map(s => s.key)).toEqual([...GROUP_ORDER])
    expect(sections.map(s => s.rows.length)).toEqual([1, 1, 0, 2, 1])
    expect(sections.map(s => s.title)).toEqual(['NEW SIGNAL', 'OPEN PAPER POSITION', 'NOTHING TODAY', 'LATE OR MISSED', 'WAITING'])
  })

  it('keeps a row whose group is unknown out of the way, never dropped', () => {
    const sections = groupSections({ ...today, rows: [row('z9', 'something_new')] })
    expect(sections.at(-1)?.key).toBe('other')
    expect(sections.at(-1)?.rows).toHaveLength(1)
    expect(groupSections({ ...today, rows: [] }).every(s => s.rows.length === 0)).toBe(true)
  })

  it('writes the header lines from the command facts', () => {
    expect(behindLine(today)).toBe('1 of 5 behind')
    expect(closedSessionLine(today)).toBe('Newest closed session: markets that trade every day 2026-11-19; XNYS 2026-11-19')
    expect(closedSessionLine({ ...today, markets: [] })).toBe('Newest closed session: none')
  })

  it('marks a behind or late row in words, with an icon', () => {
    expect(rowMarker(today.rows[2])).toEqual({ icon: '◷', words: 'Behind: 2 sessions without an entry' })
    expect(rowMarker(row('x', 'late_or_missed', { behind: true, sessions_ago: 1 }))?.words).toBe('Behind: 1 session without an entry')
    expect(rowMarker(today.rows[3])?.words).toBe('Late: the bar was not stored when due')
    expect(rowMarker(row('x', 'late_or_missed', { entry_kind: 'missed' }))?.words).toBe('Missed: the rule had a signal that no order could follow')
    expect(rowMarker(row('x', 'late_or_missed', { entry_kind: 'broken' }))?.words).toBe('Journal cannot be read')
    expect(rowMarker(today.rows[0])).toBeNull()
  })

  it('shows readings as label: value pairs', () => {
    expect(readingPairs(today.rows[0])).toEqual([['fast_sma', '101.20'], ['slow_sma', '99.80']])
    expect(readingPairs(row('x', 'waiting', { readings: {} }))).toEqual([])
  })

  it('says the paper position and the change since the start', () => {
    expect(paperLine(row('x', 'open_position', { paper: { open: true, units: 12.5, entry_price: 100, equity: 10150, equity_pct: 1.5 } }))).toEqual({
      position: 'Paper position open: 12.5 units from 100.00', change: '+1.50%', dir: 'up',
    })
    expect(paperLine(today.rows[0])).toEqual({ position: 'Paper account flat', change: '0.00%', dir: 'flat' })
    expect(paperLine(row('x', 'late_or_missed', { paper: {} })).change).toBe('—')
    expect(paperLine(row('x', 'late_or_missed', { paper: { open: false, equity_pct: -0.4 } })).dir).toBe('down')
  })

  it('says the session date and how many sessions ago', () => {
    expect(sessionLine(today.rows[0])).toBe('Session 2026-11-19, the newest session')
    expect(sessionLine(today.rows[2])).toBe('Session 2026-11-19, 2 sessions ago')
    expect(sessionLine(row('x', 'late_or_missed', { sessions_ago: 1 }))).toBe('Session 2026-11-19, 1 session ago')
    expect(sessionLine(today.rows[4])).toBe('No session recorded yet')
  })

  it('draws the equity path from the entries that carry a value', () => {
    const points = equityPoints(show)
    expect(points).toEqual([{ session: '2026-11-17', pct: 0.5 }, { session: '2026-11-19', pct: -1.5 }])
    const geo = equityGeometry(points, 400, 120)
    expect(geo.points.split(' ')).toHaveLength(2)
    expect(geo.zeroY).toBeGreaterThan(0)
    expect(geo.zeroY).toBeLessThan(120)
    expect(geo.labels.map(l => l.text)).toEqual(['2026-11-17', '2026-11-19'])
    expect(equityGeometry([], 400, 120).points).toBe('')
  })

  it('keeps the zero line inside a path that never leaves one side', () => {
    const geo = equityGeometry([{ session: 'a', pct: 1 }, { session: 'b', pct: 2 }], 400, 120)
    expect(geo.zeroY).toBeLessThanOrEqual(120)
    expect(geo.zeroY).toBeGreaterThanOrEqual(0)
    expect(equityGeometry([{ session: 'a', pct: 0 }], 400, 120).points).toMatch(/^\d/)
  })

  it('lists up to ten entries, newest first', () => {
    const many = { ...show, recent: Array.from({ length: 12 }, (_, i) => ({ ...show.recent[0], session: `2026-11-${String(i + 1).padStart(2, '0')}` })) }
    const rows = tableRows(many)
    expect(rows).toHaveLength(10)
    expect(rows[0].session).toBe('2026-11-12')
    expect(tableRows(show)[1]).toMatchObject({ kind: 'late', equity: '—' })
    expect(tableRows(show)[0]).toMatchObject({ session: '2026-11-19', equity: '-1.50%', words: 'holding' })
  })

  it('writes the replay check line', () => {
    expect(replayLine(show)).toBe('Replay check: agrees (3 sessions compared)')
    expect(replayLine({ ...show, replay: { agrees: false, checked: 3, differences: [{ session: '2026-11-18', what: 'fill', detail: 'x' }, { session: '2026-11-19', what: 'fill', detail: 'y' }, { session: '2026-11-18', what: 'book', detail: 'z' }] } }))
      .toBe('Replay check: does not agree: sessions 2026-11-18, 2026-11-19')
    expect(replayLine({ ...show, replay: null })).toBe('Replay check: none yet')
  })

  it('lists the frozen facts without computing anything', () => {
    const facts = Object.fromEntries(detailFacts(show))
    expect(facts['What is followed']).toBe('rule test bbbbbbbbbbbbbbbb')
    expect(facts['Followed since']).toContain('9 Nov 2026')
    expect(facts['Paper size']).toBe('10% of a paper account')
    expect(facts['Version']).toBe('1')
    expect(facts['Assets']).toBe('BBB')
    expect(kindWords('setup_find')).toBe('setup find')
  })

  it('marks direction with a glyph', () => {
    expect(rankMark('up')).toBe('▲')
    expect(rankMark('down')).toBe('▼')
    expect(rankMark('flat')).toBe('')
  })
})

describe('stored bars behind the newest closed session', () => {
  const waiting = row('e5', 'waiting', { session_date: null, sessions_ago: null, calendar: 'XNYS' })
  const markets = [{ calendar: 'XNYS', newest_closed_session: '2026-11-20' }]

  it('says plainly that the stored bars end before the newest closed session', () => {
    expect(barsBehindLine(waiting, markets, { AAA: '2026-11-19' }))
      .toBe('Stored bars end 2026-11-19; the newest closed session is 2026-11-20: bars are one session behind.')
    expect(barsBehindLine(waiting, markets, { AAA: '2026-11-16' }))
      .toBe('Stored bars end 2026-11-16; the newest closed session is 2026-11-20: bars are behind.')
  })

  it('says nothing when the bars are current, unknown, or the follow is not waiting', () => {
    expect(barsBehindLine(waiting, markets, { AAA: '2026-11-20' })).toBeNull()
    expect(barsBehindLine(waiting, markets, {})).toBeNull()
    expect(barsBehindLine({ ...waiting, group: 'new_signal' }, markets, { AAA: '2026-11-19' })).toBeNull()
  })
})
