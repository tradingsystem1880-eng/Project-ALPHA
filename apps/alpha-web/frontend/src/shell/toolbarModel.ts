// Toolbar and title bar (spec 2026-09-01 §4.2 items 1 and 3; artboard 1-Terminal). The timeframe
// buttons are the classic five; only what the data house actually serves is enabled, and a
// disabled button says why. The title bar reads the profile and the active document — the
// chart's symbol and timeframe spelled the artboard way (`[BTCUSDT,D1]`), any other document's
// own title — never a symbol the browser made up.

import { displaySymbol } from '../panels/marketWatchModel'
import type { Profile } from '../state/settings'
import { profile as manifest } from './profiles'

export const TIMEFRAMES = ['M15', 'H1', 'H4', 'D1', 'W1'] as const
export type TimeframeLabel = (typeof TIMEFRAMES)[number]

export interface TimeframeButton {
  label: TimeframeLabel
  disabled: boolean
  reason: string | null
}

/** Today the candles projection is daily only; the others stay visible but honest. */
export function timeframeButtons(available: readonly TimeframeLabel[]): TimeframeButton[] {
  return TIMEFRAMES.map((label) => ({
    label,
    disabled: !available.includes(label),
    reason: available.includes(label) ? null : 'daily data only',
  }))
}

export interface ActiveContext {
  symbol: string | null
  timeframe: TimeframeLabel
}

/**
 * `ALPHA Terminal — Crypto — [BTCUSDT,D1]` for the chart; `— [<document title>]` for any other
 * document; no bracket when nothing is open or the chart has no symbol.
 */
export function windowTitle(
  profileId: Profile,
  active: ActiveContext | null,
  documentTitle: string | null = null,
): string {
  const base = `ALPHA Terminal — ${manifest(profileId).label}`
  if (documentTitle) return `${base} — [${documentTitle}]`
  if (!active || !active.symbol) return base
  return `${base} — [${displaySymbol(active.symbol)},${active.timeframe}]`
}

/** The venue the profile pulls from, capitalised for the chrome; null for equities. */
export function venueLabel(profileId: Profile): string | null {
  const venue = manifest(profileId).defaultVenue
  return venue ? venue.charAt(0).toUpperCase() + venue.slice(1) : null
}

/** The document header line for the chart: `BTCUSDT,D1 · Binance · 2019-01-01 → latest`. */
export function chartHeader(
  symbol: string | null,
  venue: string | null,
  start: string | null,
  end: string | null,
): string {
  if (!symbol) return 'No symbol'
  const parts = [`${displaySymbol(symbol)},D1`, venue, `${start ?? 'start'} → ${end ?? 'latest'}`]
  return parts.filter((part): part is string => part !== null).join(' · ')
}
