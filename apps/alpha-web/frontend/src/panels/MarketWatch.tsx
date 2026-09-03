// Market Watch dock (spec 2026-09-01 §4.2 item 4): one row per stored pair on one venue —
// symbol · venue · last · daily % · age — red/green, for the profile's watchlist and stored pairs.
// Prices are the last two daily bars of the candles projection (`?tail=2`, so a pair whose
// history ends months ago still reads its last close) and the Age cell says which day that bar
// is from; a bar older than two days is dimmed as history. A symbol with no stored bars shows
// `—`. Clicking a row sets the linked symbol; `+ click to add…` opens the Data Manager.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { setLinked, useLinked } from '../context/linked'
import { setSettings, useSettings } from '../state/settings'
import { openDataSymbol } from './actions'
import {
  MARKET_WATCH_TABS,
  TICKER_POLL_MS,
  applyTicker,
  relatedRows,
  shouldPoll,
  tickerExchange,
  watchRows,
  watchSymbols,
  type LiveQuote,
  type WatchQuote,
  type WatchRow,
} from './marketWatchModel'

function clockText(now: number): string {
  return new Date(now).toISOString().slice(11, 19)
}

const TONE_GLYPH: Record<WatchRow['tone'], string> = { up: '▲', down: '▼', flat: '•', none: '' }

export function MarketWatch() {
  const { profile, liveTicker } = useSettings()
  const linked = useLinked()
  const [tab, setTab] = useState<string>(MARKET_WATCH_TABS[0])
  const [stored, setStored] = useState<string[]>([])
  const [quotes, setQuotes] = useState<Record<string, WatchQuote | null>>({})
  const [live, setLive] = useState<Record<string, LiveQuote | null>>({})
  const [now, setNow] = useState(() => Date.now())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [])

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
    for (const symbol of symbolKey.split(' ').filter(Boolean)) {
      api
        .candles(symbol, '?tail=2')
        .then(
          (result) =>
            live &&
            setQuotes((current) => ({
              ...current,
              [symbol]: { bars: result.bars, provenance: result.provenance },
            })),
        )
        .catch(() => live && setQuotes((current) => ({ ...current, [symbol]: null })))
    }
    return () => {
      live = false
    }
  }, [symbolKey])

  const storedRows = watchRows(profile, stored, quotes, now)
  // Public tickers: one read per quotable row every TICKER_POLL_MS, only while the toggle is on
  // and the tab is visible; a failed read leaves the stored close and its date in place.
  const tickerKey = storedRows
    .map((row) => [row.symbol, tickerExchange(row)] as const)
    .filter((entry): entry is readonly [string, string] => entry[1] !== null)
    .map(([symbol, exchange]) => `${symbol}@${exchange}`)
    .join(' ')
  useEffect(() => {
    if (!liveTicker) {
      setLive({})
      return
    }
    let alive = true
    const poll = () => {
      if (!shouldPoll(liveTicker, document.visibilityState)) return
      for (const entry of tickerKey.split(' ').filter(Boolean)) {
        const [symbol, exchange] = entry.split('@')
        api
          .ticker(symbol, exchange)
          .then((quote) => alive && setLive((current) => ({ ...current, [symbol]: quote })))
          .catch(() => alive && setLive((current) => ({ ...current, [symbol]: null })))
      }
    }
    poll()
    const timer = window.setInterval(poll, TICKER_POLL_MS)
    document.addEventListener('visibilitychange', poll)
    return () => {
      alive = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', poll)
    }
  }, [liveTicker, tickerKey])

  const rows = storedRows.map((row) => (liveTicker ? applyTicker(row, live[row.symbol]) : row))
  const selected = linked.symbol ? relatedRows(linked.symbol, rows) : []
  return (
    <div className="dock-panel market-watch">
      <div className="dock-toolbar market-watch-head">
        <span className="mono market-watch-clock" aria-label="UTC clock">{clockText(now)} UTC</span>
        <span className="spacer" />
        <label className="settings-row" title="Poll each venue's public last-trade price every 10 s while this tab is visible. Display only: nothing is stored and nothing else reads it.">
          <input
            type="checkbox"
            checked={liveTicker}
            onChange={(event) => setSettings({ liveTicker: event.target.checked })}
          />
          <span>Live</span>
        </label>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {tab === 'Symbols' ? (
        <table className="blotter market-watch-table" aria-label="Market Watch">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Venue</th>
              <th className="num">Last</th>
              <th className="num">Daily %</th>
              <th className="num">Age</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.symbol}
                className={`watch-row tone-${row.tone}${linked.symbol === row.symbol ? ' active' : ''}${row.stale ? ' stale' : ''}`}
                title={
                  row.asOf === 'live'
                    ? `${row.symbol} on ${row.venue} · public last-trade price, refreshed every 10 s`
                    : row.asOf
                      ? `${row.symbol} on ${row.venue ?? 'an unknown venue'} · last stored bar ${row.asOf}${row.stale ? ' (history, not a quote)' : ''}`
                      : `${row.symbol} · no stored bars`
                }
              >
                <td className="mono">
                  <button
                    type="button"
                    className="watch-select"
                    aria-label={row.symbol}
                    aria-pressed={linked.symbol === row.symbol}
                    onClick={() => setLinked({ symbol: row.symbol })}
                  >
                    <span className="watch-glyph" aria-hidden="true">{TONE_GLYPH[row.tone]}</span>
                    {row.label}
                  </button>
                </td>
                <td className="watch-venue">{row.venue ?? '—'}</td>
                <td className="num mono">{row.last}</td>
                <td className="num mono">{row.change}</td>
                <td className={`num mono watch-age${row.asOf === 'live' ? ' live' : ''}`}>{row.asOf ?? '—'}</td>
              </tr>
            ))}
            <tr className="watch-row watch-add">
              <td colSpan={5}>
                <button type="button" className="watch-select" onClick={openDataSymbol}>
                  + click to add…
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      ) : tab === 'Details' ? (
        <div className="market-watch-details-wrap">
          <dl className="market-watch-details">
            <dt>Symbol</dt>
            <dd className="mono">{linked.symbol ?? '—'}</dd>
            <dt>Window</dt>
            <dd className="mono">{`${linked.start ?? 'start'} → ${linked.end ?? 'latest'}`}</dd>
            <dt>Snapshot</dt>
            <dd className="mono">{linked.snapshotId ?? '—'}</dd>
          </dl>
          {selected.length ? (
            <table className="blotter market-watch-table" aria-label="Stored quotes for the selected asset">
              <thead>
                <tr>
                  <th>Pair</th>
                  <th>Venue</th>
                  <th className="num">Last</th>
                  <th className="num">Bar date</th>
                </tr>
              </thead>
              <tbody>
                {selected.map((row) => (
                  <tr key={row.symbol} className={row.stale ? 'stale' : ''}>
                    <td className="mono">{row.label}</td>
                    <td>{row.venue ?? '—'}</td>
                    <td className="num mono">{row.last}</td>
                    <td className="num mono">{row.asOf ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      ) : (
        <p className="muted">
          {stored.length} stored symbol{stored.length === 1 ? '' : 's'}; prices are the last two
          daily bars in the store, dated in the Age column. With Live on, pairs on Binance or
          Coinbase show the venue's public last trade instead (display only, never stored).
        </p>
      )}
      <nav className="rd-tabs dock-tabs" role="tablist" aria-label="Market Watch tabs">
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
    </div>
  )
}
