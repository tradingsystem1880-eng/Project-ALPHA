import { useEffect, useMemo, useState } from 'react'

import type { Candle } from '../api/types'
import { candlesCsv, chartTablePage } from './chartTableModel'

function downloadName(runId: string | null, symbol: string): string {
  const source = runId || symbol || 'market'
  return `${source.replace(/[^A-Za-z0-9._-]/g, '_')}-ohlcv.csv`
}

export function ChartDataAlternative({
  bars,
  truncated,
  runId,
  symbol,
}: {
  bars: Candle[]
  truncated: boolean
  runId: string | null
  symbol: string
}) {
  const [page, setPage] = useState(0)
  const window = useMemo(() => chartTablePage(bars, page), [bars, page])

  useEffect(() => setPage(0), [bars])

  function downloadExactCsv() {
    const url = URL.createObjectURL(
      new Blob([candlesCsv(bars)], { type: 'text/csv;charset=utf-8' }),
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = downloadName(runId, symbol)
    document.body.append(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <details className="chart-data-alternative">
      <summary>OHLCV table and exact CSV · UTC · native quote / volume units</summary>
      <div className="chart-data-toolbar mono">
        <button
          className="btn"
          aria-label="Previous OHLCV page"
          disabled={window.page === 0}
          onClick={() => setPage((value) => Math.max(0, value - 1))}
        >
          Previous
        </button>
        <span aria-live="polite">
          {window.start}–{window.end} / {window.total} RETURNED BARS · PAGE {window.page + 1}/{window.pages}
        </span>
        <button
          className="btn"
          aria-label="Next OHLCV page"
          disabled={window.page >= window.pages - 1}
          onClick={() => setPage((value) => value + 1)}
        >
          Next
        </button>
        <span className={truncated ? 'chart-bound-warning' : 'muted'}>
          {truncated
            ? 'BACKEND PROJECTION TRUNCATED · MORE BARS EXIST'
            : 'RETURNED WINDOW COMPLETE'}
        </span>
        <span className="spacer" />
        <button
          className="btn"
          aria-label="Download exact returned OHLCV CSV"
          onClick={downloadExactCsv}
        >
          Download exact returned OHLCV CSV
        </button>
      </div>
      <div className="chart-ohlcv-table-wrap" tabIndex={0} aria-label="Scrollable returned OHLCV table">
        <table className="blotter compact" aria-label="Returned OHLCV bars">
          <thead>
            <tr>
              <th>timestamp UTC</th>
              <th className="r">open</th>
              <th className="r">high</th>
              <th className="r">low</th>
              <th className="r">close</th>
              <th className="r">volume</th>
            </tr>
          </thead>
          <tbody>
            {window.rows.map((bar) => (
              <tr key={bar.t}>
                <td className="mono">{new Date(bar.t * 1_000).toISOString()}</td>
                <td className="num">{bar.o}</td>
                <td className="num">{bar.h}</td>
                <td className="num">{bar.l}</td>
                <td className="num">{bar.c}</td>
                <td className="num">{bar.v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
