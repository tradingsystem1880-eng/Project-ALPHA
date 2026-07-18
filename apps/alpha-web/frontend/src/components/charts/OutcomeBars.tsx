// Prop-firm per-path outcome distributions: days-to-pass and payout histograms from the
// persisted Monte-Carlo paths. Binning comes from the shared histogram model; coloring is
// semantic by measure.

import { useMemo } from 'react'

import type { PropfirmPaths } from '../../api/types'
import { CHART } from '../../util/chartTheme'
import { fmtNum } from '../../util/format'
import { binValues } from './histogram'

const N_BINS = 31

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
  const model = useMemo(() => binValues(values, N_BINS), [values])
  if (!model) return null
  const padB = 16
  const padT = 6
  const plotH = height - padB - padT
  const barW = width / N_BINS
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
  const days = useMemo(
    () => data.paths.days_to_pass.filter((d): d is number => d !== null),
    [data],
  )
  return (
    <div className="outcome-bars">
      <Histogram values={days} label={`Days to pass (the ${days.length} passing paths)`} color={CHART.accent} />
      <Histogram
        values={data.paths.payout}
        label="Net payout per attempt ($, all paths incl. busts & fees)"
        color={CHART.up}
        fmt={(v) => `$${fmtNum(v, 0)}`}
      />
    </div>
  )
}
