// Where the observed statistic lands in the null distribution: a 0–100% strip with the
// pass threshold marked and the observed percentile as a needle. The single number that
// decides the luck test, made spatial.

import { CHART, withAlpha } from '../../util/chartTheme'
import { fmtPct } from '../../util/format'

interface Props {
  percentile: number | null // 0..1
  threshold: number | null // 0..1
  width?: number
}

export function PercentileGauge({ percentile, threshold, width = 260 }: Props) {
  if (percentile === null || !Number.isFinite(percentile)) return <span className="muted">—</span>
  const h = 30
  const pad = 6
  const x = (v: number) => pad + Math.max(0, Math.min(1, v)) * (width - 2 * pad)
  const thr = threshold ?? 0.95
  const passed = percentile > thr
  return (
    <svg width={width} height={h} className="pct-gauge" role="img" aria-label={`percentile ${fmtPct(percentile, 1)} vs threshold ${fmtPct(thr, 0)}`}>
      {/* track */}
      <rect x={pad} y={10} width={width - 2 * pad} height={6} rx={3} fill={CHART.grid} />
      {/* pass zone */}
      <rect x={x(thr)} y={10} width={x(1) - x(thr)} height={6} rx={3} fill={withAlpha(CHART.up, 0.25)} />
      {/* observed needle */}
      <line x1={x(percentile)} x2={x(percentile)} y1={4} y2={22} stroke={passed ? CHART.up : CHART.down} strokeWidth={2.5} />
      <text x={Math.min(Math.max(x(percentile), 18), width - 18)} y={h - 1} textAnchor="middle" className="svg-num" fill={passed ? CHART.up : CHART.down}>
        {fmtPct(percentile, 1)}
      </text>
      <text x={x(thr)} y={8} textAnchor="middle" className="svg-num">
        {fmtPct(thr, 0)}
      </text>
    </svg>
  )
}
