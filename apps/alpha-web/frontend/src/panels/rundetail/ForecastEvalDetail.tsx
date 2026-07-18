// Forecast-eval layout: the skill scorecard, honest (post-cutoff) numbers first.

import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { ForecastOrigins } from '../../api/types'
import { OriginsChart } from '../../components/charts/OriginsChart'
import { forecastStories, forecastSuggestions } from '../../explain/forecast'
import type { ForecastManifest } from '../../explain/types'
import { ExplainCard, Section, SuggestionList } from './common'

export function ForecastEvalDetail({
  manifest,
  runId,
  hasOrigins = false,
  onLaunch,
}: {
  manifest: ForecastManifest
  runId: string
  hasOrigins?: boolean
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => forecastStories(manifest), [manifest])
  const sugg = useMemo(() => forecastSuggestions(manifest), [manifest])
  const [origins, setOrigins] = useState<ForecastOrigins | null>(null)

  useEffect(() => {
    if (!hasOrigins) return
    let live = true
    api.origins(runId).then((o) => live && setOrigins(o)).catch(() => {})
    return () => {
      live = false
    }
  }, [runId, hasOrigins])

  return (
    <>
      {origins ? (
        <Section title="CRPS per origin — model vs random walk">
          <OriginsChart origins={origins} />
        </Section>
      ) : null}
      <Section title="Forecast skill — rolling origins">
        <div className="gate-cards">
          {stories.map((s) => (
            <ExplainCard key={s.title} story={s} title={s.title} stats={s.stats} />
          ))}
        </div>
        <p className="muted">
          Only the post-cutoff block measures real zero-shot skill — pre-cutoff origins overlap the
          model&apos;s pretraining data (ADR-0009). Per-origin scores live in origins.parquet.
        </p>
      </Section>
      {sugg.length ? (
        <Section title="Next steps">
          <SuggestionList items={sugg} onLaunch={onLaunch} />
        </Section>
      ) : null}
    </>
  )
}
