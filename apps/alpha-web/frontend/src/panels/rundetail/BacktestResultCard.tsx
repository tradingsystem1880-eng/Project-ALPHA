import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { RunDetail } from '../../api/types'
import { backtestResult, backtestSource } from './backtestResultModel'

type Result = ReturnType<typeof backtestResult>
type Read = { key: string; result: Result }

export function BacktestResultCard({ detail, runId }: { detail: RunDetail; runId: string }) {
  const source = backtestSource(detail, runId)
  const key = source ? `${source.runId}:${source.sha256}` : null
  const [read, setRead] = useState<Read | null>(null)
  useEffect(() => {
    if (!key) return
    let live = true
    setRead(null)
    api.equity(runId).then(series => {
      if (live) setRead({ key, result: backtestResult(series) })
    }).catch(() => { if (live) setRead({ key, result: null }) })
    return () => { live = false }
  }, [key, runId])
  const selected = read?.key === key ? read : null
  if (!source || (selected && !selected.result)) return <section aria-label="Backtest result card">
    <h2>Backtest result</h2><p>Run: <span className="mono">{runId}</span></p>
    <p role="status">Summary unavailable: required run evidence is missing or invalid.</p>
    {source ? <p>Source: equity_curve.parquet · SHA-256: <span className="mono">{source.sha256}</span></p> : null}
  </section>
  if (!selected?.result) return <section aria-label="Backtest result card">
    <h2>Backtest result</h2><p role="status">Loading recorded evidence…</p>
  </section>
  return <section aria-label="Backtest result card">
    <h2>Backtest result</h2>
    <p role="status">Historical simulation. Drawdown is computed by the server from recorded equity.</p>
    <table className="blotter summary-table"><caption>Recorded curve result</caption>
      <thead><tr><th scope="col">Measure</th><th scope="col">Value</th><th scope="col">Unit</th></tr></thead>
      <tbody>
        <tr><th scope="row">Final drawdown</th><td className="mono">{selected.result.drawdown}</td><td>fraction of running peak equity</td></tr>
        <tr><th scope="row">Final observation time</th><td className="mono">{selected.result.timestampUtc}</td><td>UTC (whole seconds)</td></tr>
        <tr><th scope="row">Curve observations</th><td className="mono">{selected.result.observations}</td><td>count</td></tr>
      </tbody>
    </table>
    <p>Drawdown is zero at the running peak and negative below it. This is not a forecast or trading approval.
      Costs and statistical uncertainty are not assessed by this card.</p>
    <p>UTC time displays the containing whole second; fractional seconds are omitted from this display.
      Exact raw Unix seconds are retained in Source.</p>
    <details><summary>Source</summary>
      <p>Run: <span className="mono">{source.runId}</span></p>
      <p>Final observation time: <span className="mono">{selected.result.timestampUnixSeconds}</span> UTC Unix seconds (exact API value).</p>
      <p>Artifact: equity_curve.parquet · SHA-256: <span className="mono">{source.sha256}</span></p>
      <p>Projection: <span className="mono">/api/runs/{source.runId}/equity</span>. The existing API checks v3 artifact bytes on read.</p>
    </details>
  </section>
}
