// Optimization-run layout: the parameter surface (heatmap from the manifest's full trial grid)
// plus the three overfitting-control stories.

import { useMemo } from 'react'

import { ParamHeatmap } from '../../components/charts/ParamHeatmap'
import { optimStories, optimSuggestions } from '../../explain/optim'
import type { OptimManifest } from '../../explain/types'
import { fmtNum } from '../../util/format'
import { ExplainCard, Section, SuggestionList } from './common'

export function OptimDetail({
  manifest,
  onLaunch,
}: {
  manifest: OptimManifest
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => optimStories(manifest), [manifest])
  const sugg = useMemo(() => optimSuggestions(manifest), [manifest])
  const configs = useMemo(() => manifest.configs ?? [], [manifest])
  const sharpes = useMemo(() => manifest.sharpes ?? [], [manifest])
  const bestIndex = useMemo(() => {
    let best = -Infinity
    let idx: number | undefined
    sharpes.forEach((s, i) => {
      if (typeof s === 'number' && s > best) {
        best = s
        idx = i
      }
    })
    return idx
  }, [sharpes])

  return (
    <>
      <Section
        title={`Parameter surface · ${manifest.n_configs ?? configs.length} configs`}
        right={
          <span className="muted">
            best {fmtNum(manifest.best_sharpe)} ·{' '}
            {(manifest.best_config ?? []).map(([k, v]) => `${k}=${v}`).join(' ')}
          </span>
        }
      >
        <ParamHeatmap configs={configs} sharpes={sharpes} bestIndex={bestIndex} />
        <p className="muted">
          A trustworthy sweep shows a plateau — neighboring cells nearly as good as the ringed
          best. An isolated bright cell in a dark neighborhood is the signature of a lucky
          parameter, and the controls below exist to catch exactly that.
        </p>
      </Section>
      <Section title="Overfitting controls">
        <div className="gate-cards">
          {stories.map((s) => (
            <ExplainCard key={s.title} story={s} title={s.title} passed={s.passed} stats={s.stats} />
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
