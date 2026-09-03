// Market Watch rows (spec 2026-09-01 §4.2 item 4): the profile's starter watchlist first, then
// every stored pair of the same symbol style, de-duplicated. Last and daily % come from the
// candles projection; a missing or non-finite price reads `—` (never `0.00`), because a number
// that was not observed must not look like one that was.

import type { Candle } from '../api/types'
import type { Profile } from '../state/settings'
import { dockOf } from '../shell/documents'
import { profile as manifest, symbolFitsProfile } from '../shell/profiles'
import { fmtUtcDate } from '../util/format'

export type WatchTone = 'up' | 'down' | 'flat' | 'none'

export interface WatchRow {
  symbol: string
  last: string
  change: string
  tone: WatchTone
  /** UTC date of the last stored bar the price comes from; null when there is none. */
  asOf: string | null
}

export const MARKET_WATCH_TABS = dockOf('MarketWatch').tabs

export function watchSymbols(profileId: Profile, stored: readonly string[]): string[] {
  const { starterWatchlist } = manifest(profileId)
  const seen = new Set<string>()
  const rows: string[] = []
  for (const symbol of [...starterWatchlist, ...stored]) {
    if (seen.has(symbol) || !symbolFitsProfile(profileId, symbol)) continue
    seen.add(symbol)
    rows.push(symbol)
  }
  return rows
}

function priceText(value: number): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: value >= 100 ? 2 : 6 })
}

/** One row from the last two daily bars; anything missing is shown as missing. */
export function watchRow(symbol: string, bars: readonly Candle[] | null | undefined): WatchRow {
  const none: WatchRow = { symbol, last: '—', change: '—', tone: 'none', asOf: null }
  if (!bars || bars.length === 0) return none
  const lastBar = bars[bars.length - 1]
  const last = lastBar.c
  if (!Number.isFinite(last)) return none
  const asOf = fmtUtcDate(lastBar.t)
  const previous = bars.length > 1 ? bars[bars.length - 2].c : Number.NaN
  if (!Number.isFinite(previous) || previous === 0) {
    return { symbol, last: priceText(last), change: '—', tone: 'none', asOf }
  }
  const pct = (last / previous - 1) * 100
  const tone: WatchTone = pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat'
  const sign = pct > 0 ? '+' : ''
  return { symbol, last: priceText(last), change: `${sign}${pct.toFixed(2)}%`, tone, asOf }
}

export function watchRows(
  profileId: Profile,
  stored: readonly string[],
  quotes: Readonly<Record<string, readonly Candle[] | null | undefined>>,
): WatchRow[] {
  return watchSymbols(profileId, stored).map((symbol) => watchRow(symbol, quotes[symbol]))
}
