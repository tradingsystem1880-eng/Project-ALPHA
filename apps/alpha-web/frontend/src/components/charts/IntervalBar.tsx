// A confidence interval as a horizontal bar: [lower ─── point ─── upper] against a zero line.
// Pure SVG — no chart lib needed for a single interval.

import { CHART } from '../../util/chartTheme'
import { fmtNum } from '../../util/format'

interface Props {
  lower: number | null
  point: number | null
  upper: number | null
  width?: number
}

export function IntervalBar({ lower, point, upper, width = 260 }: Props) {
  if (lower === null || upper === null || !Number.isFinite(lower) || !Number.isFinite(upper))
    return <span className="muted">—</span>
  const h = 34
  const pad = 34
  const lo = Math.min(lower, 0)
  const hi = Math.max(upper, 0)
  const span = hi - lo || 1
  const x = (v: number) => pad + ((v - lo) / span) * (width - 2 * pad)
  const good = lower > 0
  const color = good ? CHART.up : lower <= 0 && upper >= 0 ? CHART.gold : CHART.down
  return (
    <svg width={width} height={h} className="interval-bar" role="img" aria-label={`CI ${fmtNum(lower)} to ${fmtNum(upper)}`}>
      {/* zero line */}
      <line x1={x(0)} x2={x(0)} y1={4} y2={h - 12} stroke={CHART.muted} strokeDasharray="2 3" />
      {/* interval */}
      <line x1={x(lower)} x2={x(upper)} y1={12} y2={12} stroke={color} strokeWidth={2} />
      <line x1={x(lower)} x2={x(lower)} y1={8} y2={16} stroke={color} strokeWidth={2} />
      <line x1={x(upper)} x2={x(upper)} y1={8} y2={16} stroke={color} strokeWidth={2} />
      {point !== null && Number.isFinite(point) ? (
        <circle cx={x(point)} cy={12} r={3.5} fill={color} />
      ) : null}
      <text x={x(lower)} y={h - 2} textAnchor="middle" className="svg-num">
        {fmtNum(lower)}
      </text>
      <text x={x(upper)} y={h - 2} textAnchor="middle" className="svg-num">
        {fmtNum(upper)}
      </text>
    </svg>
  )
}
