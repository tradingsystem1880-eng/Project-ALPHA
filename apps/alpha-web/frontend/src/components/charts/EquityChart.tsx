// Equity + drawdown as two stacked, cursor-synced plots on one time axis (never dual-axis).
// Walk-forward fold boundaries shade the OOS test windows on the equity plot; trade entries
// mark under the curve when a trade log exists.

import { useMemo } from 'react'
import uPlot from 'uplot'

import type { EquitySeries, TradeRow } from '../../api/types'
import type { FoldRow } from '../../explain/types'
import { AXIS, CHART } from '../../util/chartTheme'
import { fmtPct } from '../../util/format'
import { UplotChart } from '../UplotChart'
import { hoverPlugin } from './hoverPlugin'

/** Shade alternate walk-forward test windows so fold structure is visible on the equity curve.
 *  Fold bounds are BAR INDICES into the full series (walkforward.py splits by position),
 *  so we map index → timestamp through the equity ts array. */
function foldShadePlugin(folds: FoldRow[], ts: number[]): uPlot.Plugin {
  return {
    hooks: {
      drawClear: (u: uPlot) => {
        if (!folds.length || !ts.length) return
        const ctx = u.ctx
        ctx.save()
        ctx.fillStyle = 'rgba(79, 141, 255, 0.05)'
        for (const f of folds) {
          if (f.index % 2 === 1) continue // alternate shading
          const t0 = ts[Math.min(f.test_start, ts.length - 1)]
          const t1 = ts[Math.min(f.test_end - 1, ts.length - 1)]
          if (t0 == null || t1 == null) continue
          const x0 = u.valToPos(t0, 'x', true)
          const x1 = u.valToPos(t1, 'x', true)
          ctx.fillRect(x0, u.bbox.top, x1 - x0, u.bbox.height)
        }
        ctx.restore()
      },
    },
  }
}

function tradeMarkerPlugin(trades: TradeRow[]): uPlot.Plugin {
  const entries = trades
    .map((t) => ({
      ts: typeof t.entry_ts === 'string' ? Date.parse(t.entry_ts) / 1000 : null,
      win: typeof t.realized_pnl === 'number' ? t.realized_pnl >= 0 : null,
    }))
    .filter((t): t is { ts: number; win: boolean | null } => t.ts !== null && Number.isFinite(t.ts))
  return {
    hooks: {
      draw: (u: uPlot) => {
        if (!entries.length) return
        const ctx = u.ctx
        ctx.save()
        const y = u.bbox.top + u.bbox.height - 4
        for (const e of entries) {
          const x = u.valToPos(e.ts, 'x', true)
          if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue
          ctx.fillStyle = e.win === null ? CHART.muted : e.win ? CHART.up : CHART.down
          ctx.beginPath()
          ctx.moveTo(x, y - 4)
          ctx.lineTo(x - 3, y)
          ctx.lineTo(x + 3, y)
          ctx.closePath()
          ctx.fill()
        }
        ctx.restore()
      },
    },
  }
}

interface Props {
  eq: EquitySeries
  folds?: FoldRow[]
  trades?: TradeRow[]
  height?: number
}

export function EquityChart({ eq, folds = [], trades = [], height = 200 }: Props) {
  const sync = useMemo(() => uPlot.sync(`eq-${Math.random().toString(36).slice(2)}`), [])

  const equityData = useMemo<uPlot.AlignedData>(() => [eq.ts, eq.equity], [eq])
  const ddData = useMemo<uPlot.AlignedData>(() => [eq.ts, eq.drawdown], [eq])

  const equityOpts = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(
    () => ({
      scales: { x: { time: true }, y: {} },
      axes: [{ ...AXIS }, { ...AXIS, scale: 'y' }],
      series: [
        {},
        { label: 'Equity', scale: 'y', stroke: CHART.accent, width: 1.5, points: { show: false } },
      ],
      cursor: { points: { show: false }, sync: { key: sync.key } },
      legend: { show: false },
      plugins: [
        foldShadePlugin(folds, eq.ts),
        tradeMarkerPlugin(trades),
        hoverPlugin([{ idx: 1, label: 'equity', color: CHART.accent, format: (v) => v.toFixed(3) }]),
      ],
    }),
    [folds, trades, eq.ts, sync.key],
  )

  const ddOpts = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(
    () => ({
      scales: { x: { time: true }, y: {} },
      axes: [
        { ...AXIS, show: false },
        {
          ...AXIS,
          scale: 'y',
          values: (_u: uPlot, vals: number[]) => vals.map((v) => `${(v * 100).toFixed(0)}%`),
        },
      ],
      series: [
        {},
        {
          label: 'Drawdown',
          scale: 'y',
          stroke: CHART.down,
          width: 1,
          fill: 'rgba(239, 83, 80, 0.12)',
          points: { show: false },
        },
      ],
      cursor: { points: { show: false }, sync: { key: sync.key } },
      legend: { show: false },
      plugins: [hoverPlugin([{ idx: 1, label: 'dd', color: CHART.down, format: (v) => fmtPct(v, 1) }])],
    }),
    [sync.key],
  )

  return (
    <div className="equity-stack">
      <UplotChart data={equityData} options={equityOpts} height={height} />
      <UplotChart data={ddData} options={ddOpts} height={70} />
    </div>
  )
}
