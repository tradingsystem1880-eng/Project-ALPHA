// Price — candlesticks for the linked symbol over the linked as-of window (PIT-adjusted). Typing a
// symbol here rebroadcasts it to every linked panel.

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Candle } from '../api/types'
import { setLinked, useLinked } from '../context/linked'
import { PriceChartCanvas } from '../components/PriceChartCanvas'

export function PriceChart() {
  const linked = useLinked()
  const [symbol, setSymbol] = useState(linked.symbol ?? '')
  const [bars, setBars] = useState<Candle[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (linked.symbol) setSymbol(linked.symbol)
  }, [linked.symbol])

  useEffect(() => {
    if (!symbol) {
      setBars(null)
      return
    }
    let live = true
    setError(null)
    setBars(null)
    const params = new URLSearchParams()
    if (linked.start) params.set('start', linked.start)
    if (linked.end) params.set('end', linked.end)
    const query = params.toString() ? `?${params.toString()}` : ''
    api
      .candles(symbol, query)
      .then((c) => live && setBars(c.bars))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [symbol, linked.start, linked.end])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Price</span>
        <input
          className="field sym-input"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setLinked({ symbol })}
          placeholder="symbol"
          spellCheck={false}
        />
        {bars ? <span className="count">{bars.length} bars</span> : null}
      </div>
      <div className="panel-body price-body">
        {error ? (
          <div className="placeholder">
            <div className="big">no data</div>
            {error}
          </div>
        ) : !symbol ? (
          <div className="placeholder">
            <div className="big">no symbol</div>
            Pick one in Data Explorer or a run, or type it above
          </div>
        ) : !bars ? (
          <div className="placeholder">loading…</div>
        ) : bars.length === 0 ? (
          <div className="placeholder">no bars in window</div>
        ) : (
          <PriceChartCanvas bars={bars} />
        )}
      </div>
    </div>
  )
}
