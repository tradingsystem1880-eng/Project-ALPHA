// Parameter-sweep visualization from the optim manifest's configs[] + sharpes[].
// Two varying axes → heatmap (sequential single-hue ramp, value labeled in each cell);
// one varying axis → bar strip. The best cell is ringed. Plateaus good, pinnacles suspect.

import { useMemo } from 'react'

import { CHART } from '../../util/chartTheme'
import { fmtNum } from '../../util/format'

type Pair = [string, number]

interface Props {
  configs: Pair[][]
  sharpes: (number | null)[]
  bestIndex?: number
}

interface Grid {
  xName: string
  yName: string | null
  xVals: number[]
  yVals: number[]
  cells: Map<string, { sharpe: number | null; index: number }>
}

function buildGrid(configs: Pair[][], sharpes: (number | null)[]): Grid | null {
  if (!configs.length) return null
  // find axes that actually vary
  const byName = new Map<string, Set<number>>()
  for (const cfg of configs)
    for (const [k, v] of cfg) {
      if (!byName.has(k)) byName.set(k, new Set())
      byName.get(k)!.add(v)
    }
  const varying = [...byName.entries()].filter(([, s]) => s.size > 1).map(([k, s]) => ({ k, n: s.size }))
  if (!varying.length) return null
  varying.sort((a, b) => b.n - a.n)
  const xName = varying[0].k
  const yName = varying.length > 1 ? varying[1].k : null
  const xVals = [...byName.get(xName)!].sort((a, b) => a - b)
  const yVals = yName ? [...byName.get(yName)!].sort((a, b) => a - b) : [0]
  const cells = new Map<string, { sharpe: number | null; index: number }>()
  configs.forEach((cfg, i) => {
    const cx = cfg.find(([k]) => k === xName)?.[1]
    const cy = yName ? cfg.find(([k]) => k === yName)?.[1] : 0
    if (cx === undefined || cy === undefined) return
    cells.set(`${cx}|${cy}`, { sharpe: sharpes[i] ?? null, index: i })
  })
  return { xName, yName, xVals, yVals, cells }
}

/** Sequential ramp on the accent hue: light (low) → saturated (high) against the dark surface. */
function ramp(t: number): string {
  const a = 0.1 + 0.85 * Math.max(0, Math.min(1, t))
  return `rgba(79, 141, 255, ${a.toFixed(3)})`
}

export function ParamHeatmap({ configs, sharpes, bestIndex }: Props) {
  const grid = useMemo(() => buildGrid(configs, sharpes), [configs, sharpes])
  if (!grid) return <span className="muted">single configuration — nothing to sweep</span>

  const finite = sharpes.filter((s): s is number => typeof s === 'number' && Number.isFinite(s))
  const lo = Math.min(...finite)
  const hi = Math.max(...finite)
  const span = hi - lo || 1
  const cell = 54
  const cellH = 34
  const padL = 64
  const padB = 30
  const padT = 18
  const width = padL + grid.xVals.length * cell + 8
  const height = padT + grid.yVals.length * cellH + padB

  return (
    <div className="heatmap-wrap">
      <svg width={width} height={height} role="img" aria-label={`OOS Sharpe by ${grid.xName}${grid.yName ? ` × ${grid.yName}` : ''}`}>
        {grid.yVals.map((yv, yi) =>
          grid.xVals.map((xv, xi) => {
            const c = grid.cells.get(`${xv}|${yv}`)
            const x = padL + xi * cell
            const y = padT + yi * cellH
            const s = c?.sharpe ?? null
            const isBest = c !== undefined && bestIndex !== undefined && c.index === bestIndex
            return (
              <g key={`${xi}-${yi}`}>
                <rect
                  x={x + 1}
                  y={y + 1}
                  width={cell - 2}
                  height={cellH - 2}
                  rx={3}
                  fill={s === null ? 'transparent' : ramp((s - lo) / span)}
                  stroke={isBest ? CHART.gold : CHART.line}
                  strokeWidth={isBest ? 2 : 1}
                >
                  <title>{`${grid.xName}=${xv}${grid.yName ? `, ${grid.yName}=${yv}` : ''}: Sharpe ${fmtNum(s)}`}</title>
                </rect>
                <text x={x + cell / 2} y={y + cellH / 2 + 3.5} textAnchor="middle" className="svg-num" fill={CHART.ink}>
                  {fmtNum(s, 2)}
                </text>
              </g>
            )
          }),
        )}
        {grid.xVals.map((xv, xi) => (
          <text key={xi} x={padL + xi * cell + cell / 2} y={height - padB + 14} textAnchor="middle" className="svg-num">
            {xv}
          </text>
        ))}
        {grid.yVals.map((yv, yi) => (
          <text key={yi} x={padL - 8} y={padT + yi * cellH + cellH / 2 + 3.5} textAnchor="end" className="svg-num">
            {grid.yName ? yv : ''}
          </text>
        ))}
        <text x={padL + (grid.xVals.length * cell) / 2} y={height - 4} textAnchor="middle" className="svg-axis-label">
          {grid.xName}
        </text>
        {grid.yName ? (
          <text x={12} y={padT + (grid.yVals.length * cellH) / 2} textAnchor="middle" className="svg-axis-label" transform={`rotate(-90 12 ${padT + (grid.yVals.length * cellH) / 2})`}>
            {grid.yName}
          </text>
        ) : null}
      </svg>
    </div>
  )
}
