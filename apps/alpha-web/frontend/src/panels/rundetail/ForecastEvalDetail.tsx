// Forecast-eval layout: the skill scorecard, honest (post-cutoff) numbers first.

import { useMemo } from 'react'

import { forecastStories, forecastSuggestions } from '../../explain/forecast'
import type { ForecastManifest } from '../../explain/types'
import { ExplainCard, Section, SuggestionList } from './common'

export function ForecastEvalDetail({
  manifest,
  onLaunch,
}: {
  manifest: ForecastManifest
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => forecastStories(manifest), [manifest])
  const sugg = useMemo(() => forecastSuggestions(manifest), [manifest])

  return (
    <>
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
