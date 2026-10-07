import { useMemo } from 'react'
import type { NativeTearSheetProjection, PortfolioAnalyticsProjection } from '../api/types'
import { ScientificCartesianCanvas } from './ScientificCartesianCanvas'
import { CHART } from '../util/chartTheme'
/** Axis transforms only; bins, quantiles, returns and correlations are authored by the backend. */
function Cartesian({ rows, title, xLabel, yLabel, bars = false }: { rows: { x: number; y: number; right?: number }[]; title: string; xLabel: string; yLabel: string; bars?: boolean }) {
  if (!rows.length) return <p>{title} unavailable: no recorded points.</p>
  return <figure className="scientific-plot"><figcaption>{title}</figcaption><ScientificCartesianCanvas rows={rows} title={title} xLabel={xLabel} yLabel={yLabel} bars={bars}/><details><summary>{title} recorded values table</summary><table className="blotter"><thead><tr><th>{xLabel}</th>{bars ? <th>Right boundary</th> : null}<th>{yLabel}</th></tr></thead><tbody>{rows.map((p, i) => <tr key={i}><td>{p.x}</td>{bars ? <td>{p.right}</td> : null}<td>{p.y}</td></tr>)}</tbody></table></details></figure>
}
export function ScientificPlots({ native }: { native: NativeTearSheetProjection }) {
  const histogram = useMemo(() => native.histogram.map(p => ({ x: p.left, right: p.right, y: p.count })), [native.histogram])
  const qq = useMemo(() => native.qq.map(p => ({ x: p.theoretical, y: p.sample })), [native.qq])
  const years = [...new Set(native.calendar_returns.map(p => p.year))]
  return <div className="scientific-grid">
    <Cartesian title="Return distribution" xLabel="Return (fraction)" yLabel="Count" bars rows={histogram}/>
    <Cartesian title="Normal QQ" xLabel="Theoretical normal quantile" yLabel="Sample return (fraction)" rows={qq}/>
    <figure className="scientific-plot"><figcaption>Monthly returns · fraction</figcaption>{years.length ? <svg viewBox={`0 0 600 ${60 + years.length * 28}`} role="img" aria-label="Recorded monthly-return heatmap; exact values table below">
      {Array.from({ length: 12 }, (_, m) => <text key={m} x={75 + m * 43} y="24">{m + 1}</text>)}
      {years.map((year, row) => <g key={year}><text x="5" y={52 + row * 28}>{year}</text>{Array.from({ length: 12 }, (_, month) => { const p = native.calendar_returns.find(p => p.year === year && p.month === month + 1); return <g key={month}><rect x={62 + month * 43} y={34 + row * 28} width="40" height="25" fill={p ? p.return_value >= 0 ? CHART.up : CHART.down : CHART.grid} fillOpacity={p ? Math.max(0.2, Math.min(1, Math.abs(p.return_value) * 10)) : 1}/><text x={82 + month * 43} y={51 + row * 28} textAnchor="middle" fontSize="8">{p ? p.return_value.toFixed(3) : '—'}</text></g> })}</g>)}
    </svg> : <p>No recorded calendar returns.</p>}<details><summary>Monthly returns table</summary><table className="blotter"><thead><tr><th>Year</th><th>Month</th><th>Return (fraction)</th></tr></thead><tbody>{native.calendar_returns.map(p => <tr key={`${p.year}-${p.month}`}><td>{p.year}</td><td>{p.month}</td><td>{p.return_value}</td></tr>)}</tbody></table></details></figure>
  </div>
}
export function CorrelationPlot({ portfolio }: { portfolio: PortfolioAnalyticsProjection }) {
  const symbols = portfolio.symbols, size = Math.max(400, 110 + symbols.length * 64)
  return <figure className="scientific-plot"><figcaption>Recorded Pearson correlation · coefficient · association, not causation</figcaption>{!portfolio.correlations.length ? <p>No recorded correlations.</p> : <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Recorded portfolio correlation matrix; aligned OOS pairwise timestamp intersections">
    {symbols.map((s, i) => <g key={s}><text x="2" y={130 + i * 64}>{s}</text><text transform={`translate(${128 + i * 64},100) rotate(-45)`}>{s}</text>{symbols.map((b, j) => { const p = portfolio.correlations.find(p => p.asset_a === s && p.asset_b === b); return <g key={b}><rect x={105 + j * 64} y={105 + i * 64} width="60" height="60" fill={p?.correlation == null ? CHART.grid : p.correlation >= 0 ? CHART.up : CHART.down} fillOpacity={p?.correlation == null ? 1 : Math.max(0.15, Math.abs(p.correlation))}/><text x={135 + j * 64} y={137 + i * 64} textAnchor="middle">{p?.correlation?.toFixed(2) ?? '—'}</text></g> })}</g>)}
  </svg>}<details><summary>Correlation values, sample counts and OOS windows</summary><table className="blotter"><thead><tr><th>A</th><th>B</th><th>Coefficient</th><th>n</th><th>OOS start</th><th>OOS end</th></tr></thead><tbody>{portfolio.correlations.map(p => <tr key={`${p.asset_a}-${p.asset_b}`}><td>{p.asset_a}</td><td>{p.asset_b}</td><td>{p.correlation ?? 'Unavailable'}</td><td>{p.sample_count}</td><td>{p.oos_start ?? 'Unavailable'}</td><td>{p.oos_end ?? 'Unavailable'}</td></tr>)}</tbody></table></details><p className="mono">{JSON.stringify(portfolio.bounds)} · {JSON.stringify(portfolio.provenance)}</p></figure>
}
