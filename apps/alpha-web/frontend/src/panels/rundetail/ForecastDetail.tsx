// Forecast-run layout: the full multi-quantile fan (50%/90% bands + optional sample spaghetti),
// the cone summary story, and the pretraining-overlap caveat.

import { useMemo } from 'react'

import { api } from '../../api/client'
import type { ForecastSeries } from '../../api/types'
import { FanChart } from '../../components/charts/FanChart'
import { forecastStories, forecastSuggestions } from '../../explain/forecast'
import type { ForecastManifest } from '../../explain/types'
import { ExplainCard, Section, SuggestionList, useProjection } from './common'

export function ForecastDetail({
  manifest,
  fc,
  runId,
  hasPaths = false,
  onLaunch,
}: {
  manifest: ForecastManifest
  fc: ForecastSeries | null
  runId: string
  hasPaths?: boolean
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => forecastStories(manifest), [manifest])
  const sugg = useMemo(() => forecastSuggestions(manifest), [manifest])
  const paths = useProjection(hasPaths, runId, () => api.forecastPaths(runId, 30))

  return (
    <>
      {fc ? (
        <Section title="Outcome fan">
          <FanChart fc={fc} paths={paths} />
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
