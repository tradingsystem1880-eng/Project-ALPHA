// The full forecast fan: layered central bands (50% and 90%) around the median, optional
// per-sample spaghetti underneath. One hue — the bands encode probability density, not identity.

import { useMemo, useState } from 'react'
import type uPlot from 'uplot'

import type { ForecastPaths, ForecastSeries } from '../../api/types'
import { AXIS, CHART } from '../../util/chartTheme'
import { UplotChart } from '../UplotChart'
import { hoverPlugin } from './hoverPlugin'

function spaghettiPlugin(paths: ForecastPaths | null): uPlot.Plugin {
  return {
    hooks: {
      draw: (u: uPlot) => {
        if (!paths || !paths.samples.length) return
        const ctx = u.ctx
        ctx.save()
        ctx.beginPath()
        ctx.rect(u.bbox.left, u.bbox.top, u.bbox.width, u.bbox.height)
        ctx.clip()
        ctx.strokeStyle = CHART.accent
        ctx.globalAlpha = 0.14
        ctx.lineWidth = 1
        for (const s of paths.samples) {
          ctx.beginPath()
          s.closes.forEach((c, i) => {
            const px = u.valToPos(paths.ts[i], 'x', true)
            const py = u.valToPos(c, 'y', true)
            if (i === 0) ctx.moveTo(px, py)
            else ctx.lineTo(px, py)
          })
          ctx.stroke()
        }
        ctx.restore()
      },
    },
  }
}

interface Props {
  fc: ForecastSeries
  paths: ForecastPaths | null
  height?: number
}

export function FanChart({ fc, paths, height = 280 }: Props) {
  const [showPaths, setShowPaths] = useState(false)

  const data = useMemo<uPlot.AlignedData>(() => {
    const x = [...fc.history_ts, ...fc.forecast_ts]
    const nH = fc.history.length
    const padH = fc.history.map(() => null)
    const joined = (arr: number[] | null | undefined): (number | null)[] =>
      arr ? [...fc.history.map((v, i) => (i === nH - 1 ? v : null)), ...arr] : x.map(() => null)
    return [
      x,
      [...fc.history, ...fc.forecast.map(() => null)], // 1 history
      joined(fc.forecast), // 2 median
      fc.p90 ? [...padH, ...fc.p90] : x.map(() => null), // 3 q95
      fc.q75 ? [...padH, ...fc.q75] : x.map(() => null), // 4 q75
      fc.q25 ? [...padH, ...fc.q25] : x.map(() => null), // 5 q25
      fc.p10 ? [...padH, ...fc.p10] : x.map(() => null), // 6 q05
    ] as uPlot.AlignedData
  }, [fc])

  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(
    () => ({
      scales: { x: { time: true }, y: {} },
      axes: [{ ...AXIS }, { ...AXIS, scale: 'y' }],
      series: [
        {},
        { label: 'History', stroke: CHART.ink, width: 1.5, points: { show: false } },
        { label: 'Median', stroke: CHART.accent, width: 1.5, dash: [4, 3], points: { show: false } },
        { stroke: 'transparent', points: { show: false } },
        { stroke: 'transparent', points: { show: false } },
        { stroke: 'transparent', points: { show: false } },
        { stroke: 'transparent', points: { show: false } },
      ],
      // layered central intervals: 90% (light) behind 50% (denser)
      bands: [
        { series: [3, 6], fill: 'rgba(79, 141, 255, 0.10)' },
        { series: [4, 5], fill: 'rgba(79, 141, 255, 0.20)' },
      ],
      legend: { show: false },
      cursor: { points: { show: false } },
      plugins: [
        spaghettiPlugin(showPaths ? paths : null),
        hoverPlugin([
          { idx: 1, label: 'close', color: CHART.ink, format: (v) => v.toFixed(2) },
          { idx: 2, label: 'median', color: CHART.accent, format: (v) => v.toFixed(2) },
          { idx: 6, label: 'p05', color: CHART.muted, format: (v) => v.toFixed(2) },
          { idx: 3, label: 'p95', color: CHART.muted, format: (v) => v.toFixed(2) },
        ]),
      ],
    }),
    [paths, showPaths],
  )

  return (
    <div className="fan-chart">
      <div className="fan-controls">
        <span className="muted">bands = 50% / 90% central intervals of sampled paths</span>
        {paths && paths.samples.length ? (
          <button className="btn ghost" onClick={() => setShowPaths((s) => !s)}>
            {showPaths ? 'hide' : 'show'} {paths.samples.length} sample paths
          </button>
        ) : null}
      </div>
      <UplotChart data={data} options={options} height={height} />
    </div>
  )
}
