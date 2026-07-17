// Forecast-run layout: the outcome cone (fan once full quantiles are served; p10/50/90 today),
// the cone summary story, and the pretraining-overlap caveat.

import { useMemo } from 'react'
import type uPlot from 'uplot'

import type { ForecastSeries } from '../../api/types'
import { hoverPlugin } from '../../components/charts/hoverPlugin'
import { UplotChart } from '../../components/UplotChart'
import { forecastStories, forecastSuggestions } from '../../explain/forecast'
import type { ForecastManifest } from '../../explain/types'
import { AXIS, CHART } from '../../util/chartTheme'
import { ExplainCard, Section, SuggestionList } from './common'

function coneOptions(): Omit<uPlot.Options, 'width' | 'height'> {
  return {
    scales: { x: { time: true }, y: {} },
    axes: [{ ...AXIS }, { ...AXIS, scale: 'y' }],
    series: [
      {},
      { label: 'History', stroke: CHART.ink, width: 1.5, points: { show: false } },
      { label: 'Median', stroke: CHART.accent, width: 1.5, dash: [4, 3], points: { show: false } },
      { stroke: 'transparent', points: { show: false } },
      { stroke: 'transparent', points: { show: false } },
    ],
    bands: [{ series: [4, 3], fill: CHART.band }],
    legend: { show: false },
    cursor: { points: { show: false } },
    plugins: [
      hoverPlugin([
        { idx: 1, label: 'close', color: CHART.ink, format: (v) => v.toFixed(2) },
        { idx: 2, label: 'median', color: CHART.accent, format: (v) => v.toFixed(2) },
      ]),
    ],
  }
}

export function ForecastDetail({
  manifest,
  fc,
  onLaunch,
}: {
  manifest: ForecastManifest
  fc: ForecastSeries | null
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => forecastStories(manifest), [manifest])
  const sugg = useMemo(() => forecastSuggestions(manifest), [manifest])

  const data = useMemo<uPlot.AlignedData | null>(() => {
    if (!fc) return null
    const x = [...fc.history_ts, ...fc.forecast_ts]
    const nH = fc.history.length
    const hist = [...fc.history, ...fc.forecast.map(() => null)]
    const median = [...fc.history.map((v, i) => (i === nH - 1 ? v : null)), ...fc.forecast]
    const pad = fc.history.map(() => null)
    const p90 = fc.p90 ? [...pad, ...fc.p90] : x.map(() => null)
    const p10 = fc.p10 ? [...pad, ...fc.p10] : x.map(() => null)
    return [x, hist, median, p90, p10] as uPlot.AlignedData
  }, [fc])
  const options = useMemo(coneOptions, [])

  return (
    <>
      {data ? (
        <Section title="Outcome cone" right={<span className="muted">band = p10–p90 of sampled paths</span>}>
          <UplotChart data={data} options={options} height={260} />
        </Section>
      ) : null}
      <Section title="The story">
        <div className="gate-cards">
          {stories.map((s) => (
            <ExplainCard key={s.title} story={s} title={s.title} stats={s.stats} />
          ))}
        </div>
      </Section>
      {sugg.length ? (
        <Section title="Next steps">
          <SuggestionList items={sugg} onLaunch={onLaunch} />
        </Section>
      ) : null}
    </>
  )
}
