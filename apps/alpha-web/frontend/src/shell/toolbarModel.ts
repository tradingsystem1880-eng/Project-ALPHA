// Toolbar and title bar (spec 2026-09-01 §4.2 items 1 and 3). The timeframe buttons are the
// classic five; only what the data house actually serves is enabled, and a disabled button says
// why. The title bar reads the profile and the active document's context — never a symbol the
// browser made up.

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
  /** Venue label (e.g. Binance) or null where the source is not venue-qualified. */
  venue: string | null
  timeframe: TimeframeLabel
}

/** `ALPHA Terminal — Crypto — [BTC/USDT · Binance · D1]`; no bracket when nothing is open. */
export function windowTitle(profileId: Profile, active: ActiveContext | null): string {
  const base = `ALPHA Terminal — ${manifest(profileId).label}`
  if (!active || !active.symbol) return base
  const parts = [active.symbol, active.venue, active.timeframe].filter(
    (part): part is string => part !== null,
  )
  return `${base} — [${parts.join(' · ')}]`
}

/** The venue the profile pulls from, capitalised for the title bar; null for equities. */
export function venueLabel(profileId: Profile): string | null {
  const venue = manifest(profileId).defaultVenue
  return venue ? venue.charAt(0).toUpperCase() + venue.slice(1) : null
}
