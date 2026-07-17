// Screener — a quote + recent news for the linked symbol (finnhub, opt-in). When the finnhub key
// isn't set the endpoints fail loud with setup instructions, shown here as a configure prompt.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ScreenerNewsItem, ScreenerQuote } from '../api/types'
import { setLinked, useLinked } from '../context/linked'
import { fmtNum, fmtTime } from '../util/format'

export function Screener() {
  const linked = useLinked()
  const [symbol, setSymbol] = useState(linked.symbol ?? 'AAPL')
  const [quote, setQuote] = useState<ScreenerQuote | null>(null)
  const [news, setNews] = useState<ScreenerNewsItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (linked.symbol) setSymbol(linked.symbol)
  }, [linked.symbol])

  useEffect(() => {
    if (!symbol) return
    let live = true
    setError(null)
    setQuote(null)
    setNews(null)
    api
      .screenerQuote(symbol)
      .then((q) => live && setQuote(q))
      .catch((e: unknown) => live && setError(String(e)))
    api
      .screenerNews(symbol)
      .then((n) => live && setNews(n.items))
      .catch(() => {})
    return () => {
      live = false
    }
  }, [symbol])

  const up = quote ? quote.change >= 0 : true

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Screener</span>
        <input
          className="field sym-input"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setLinked({ symbol })}
          placeholder="symbol"
          spellCheck={false}
        />
      </div>
      <div className="panel-body panel-pad de">
        {error ? (
          <div className="ai-note">
            <strong>Screener needs a finnhub key.</strong> {error}
          </div>
        ) : !quote ? (
          <div className="placeholder">loading…</div>
        ) : (
          <>
            <div className="quote-hero">
              <span className="quote-price num">{fmtNum(quote.current, 2)}</span>
              <span className={`quote-chg num ${up ? 'pos' : 'neg'}`}>
                {up ? '▲' : '▼'} {fmtNum(quote.change, 2)} ({fmtNum(quote.percent_change, 2)}%)
              </span>
            </div>
            <div className="metric-grid">
              <div className="metric">
                <span className="eyebrow">Open</span>
                <span className="metric-val num">{fmtNum(quote.open, 2)}</span>
              </div>
              <div className="metric">
                <span className="eyebrow">High</span>
                <span className="metric-val num">{fmtNum(quote.high, 2)}</span>
              </div>
              <div className="metric">
                <span className="eyebrow">Low</span>
                <span className="metric-val num">{fmtNum(quote.low, 2)}</span>
              </div>
              <div className="metric">
                <span className="eyebrow">Prev Close</span>
                <span className="metric-val num">{fmtNum(quote.prev_close, 2)}</span>
              </div>
            </div>
          </>
        )}

        {news && news.length ? (
          <>
            <div className="rd-head">News</div>
            <div className="news-list">
              {news.map((n, i) => (
                <a key={i} className="news-item" href={n.url} target="_blank" rel="noreferrer">
                  <span className="news-headline">{n.headline}</span>
                  <span className="news-meta mono">
                    {n.source} · {fmtTime(n.datetime)}
                  </span>
                </a>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
