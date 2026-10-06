import { useMemo, useState } from 'react'
import { dateWindow, seriesSummary, trailingWindow, type ScientificPoint } from './scientificPlotModel'
const utcDay = (time: number) => new Date(time * 1000).toISOString().slice(0, 10)
export function ScientificRangeControls({ points, unit, onRange, onFit, ready }: { ready: boolean; points: readonly ScientificPoint[]; unit: string; onRange: (from: number, to: number) => void; onFit: () => void }) {
  const summary = useMemo(() => seriesSummary(points), [points])
  const [from, setFrom] = useState(''), [to, setTo] = useState(''), [error, setError] = useState(false)
  const first = summary.first === null ? '' : utcDay(summary.first), last = summary.last === null ? '' : utcDay(summary.last)
  const value = (n: number | null) => n === null ? 'Unavailable' : n.toPrecision(7)
  return <div className="scientific-explore">
    <div className="scientific-range-buttons" role="group" aria-label="Scientific chart time window">
      <span>View</span><button className="btn" disabled={!ready || !points.length} onClick={onFit}>All data</button>
      {[30, 90, 365].map(days => <button className="btn" key={days} disabled={!ready || points.length < 2} title={`Last ${days} days ending at the final returned timestamp; display only`} onClick={() => { const range = trailingWindow(points, days); if (range) onRange(...range) }}>{days === 365 ? '1Y' : `${days}D`}</button>)}
      <details className="scientific-window"><summary>UTC dates</summary><form onSubmit={e => { e.preventDefault(); if (!ready || points.length < 2) return; const range = dateWindow(points, from || first, to || last); setError(!range); if (range) onRange(...range) }}>
        <label>From UTC<input className="field" type="date" aria-label="Chart start date UTC" value={from || first} onChange={e => setFrom(e.target.value)} min={first} max={last}/></label>
        <label>To UTC<input className="field" type="date" aria-label="Chart end date UTC" value={to || last} onChange={e => setTo(e.target.value)} min={first} max={last}/></label>
        <button className="btn" disabled={!ready || points.length < 2}>Apply window</button>{error ? <span role="alert">Choose an ordered range within returned coverage.</span> : null}
      </form></details>
      <details className="scientific-coverage"><summary>{summary.total.toLocaleString()} observations · {summary.missing.toLocaleString()} missing</summary><dl>
        <dt>Returned coverage · UTC</dt><dd>{first || 'Unavailable'} → {last || 'Unavailable'}</dd>
        <dt>Observed minimum</dt><dd>{value(summary.minimum)} · {unit}</dd><dt>Observed maximum</dt><dd>{value(summary.maximum)} · {unit}</dd><dt>Final timestamp value</dt><dd>{value(summary.latest)} · {unit}</dd>
      </dl><p>Summary of the full returned series, independent of zoom. Missing values remain gaps. Display ranges do not acquire or resample data.</p></details>
    </div>
  </div>
}
