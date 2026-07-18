// Overview tab: the verdict (explained), headline OOS metrics, the equity story, and what to
// try next — the sixty-second read of a run.

import { useMemo } from 'react'

import type { EquitySeries, TradeRow } from '../../api/types'
import { EquityChart } from '../../components/charts/EquityChart'
import { Medallion } from '../../components/charts/Medallion'
import { Term } from '../../components/Term'
import { suggestions } from '../../explain/suggestions'
import type { FoldRow, ValidateManifest } from '../../explain/types'
import { verdictStories } from '../../explain/verdictStory'
import { useSettings } from '../../state/settings'
import { ExplainCard, MetricGrid, Section, SuggestionList, asObj } from './common'

interface Props {
  manifest: ValidateManifest
  eq: EquitySeries | null
  trades: TradeRow[]
  onLaunch?: (command: string, args: string) => void
}

export function Overview({ manifest, eq, trades, onLaunch }: Props) {
  const { explain } = useSettings()
  const stories = useMemo(() => verdictStories(manifest), [manifest])
  const sugg = useMemo(() => suggestions(manifest), [manifest])
  const verdict = manifest.verdict
  const oos = asObj(manifest.oos_metrics)
  const folds: FoldRow[] = manifest.folds ?? []
  const overall = stories.find((s) => s.dimension === 'overall')

  return (
    <>
      {verdict ? (
        <Section title="Verdict" right={<Term k="verdict">A–F bands</Term>}>
          <div className="verdict-row">
            <Medallion grade={verdict.overall} big />
            <div className="dims">
              {stories
                .filter((s) => s.dimension !== 'overall')
                .map((s) => (
                  <div className="dim" key={s.dimension} title={s.narrative}>
                    <Medallion grade={s.grade} label={s.dimension} />
                    <span className="dim-note mono">{s.terse}</span>
                  </div>
                ))}
            </div>
          </div>
          {overall && explain === 'narrative' ? (
            <p className="explain-narrative">{overall.narrative}</p>
          ) : null}
        </Section>
      ) : null}

      {oos ? (
        <Section title="Out-of-sample metrics">
          <MetricGrid metrics={oos} />
        </Section>
      ) : null}

      {eq && eq.ts.length ? (
        <Section title="Equity & drawdown" right={<span className="muted">shaded = OOS test windows · ▲ trade entries</span>}>
          <EquityChart eq={eq} folds={folds} trades={trades} />
        </Section>
      ) : null}

      {sugg.length ? (
        <Section title="What to learn from this run">
          <SuggestionList items={sugg} onLaunch={onLaunch} />
        </Section>
      ) : null}

      {!verdict && !oos ? (
        <ExplainCard
          title="Plain backtest"
          story={{
            terse: 'single backtest — no gauntlet',
            narrative:
              'This is a raw backtest run: one pass over the data with fixed parameters and no ' +
              'statistical validation. Use it to inspect behavior, then send the same setup ' +
              'through `alpha validate` for the full gauntlet before believing any number here.',
            tone: 'info',
          }}
        />
      ) : null}
    </>
  )
}
