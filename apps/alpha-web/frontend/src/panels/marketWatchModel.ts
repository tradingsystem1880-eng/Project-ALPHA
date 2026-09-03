// Market Watch rows (spec 2026-09-01 §4.2 item 4): the profile's starter watchlist first, then
// every stored pair of the same symbol style, de-duplicated. Each row is one stored pair on one
// venue — BTC/USDT on Binance and BTC/USD on Coinbase are two rows, never merged (CLAUDE.md crypto
// rule) — so the venue and the date of the bar a price comes from are part of the row. A missing
// or non-finite price reads `—` (never `0.00`), because a number that was not observed must not
// look like one that was.

import type { Candle } from '../api/types'
import type { Profile } from '../state/settings'
import { dockOf } from '../shell/documents'
import { profile as manifest, symbolFitsProfile } from '../shell/profiles'
import { fmtUtcDate } from '../util/format'

export type WatchTone = 'up' | 'down' | 'flat' | 'none'

export interface WatchQuote {
  bars: readonly Candle[]
  provenance?: { source?: string | null } | null
}

export interface WatchRow {
  /** The stored symbol as the store names it (`BTC/USDT`); what the linked context receives. */
  symbol: string
  /** The artboard's spelling (`BTCUSDT`). */
  label: string
  /** Venue/provider the stored bars came from (`Binance`, `Coinbase`, `Tiingo`); null when unknown. */
  venue: string | null
  last: string
  change: string
  tone: WatchTone
  /** UTC date of the last stored bar the price comes from; null when there is none. */
  asOf: string | null
  /** Compact age for the narrow dock: `live`, `0d`…`65d`, or null with no bar. */
  age: string | null
  /** The last bar is older than `STALE_AFTER_DAYS`; the price is history, not a quote. */
  stale: boolean
}

export const MARKET_WATCH_TABS = dockOf('MarketWatch').tabs
export const STALE_AFTER_DAYS = 2

const VENUE_NAMES: Readonly<Record<string, string>> = {
  binance: 'Binance',
  bybit: 'Bybit',
  coinbase: 'Coinbase',
  kraken: 'Kraken',
  tiingo: 'Tiingo',
  yfinance: 'Yahoo',
  stooq: 'Stooq',
  quantpad: 'QuantPad',
  ccxt: 'CCXT',
  coingecko: 'CoinGecko',
  geckoterminal: 'GeckoTerminal',
  coinmetrics: 'Coin Metrics',
}

/** `ccxt:binance` → `Binance`; a bare provider id → its display name; unknown → as given. */
export function venueLabel(source: string | null | undefined): string | null {
  if (!source) return null
  const id = source.includes(':') ? source.slice(source.indexOf(':') + 1) : source
  const key = id.trim().toLowerCase()
  if (!key) return null
  return VENUE_NAMES[key] ?? key.charAt(0).toUpperCase() + key.slice(1)
}

export function displaySymbol(symbol: string): string {
  return symbol.replace('/', '')
}

/** `BTC/USDT` → `BTC`, `BTC-USD` → `BTC`, `AAPL` → `AAPL`. */
export function baseAsset(symbol: string): string {
  return symbol.split(/[/-]/)[0]
}

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

export function isStale(barTs: number, nowMs: number): boolean {
  return nowMs - barTs * 1000 > STALE_AFTER_DAYS * 86_400_000
}

/** Whole days between the bar and now, floored at zero: `65d`. */
export function ageText(barTs: number, nowMs: number): string {
  return `${Math.max(0, Math.floor((nowMs - barTs * 1000) / 86_400_000))}d`
}

/** One row from the last two daily bars; anything missing is shown as missing. */
export function watchRow(
  symbol: string,
  quote: WatchQuote | null | undefined,
  nowMs: number,
): WatchRow {
  const label = displaySymbol(symbol)
  const none: WatchRow = {
    symbol,
    label,
    venue: venueLabel(quote?.provenance?.source),
    last: '—',
    change: '—',
    tone: 'none',
    asOf: null,
    age: null,
    stale: false,
  }
  const bars = quote?.bars
  if (!bars || bars.length === 0) return none
  const lastBar = bars[bars.length - 1]
  const last = lastBar.c
  if (!Number.isFinite(last) || !Number.isFinite(lastBar.t)) return none
  const dated = { ...none, asOf: fmtUtcDate(lastBar.t), age: ageText(lastBar.t, nowMs), stale: isStale(lastBar.t, nowMs) }
  const previous = bars.length > 1 ? bars[bars.length - 2].c : Number.NaN
  if (!Number.isFinite(previous) || previous === 0) {
    return { ...dated, last: priceText(last) }
  }
  const pct = (last / previous - 1) * 100
  const tone: WatchTone = pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat'
  const sign = pct > 0 ? '+' : ''
  return { ...dated, last: priceText(last), change: `${sign}${pct.toFixed(2)}%`, tone }
}

export function watchRows(
  profileId: Profile,
  stored: readonly string[],
  quotes: Readonly<Record<string, WatchQuote | null | undefined>>,
  nowMs: number,
): WatchRow[] {
  return watchSymbols(profileId, stored).map((symbol) => watchRow(symbol, quotes[symbol], nowMs))
}

/** Every row that quotes the same base asset as `symbol` (all venues and quote currencies). */
export function relatedRows(symbol: string, rows: readonly WatchRow[]): WatchRow[] {
  const base = baseAsset(symbol)
  return rows.filter((row) => baseAsset(row.symbol) === base)
}

export const TICKER_POLL_MS = 10_000

/** Public tickers are read only while the trader asked for them and can see them. */
export function shouldPoll(liveTicker: boolean, visibility: DocumentVisibilityState): boolean {
  return liveTicker && visibility === 'visible'
}

/** Venues the public ticker seam serves (`alpha data ticker --source ccxt --exchange …`). */
const TICKER_EXCHANGES: Readonly<Record<string, string>> = { Binance: 'binance', Coinbase: 'coinbase' }

/** The ccxt exchange id to quote a row from, or null when the row's venue has no public ticker. */
export function tickerExchange(row: Pick<WatchRow, 'venue' | 'symbol'>): string | null {
  if (!row.venue || !row.symbol.includes('/')) return null
  return TICKER_EXCHANGES[row.venue] ?? null
}

export interface LiveQuote {
  symbol: string
  exchange: string
  last: number
  ts: string
}

/**
 * Overlay a live quote on a stored row: the price becomes the venue's last trade, the Age
 * cell reads `live`, and the row is no longer stale. A quote for another symbol or venue, or
 * a non-finite price, changes nothing — the stored close stays, dated.
 */
export function applyTicker(row: WatchRow, quote: LiveQuote | null | undefined): WatchRow {
  if (!quote || quote.symbol !== row.symbol || quote.exchange !== tickerExchange(row)) return row
  if (!Number.isFinite(quote.last) || quote.last <= 0) return row
  return { ...row, last: priceText(quote.last), asOf: 'live', age: 'live', stale: false }
}

