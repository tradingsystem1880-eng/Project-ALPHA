// Prop-firm per-path outcome distributions: days-to-pass and payout histograms from the
// persisted Monte-Carlo paths. Same histogram core as NullHistogram, semantic coloring by sign.

import { useMemo } from 'react'

import type { PropfirmPaths } from '../../api/types'
import { CHART } from '../../util/chartTheme'
import { fmtNum } from '../../util/format'

function Histogram({
  values,
  width = 380,
  height = 110,
  label,
  color,
  fmt = (v: number) => fmtNum(v, 0),
}: {
  values: number[]
  width?: number
  height?: number
  label: string
  color: string
  fmt?: (v: number) => string
}) {
  const model = useMemo(() => {
    const finite = values.filter((v) => Number.isFinite(v))
    if (!finite.length) return null
    const lo = Math.min(...finite)
    const hi = Math.max(...finite)
    const nBins = 31
    const binW = (hi - lo) / nBins || 1
    const bins = new Array<number>(nBins).fill(0)
    for (const v of finite) bins[Math.min(nBins - 1, Math.floor((v - lo) / binW))] += 1
    return { lo, hi, bins, max: Math.max(...bins), n: finite.length, nBins }
  }, [values])
  if (!model) return null
  const padB = 16
  const padT = 6
  const plotH = height - padB - padT
  const barW = width / model.nBins
  return (
    <div className="outcome-hist">
      <span className="eyebrow">{label}</span>
      <svg width={width} height={height} role="img" aria-label={label}>
        {model.bins.map((count, i) => {
          const h = model.max ? (count / model.max) * plotH : 0
          return (
            <rect key={i} x={i * barW + 0.5} y={padT + plotH - h} width={Math.max(1, barW - 1)} height={h} rx={1} fill={color} opacity={0.6}>
              <title>{`${count} paths`}</title>
            </rect>
          )
        })}
        <text x={0} y={height - 3} className="svg-num">
          {fmt(model.lo)}
        </text>
        <text x={width} y={height - 3} textAnchor="end" className="svg-num">
          {fmt(model.hi)}
        </text>
        <text x={width / 2} y={height - 3} textAnchor="middle" className="svg-num">
          {model.n.toLocaleString()} paths
        </text>
      </svg>
    </div>
  )
}

export function OutcomeBars({ data }: { data: PropfirmPaths }) {
  const days = data.paths.days_to_pass.filter((d): d is number => d !== null)
  const payouts = data.paths.payout
  return (
    <div className="outcome-bars">
      <Histogram values={days} label={`Days to pass (the ${days.length} passing paths)`} color={CHART.accent} />
      <Histogram
        values={payouts}
        label="Net payout per attempt ($, all paths incl. busts & fees)"
        color={CHART.up}
        fmt={(v) => `$${fmtNum(v, 0)}`}
      />
    </div>
  )
}
