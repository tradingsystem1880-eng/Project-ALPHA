// Per-origin forecast skill: CRPS vs the random-walk baseline across rolling origins, with the
// pretraining cutoff visually separated (pre-cutoff origins are in-sample and read hollow).

import { useMemo } from 'react'
import type uPlot from 'uplot'

import type { ForecastOrigins } from '../../api/types'
import { AXIS, CHART } from '../../util/chartTheme'
import { UplotChart } from '../UplotChart'
import { hoverPlugin } from './hoverPlugin'

function cutoffPlugin(origins: ForecastOrigins): uPlot.Plugin {
  return {
    hooks: {
      drawClear: (u: uPlot) => {
        const firstPost = origins.pre_cutoff.findIndex((p) => !p)
        if (firstPost <= 0) return
        const ctx = u.ctx
        const xCut = u.valToPos(origins.origin_ts[firstPost], 'x', true)
        ctx.save()
        // shade the pre-cutoff (in-sample) region
        ctx.fillStyle = 'rgba(215, 166, 59, 0.06)'
        ctx.fillRect(u.bbox.left, u.bbox.top, xCut - u.bbox.left, u.bbox.height)
        ctx.strokeStyle = CHART.gold
        ctx.setLineDash([3, 3])
        ctx.beginPath()
        ctx.moveTo(xCut, u.bbox.top)
        ctx.lineTo(xCut, u.bbox.top + u.bbox.height)
        ctx.stroke()
        ctx.restore()
      },
    },
  }
}

export function OriginsChart({
  origins,
  height = 220,
}: {
  origins: ForecastOrigins
  height?: number
}) {
  const data = useMemo<uPlot.AlignedData>(
    () => [origins.origin_ts, origins.crps, origins.crps_rw] as uPlot.AlignedData,
    [origins],
  )
  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(
    () => ({
      scales: { x: { time: true }, y: {} },
      axes: [{ ...AXIS }, { ...AXIS, scale: 'y' }],
      series: [
        {},
        { label: 'Model CRPS', stroke: CHART.accent, width: 1.5, points: { show: false } },
        { label: 'RW baseline', stroke: CHART.muted, width: 1, dash: [4, 3], points: { show: false } },
      ],
      legend: { show: false },
      cursor: { points: { show: false } },
      plugins: [
        cutoffPlugin(origins),
        hoverPlugin([
          { idx: 1, label: 'model', color: CHART.accent, format: (v) => v.toFixed(4) },
          { idx: 2, label: 'rw', color: CHART.muted, format: (v) => v.toFixed(4) },
        ]),
      ],
    }),
    [origins],
  )
  return (
    <div>
      <UplotChart data={data} options={options} height={height} />
      <p className="muted">
        CRPS per rolling origin (lower = sharper distributional forecast). Model below the dashed
        random-walk line = skill at that origin; the shaded region predates the pretraining cutoff
        and is in-sample.
      </p>
    </div>
  )
}
