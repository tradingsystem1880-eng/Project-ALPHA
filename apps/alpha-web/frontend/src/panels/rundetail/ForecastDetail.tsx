// Forecast-run layout: the full multi-quantile fan (50%/90% bands + optional sample spaghetti),
// the cone summary story, and the pretraining-overlap caveat.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { ForecastPaths, ForecastSeries } from '../../api/types'
import { FanChart } from '../../components/charts/FanChart'
import { forecastStories, forecastSuggestions } from '../../explain/forecast'
import type { ForecastManifest } from '../../explain/types'
import { ExplainCard, Section, SuggestionList } from './common'

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
  const [paths, setPaths] = useState<ForecastPaths | null>(null)

  useEffect(() => {
    if (!hasPaths) return
    let live = true
    api.forecastPaths(runId, 30).then((p) => live && setPaths(p)).catch(() => {})
    return () => {
      live = false
    }
  }, [runId, hasPaths])

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
