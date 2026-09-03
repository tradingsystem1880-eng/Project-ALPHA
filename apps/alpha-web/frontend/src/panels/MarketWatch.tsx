// Market Watch dock (spec 2026-09-01 §4.2 item 4): symbol · last · daily %, red/green, for the
// profile's watchlist and stored pairs. Prices are the last two daily bars of the candles
// projection; a symbol with no stored bars shows `—`. Clicking a row sets the linked symbol.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Candle } from '../api/types'
import { setLinked, useLinked } from '../context/linked'
import { useSettings } from '../state/settings'
import { MARKET_WATCH_TABS, watchRows, watchSymbols } from './marketWatchModel'

const RECENT_DAYS = 10

function recentStart(): string {
  return new Date(Date.now() - RECENT_DAYS * 86_400_000).toISOString().slice(0, 10)
}

export function MarketWatch() {
  const { profile } = useSettings()
  const linked = useLinked()
  const [tab, setTab] = useState<string>(MARKET_WATCH_TABS[0])
  const [stored, setStored] = useState<string[]>([])
  const [quotes, setQuotes] = useState<Record<string, Candle[] | null>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .symbols()
      .then((list) => live && setStored(list.symbols))
      .catch((cause) => live && setError(String(cause)))
    return () => {
      live = false
    }
  }, [])

  const symbolKey = watchSymbols(profile, stored).join(' ')
  useEffect(() => {
    let live = true
    const start = recentStart()
    for (const symbol of symbolKey.split(' ').filter(Boolean)) {
      api
        .candles(symbol, `?start=${start}`)
        .then((result) => live && setQuotes((current) => ({ ...current, [symbol]: result.bars })))
        .catch(() => live && setQuotes((current) => ({ ...current, [symbol]: null })))
    }
    return () => {
      live = false
    }
  }, [symbolKey])

  const rows = watchRows(profile, stored, quotes)
  return (
    <div className="dock-panel market-watch">
      <nav className="rd-tabs" role="tablist" aria-label="Market Watch tabs">
        {MARKET_WATCH_TABS.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={`rd-tab${tab === item ? ' active' : ''}`}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </nav>
      {error ? <p className="muted">{error}</p> : null}
      {tab === 'Symbols' ? (
        <table className="blotter market-watch-table" aria-label="Market Watch">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="num">Last</th>
              <th className="num">Daily %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.symbol}
                className={`watch-row tone-${row.tone}${linked.symbol === row.symbol ? ' active' : ''}`}
                aria-selected={linked.symbol === row.symbol}
                onClick={() => setLinked({ symbol: row.symbol })}
              >
                <td className="mono">{row.symbol}</td>
                <td className="num mono">{row.last}</td>
                <td className="num mono">{row.change}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : tab === 'Details' ? (
        <dl className="market-watch-details">
          <dt>Symbol</dt>
          <dd className="mono">{linked.symbol ?? '—'}</dd>
          <dt>Window</dt>
          <dd className="mono">{`${linked.start ?? 'start'} → ${linked.end ?? 'latest'}`}</dd>
          <dt>Snapshot</dt>
          <dd className="mono">{linked.snapshotId ?? '—'}</dd>
        </dl>
      ) : (
        <p className="muted">
          {stored.length} stored symbol{stored.length === 1 ? '' : 's'}; prices are the last two
          daily bars in the store, never a live feed.
        </p>
      )}
    </div>
  )
}
