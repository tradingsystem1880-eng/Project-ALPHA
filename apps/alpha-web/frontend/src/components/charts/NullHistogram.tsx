// The null distribution made visible: a histogram of per-path statistics with the observed
// value as a vertical marker. The single most persuasive picture in the gauntlet — "here is
// what luck looks like; here is where you landed."

import { useMemo } from 'react'

import { CHART, withAlpha } from '../../util/chartTheme'
import { fmtNum } from '../../util/format'
import { binValues } from './histogram'

interface Props {
  statistics: number[]
  observed: number | null
  threshold?: number | null // percentile 0..1 → marked as a shaded pass zone on the x axis
  width?: number
  height?: number
  title?: string
}

const N_BINS = 41

export function NullHistogram({ statistics, observed, threshold, width = 460, height = 130, title }: Props) {
  const model = useMemo(() => {
    const base = binValues(statistics, N_BINS, {
      include: observed !== null ? [observed] : [],
      padFrac: 0.04,
    })
    if (!base) return null
    const finite = statistics.filter((v) => Number.isFinite(v))
    const sorted = [...finite].sort((a, b) => a - b)
    const passCut =
      threshold != null ? sorted[Math.min(sorted.length - 1, Math.floor(threshold * sorted.length))] : null
    return { ...base, passCut }
  }, [statistics, observed, threshold])

  if (!model) return <span className="muted">no null paths persisted for this run</span>
  const padL = 8
  const padB = 18
  const padT = 14
  const plotW = width - 2 * padL
  const plotH = height - padB - padT
  const x = (v: number) => padL + ((v - model.lo) / (model.hi - model.lo)) * plotW
  const barW = plotW / N_BINS

  return (
    <div className="null-hist">
      {title ? <span className="eyebrow">{title}</span> : null}
      <svg width={width} height={height} role="img" aria-label="null distribution vs observed">
        {/* pass zone: beyond the threshold percentile of the null */}
        {model.passCut !== null ? (
          <rect x={x(model.passCut)} y={padT} width={Math.max(0, padL + plotW - x(model.passCut))} height={plotH} fill={withAlpha(CHART.up, 0.1)} />
        ) : null}
        {model.bins.map((count, i) => {
          const h = model.max ? (count / model.max) * plotH : 0
          return (
            <rect
              key={i}
              x={padL + i * barW + 0.5}
              y={padT + plotH - h}
              width={Math.max(1, barW - 1)}
              height={h}
              fill={CHART.accent}
              opacity={0.55}
            >
              <title>{`${count} paths ∈ [${fmtNum(model.lo + i * ((model.hi - model.lo) / N_BINS))}, ${fmtNum(model.lo + (i + 1) * ((model.hi - model.lo) / N_BINS))})`}</title>
            </rect>
          )
        })}
        {observed !== null && Number.isFinite(observed) ? (
          <g>
            <line x1={x(observed)} x2={x(observed)} y1={4} y2={padT + plotH} stroke={CHART.gold} strokeWidth={2} />
            <text x={Math.min(Math.max(x(observed), 30), width - 60)} y={11} textAnchor="middle" className="svg-num" fill={CHART.gold}>
              observed {fmtNum(observed)}
            </text>
          </g>
        ) : null}
        <text x={padL} y={height - 4} className="svg-num">
          {fmtNum(model.lo)}
        </text>
        <text x={width - padL} y={height - 4} textAnchor="end" className="svg-num">
          {fmtNum(model.hi)}
        </text>
        <text x={width / 2} y={height - 4} textAnchor="middle" className="svg-num">
          {model.n.toLocaleString()} no-edge paths
        </text>
      </svg>
    </div>
  )
}
