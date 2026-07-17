// Per-fold OOS Sharpe as a compact bar strip: green above zero, red below, gap for flat folds.
// Reads at a glance whether the edge is consistent or carried by a couple of windows.

import { CHART } from '../../util/chartTheme'
import { fmtNum } from '../../util/format'

interface Props {
  values: (number | null)[]
  height?: number
  /** Bar labels for the hover title, e.g. fold index. */
  title?: (i: number) => string
}

export function FoldStrip({ values, height = 56, title }: Props) {
  if (!values.length) return <span className="muted">—</span>
  const finite = values.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  const maxAbs = Math.max(1e-9, ...finite.map((v) => Math.abs(v)))
  const mid = height / 2
  const barW = 10
  const gap = 3
  const width = values.length * (barW + gap) + gap
  return (
    <svg width={width} height={height} className="fold-strip" role="img" aria-label="per-fold Sharpe">
      <line x1={0} x2={width} y1={mid} y2={mid} stroke={CHART.grid} />
      {values.map((v, i) => {
        const x = gap + i * (barW + gap)
        if (typeof v !== 'number' || !Number.isFinite(v)) {
          return <rect key={i} x={x} y={mid - 1} width={barW} height={2} fill={CHART.muted} opacity={0.5}>
            <title>{`${title ? title(i) : `fold ${i}`}: flat`}</title>
          </rect>
        }
        const hgt = (Math.abs(v) / maxAbs) * (mid - 4)
        const y = v >= 0 ? mid - hgt : mid
        return (
          <rect key={i} x={x} y={y} width={barW} height={Math.max(1.5, hgt)} rx={1.5} fill={v >= 0 ? CHART.up : CHART.down}>
            <title>{`${title ? title(i) : `fold ${i}`}: Sharpe ${fmtNum(v)}`}</title>
          </rect>
        )
      })}
    </svg>
  )
}
