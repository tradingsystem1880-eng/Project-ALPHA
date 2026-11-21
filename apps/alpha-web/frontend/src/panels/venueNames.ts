// Display names for data sources and venues. A leaf module (no shell imports) so models can share it.

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

/**
 * `ccxt:binance` → `Binance`; a bare provider id → its display name; an unlisted id → as given.
 * Legacy datasets whose provenance says `unknown` get no venue (rendered `—`), never a name.
 */
export function venueLabel(source: string | null | undefined): string | null {
  if (!source) return null
  const id = source.includes(':') ? source.slice(source.indexOf(':') + 1) : source
  const key = id.trim().toLowerCase()
  if (!key || key === 'unknown') return null
  return VENUE_NAMES[key] ?? key.charAt(0).toUpperCase() + key.slice(1)
}
