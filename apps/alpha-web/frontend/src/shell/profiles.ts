// Market profiles (spec 2026-09-01 §4.1): two static, deep-frozen manifests that say which
// windows, docks, providers, defaults and vocabulary the terminal shows for a crypto or an
// equities trader. A profile is a display setting — it is never sent to the server, never a
// permission, and lists are filtered by the server's `market` field, never by symbol text.

import type { Profile } from '../state/settings'

export type WindowId =
  | 'chart'
  | 'report'
  | 'compare'
  | 'build'
  | 'research'
  | 'governance'
  | 'forecast'
  | 'ml-lab'
  | 'jobs'
  | 'paper'
  | 'options'
  | 'screener'
  | 'corporate-actions'
  | 'funding'
  | 'open-interest'
  | 'onchain'
  | 'dex'
  | 'crowding'

export type DockId = 'MarketWatch' | 'Navigator' | 'DataManager' | 'Toolbox'

export interface ProfileManifest {
  readonly id: Profile
  readonly label: string
  readonly windows: readonly WindowId[]
  readonly docks: readonly DockId[]
  /** Provider ids (alpha_cli.providers) this profile offers for data pulls, in menu order. */
  readonly providers: readonly string[]
  readonly defaultSource: string
  /** The ccxt venue for pulls; null where the default source is not a venue-qualified one. */
  readonly defaultVenue: string | null
  readonly defaultSymbol: string
  readonly symbolStyle: 'pair' | 'ticker'
  readonly starterWatchlist: readonly string[]
  readonly paperVenues: readonly string[]
  readonly glossaryTags: readonly string[]
}

/** Windows that belong to neither market and appear in both profiles. */
export const MARKET_NEUTRAL_WINDOWS: readonly WindowId[] = Object.freeze([
  'chart',
  'report',
  'compare',
  'build',
  'research',
  'governance',
  'forecast',
  'ml-lab',
  'jobs',
  'paper',
])

const DOCKS: readonly DockId[] = Object.freeze(['MarketWatch', 'Navigator', 'DataManager', 'Toolbox'])

function freeze<T extends object>(value: T): T {
  for (const child of Object.values(value)) {
    if (child !== null && typeof child === 'object') freeze(child as object)
  }
  return Object.freeze(value)
}

export const PROFILES: Readonly<Record<Profile, ProfileManifest>> = freeze({
  crypto: {
    id: 'crypto',
    label: 'Crypto',
    windows: [...MARKET_NEUTRAL_WINDOWS, 'funding', 'open-interest', 'onchain', 'dex', 'crowding'],
    docks: DOCKS,
    providers: ['ccxt', 'binance', 'bybit', 'coingecko', 'geckoterminal', 'coinmetrics'],
    defaultSource: 'ccxt',
    defaultVenue: 'binance',
    defaultSymbol: 'XRP/USDT',
    symbolStyle: 'pair',
    starterWatchlist: ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT'],
    paperVenues: ['binance-sandbox'],
    glossaryTags: ['crypto'],
  },
  equities: {
    id: 'equities',
    label: 'Equities',
    windows: [...MARKET_NEUTRAL_WINDOWS, 'options', 'screener', 'corporate-actions'],
    docks: DOCKS,
    providers: ['tiingo', 'yfinance', 'stooq', 'quantpad'],
    defaultSource: 'tiingo',
    defaultVenue: null,
    defaultSymbol: 'AAPL',
    symbolStyle: 'ticker',
    starterWatchlist: ['SPY', 'AAPL'],
    paperVenues: ['ibkr'],
    glossaryTags: ['equities'],
  },
})

export function profile(id: Profile): ProfileManifest {
  const found = PROFILES[id]
  if (!found) throw new Error(`unknown profile ${String(id)}`)
  return found
}

/** Whether a profile shows a window; market-neutral windows are always shown. */
export function showsWindow(id: Profile, window: WindowId): boolean {
  return profile(id).windows.includes(window)
}

/** Stored symbols carry no server `market`; a profile's symbol style is the only honest fit test. */
export function symbolFitsProfile(id: Profile, symbol: string): boolean {
  return profile(id).symbolStyle === 'pair' ? symbol.includes('/') : !symbol.includes('/')
}
