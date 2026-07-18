// Per-trial OOS equity curves from the optim trial matrix: every configuration's cumulative
// path in one plot, the best highlighted. A plateau of similar curves = robust region; one
// curve escaping the pack = the overfitting suspect the controls exist to catch.

import { useMemo } from 'react'
import type uPlot from 'uplot'

import type { OptimTrials } from '../../api/types'
import { AXIS, CHART } from '../../util/chartTheme'
import { UplotChart } from '../UplotChart'

interface Props {
  trials: OptimTrials
  bestIndex?: number
  height?: number
}

export function TrialStrip({ trials, bestIndex, height = 220 }: Props) {
  const model = useMemo(() => {
    if (!trials.trials.length) return null
    const nSteps = trials.trials[0].returns.length
    const x = Array.from({ length: nSteps }, (_, i) => i)
    const curves = trials.trials.map((t) => {
      let eq = 1
      return t.returns.map((r) => (eq *= 1 + r))
    })
    return { x, curves }
  }, [trials])

  const data = useMemo<uPlot.AlignedData | null>(
    () => (model ? ([model.x, ...model.curves] as uPlot.AlignedData) : null),
    [model],
  )

  const options = useMemo<Omit<uPlot.Options, 'width' | 'height'>>(
    () => ({
      scales: { x: { time: false }, y: { distr: 3 } }, // log scale: growth reads linearly
      axes: [{ ...AXIS }, { ...AXIS, scale: 'y' }],
      series: [
        {},
        ...(model?.curves ?? []).map((_, i) => ({
          label: `#${i}`,
          stroke: i === bestIndex ? CHART.gold : CHART.accent,
          width: i === bestIndex ? 2 : 1,
          alpha: i === bestIndex ? 1 : 0.35,
          points: { show: false },
        })),
      ],
      legend: { show: false },
      cursor: { points: { show: false } },
    }),
    [model, bestIndex],
  )

  if (!data) return null
  return (
    <div>
      <UplotChart data={data} options={options} height={height} />
      <p className="muted">
        Every configuration&apos;s OOS equity (log scale, session index) — the gold curve is the
        selected best. A tight bundle means the edge is parameter-stable; a lone escapee is
        exactly what DSR/PBO deflate.
      </p>
    </div>
  )
}
