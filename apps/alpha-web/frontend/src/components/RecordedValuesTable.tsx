import { useEffect, useState } from 'react'
import { recordedCsv, type ScientificPoint } from './scientificPlotModel'
export function RecordedValuesTable({ points, label, unit, panelId }: { points: readonly ScientificPoint[]; label: string; unit: string; panelId: string }) {
  const [page, setPage] = useState(0)
  useEffect(() => setPage(0), [points])
  const pages = Math.max(1, Math.ceil(points.length / 100)), current = Math.min(page, pages - 1), start = current * 100
  const download = () => {
    const url = URL.createObjectURL(new Blob([recordedCsv(points, `${label} (${unit})`)], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${panelId.replace(/[^A-Za-z0-9._-]/g, '_')}-recorded-values.csv`
    document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url)
  }
  return <details className="recorded-values"><summary>Recorded values table · {points.length.toLocaleString()} points</summary>
    <div className="chart-data-toolbar"><button className="btn" aria-label="Previous recorded values page" disabled={!current} onClick={() => setPage(current - 1)}>Previous</button>
      <span className="mono" aria-live="polite">{points.length ? start + 1 : 0}–{Math.min(start + 100, points.length)} / {points.length} · Page {current + 1}/{pages}</span>
      <button className="btn" aria-label="Next recorded values page" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Next</button>
      <button className="btn" disabled={!points.length} onClick={download}>Download exact recorded CSV</button></div>
    <p>Full returned series, independent of chart zoom. Unavailable values export as empty cells.</p>
    <table className="blotter" aria-label={`${label} recorded values`}><thead><tr><th>UTC timestamp</th><th className="r">{label} ({unit})</th></tr></thead><tbody>{points.slice(start, start + 100).map(p => <tr key={p.time}><td className="mono">{new Date(p.time * 1000).toISOString()}</td><td className="num">{p.value ?? 'Unavailable'}</td></tr>)}</tbody></table>
  </details>
}
