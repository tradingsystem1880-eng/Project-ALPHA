// Pure helpers for the Today screen. The server computes every decision and number
// (`alpha follow today|show --json`); these functions only arrange and word what it sends.

import type { FollowRow, FollowShow, FollowToday } from '../api/types'
import { formatTime } from '../util/formatTime'
import { fmtPct } from './marketModel'

export const GROUP_ORDER = ['new_signal', 'open_position', 'nothing_today', 'late_or_missed', 'waiting'] as const
export const NOTICE = 'Paper only. Forward use; not research. Not advice.'
export const TABLE_ROWS = 10
const TITLES: Record<string, string> = {
  new_signal: 'NEW SIGNAL', open_position: 'OPEN PAPER POSITION', nothing_today: 'NOTHING TODAY', late_or_missed: 'LATE OR MISSED', waiting: 'WAITING',
}

export type Direction = 'up' | 'down' | 'flat'
export interface Section { key: string; title: string; rows: FollowRow[] }
export interface Marker { icon: string; words: string }
export interface EquityPoint { session: string; pct: number }
export interface TableRow { session: string; kind: string; words: string; equity: string }

export const rankMark = (dir: Direction): string => (dir === 'up' ? '▲' : dir === 'down' ? '▼' : '')

/** The five groups in the fixed order, counted from the rows. A row in an unknown group is kept under `other`. */
export function groupSections(data: FollowToday): Section[] {
  const known = new Set<string>(GROUP_ORDER)
  const sections: Section[] = GROUP_ORDER.map(key => ({
    key, title: data.groups.find(group => group.key === key)?.title ?? TITLES[key], rows: data.rows.filter(row => row.group === key),
  }))
  const other = data.rows.filter(row => !known.has(row.group))
  return other.length ? [...sections, { key: 'other', title: 'OTHER', rows: other }] : sections
}

export const behindLine = (data: FollowToday): string => `${data.behind} of ${data.followed} behind`

export function closedSessionLine(data: FollowToday): string {
  if (!data.markets.length) return 'Newest closed session: none'
  const parts = data.markets.map(m => `${m.calendar === '' ? 'markets that trade every day' : m.calendar} ${m.newest_closed_session}`)
  return `Newest closed session: ${parts.join('; ')}`
}

/** Why a waiting follow waits, when the stored bars trail the newest closed session of its market; else null. */
export function barsBehindLine(row: FollowRow, markets: FollowToday['markets'], barsEnd: Readonly<Record<string, string>>): string | null {
  if (row.group !== 'waiting') return null
  const end = barsEnd[row.asset]
  const newest = markets.find(market => market.calendar === (row.calendar ?? ''))?.newest_closed_session
  if (!end || !newest || end >= newest) return null
  const days = (Date.parse(`${newest}T00:00:00Z`) - Date.parse(`${end}T00:00:00Z`)) / 86_400_000
  return `Stored bars end ${end}; the newest closed session is ${newest}: bars are ${days === 1 ? 'one session ' : ''}behind.`
}

const sessions = (n: number): string => `${n} session${n === 1 ? '' : 's'}`

/** A neutral marker: an icon plus words. Colour is never the only signal. */
export function rowMarker(row: FollowRow): Marker | null {
  if (row.entry_kind === 'broken') return { icon: '!', words: 'Journal cannot be read' }
  if (row.behind) {
    const gap = row.sessions_ago
    return { icon: '◷', words: gap ? `Behind: ${sessions(gap)} without an entry` : 'Behind: no entry for the newest closed session' }
  }
  if (row.entry_kind === 'late') return { icon: '◷', words: 'Late: the bar was not stored when due' }
  if (row.entry_kind === 'missed') return { icon: '◷', words: 'Missed: the rule had a signal that no order could follow' }
  return null
}

export const readingPairs = (row: FollowRow): [string, string][] => Object.entries(row.readings).map(([label, value]) => [label, value.toFixed(2)])

export function paperLine(row: FollowRow): { position: string; change: string; dir: Direction } {
  const paper = row.paper
  const pct = paper.equity_pct
  const dir: Direction = pct === null || pct === undefined || Number(Math.abs(pct).toFixed(2)) === 0 ? 'flat' : pct > 0 ? 'up' : 'down'
  const position = paper.open === undefined || paper.open === null
    ? 'Paper account not recorded'
    : paper.open
      ? `Paper position open: ${Number((paper.units ?? 0).toPrecision(4))} units from ${(paper.entry_price ?? 0).toFixed(2)}`
      : 'Paper account flat'
  return { position, change: pct === null || pct === undefined ? '—' : fmtPct(pct), dir }
}

export function sessionLine(row: FollowRow): string {
  if (!row.session_date) return 'No session recorded yet'
  const ago = row.sessions_ago
  return `Session ${row.session_date}, ${ago === null || ago === undefined ? row.as_of_text : ago === 0 ? 'the newest session' : `${sessions(ago)} ago`}`
}

/** The percent-since-start values the journal entries carry, oldest first. Entries without a value are left out. */
export function equityPoints(show: FollowShow): EquityPoint[] {
  return show.recent.flatMap(entry => (typeof entry.equity_pct === 'number' ? [{ session: entry.session, pct: entry.equity_pct }] : []))
}

export interface Geometry {
  points: string; zeroY: number; labels: { text: string; x: number }[]
  ticks: { text: string; y: number }[]; dots: { x: number; y: number; session: string; pct: number }[]
}

/** SVG positions: x spaced by entry, y in percent with zero always inside the frame. */
export function equityGeometry(points: EquityPoint[], width: number, height: number, pad = 8): Geometry {
  if (!points.length) return { points: '', zeroY: height / 2, labels: [], ticks: [], dots: [] }
  const values = points.map(p => p.pct)
  const low = Math.min(0, ...values)
  const high = Math.max(0, ...values)
  const span = high - low || 2
  const top = high === low ? 1 : high
  const y = (pct: number) => pad + ((top - pct) / span) * (height - 2 * pad)
  const x = (index: number) => (points.length === 1 ? width / 2 : pad + (index / (points.length - 1)) * (width - 2 * pad))
  const dots = points.map((p, i) => ({ x: x(i), y: y(p.pct), session: p.session, pct: p.pct }))
  const tickValues = [...new Set([high === low ? 1 : high, 0, high === low ? -1 : low])]
  return {
    points: dots.map(d => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' '), zeroY: y(0),
    labels: points.map((p, i) => ({ text: p.session, x: x(i) })),
    ticks: tickValues.map(v => ({ text: v === 0 ? '0%' : fmtPct(v), y: y(v) })), dots,
  }
}

/** The newest entries first, at most ten. The command's own numbers; a missing value is a dash. */
export function tableRows(show: FollowShow): TableRow[] {
  return show.recent.slice(-TABLE_ROWS).reverse().map(entry => ({
    session: entry.session, kind: entry.kind, words: entry.words, equity: typeof entry.equity_pct === 'number' ? fmtPct(entry.equity_pct) : '—',
  }))
}

export function replayLine(show: FollowShow): string {
  const check = show.replay
  if (!check) return 'Replay check: none yet'
  if (check.agrees) return `Replay check: agrees (${sessions(check.checked)} compared)`
  return `Replay check: does not agree: sessions ${[...new Set(check.differences.map(d => d.session))].join(', ')}`
}

export const kindWords = (kind: string): string => kind.replace(/_/g, ' ')

function since(iso: string): string {
  try { return formatTime(iso) } catch { return iso }
}

export function detailFacts(show: FollowShow): [string, string][] {
  const r = show.record
  return [
    ['What is followed', `${kindWords(r.kind)} ${r.source_id}`], ['Assets', r.assets.join(', ')], ['Followed since', since(r.started_at)],
    ['Paper size', `${r.paper_account_percent}% of a paper account`], ['Version', String(r.version)],
    ['Idea card', r.card_id || 'none linked'], ['State', show.state],
  ]
}
