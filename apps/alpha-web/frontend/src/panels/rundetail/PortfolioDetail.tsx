// Portfolio / cross-sectional layout: combined metrics, per-leg breakdown, diversification story.

import { useMemo } from 'react'

import type { EquitySeries } from '../../api/types'
import { EquityChart } from '../../components/charts/EquityChart'
import { IntervalBar } from '../../components/charts/IntervalBar'
import { portfolioStories, portfolioSuggestions } from '../../explain/portfolio'
import type { PortfolioManifest } from '../../explain/types'
import { fmtNum } from '../../util/format'
import { ExplainCard, MetricGrid, Section, SuggestionList } from './common'
import { asObj } from './commonUtils'

export function PortfolioDetail({
  manifest,
  eq,
  onLaunch,
}: {
  manifest: PortfolioManifest
  eq: EquitySeries | null
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => portfolioStories(manifest), [manifest])
  const sugg = useMemo(() => portfolioSuggestions(manifest), [manifest])
  const metrics = asObj(manifest.metrics)
  const legs = manifest.legs ?? []
  const ci = manifest.sharpe_ci

  return (
    <>
      {metrics ? (
        <Section title="Combined out-of-sample metrics">
          <MetricGrid metrics={metrics} />
        </Section>
      ) : null}
      {ci ? (
        <Section title="Sharpe confidence interval">
          <IntervalBar
            lower={ci.lower ?? null}
            point={metrics ? ((metrics.sharpe as number | null) ?? null) : null}
            upper={ci.upper ?? null}
          />
        </Section>
      ) : null}
      {eq && eq.ts.length ? (
        <Section title="Combined equity & drawdown">
          <EquityChart eq={eq} />
        </Section>
      ) : null}
      <Section title="The story">
        <div className="gate-cards">
          {stories.map((s) => (
            <ExplainCard key={s.title} story={s} title={s.title} stats={s.stats} />
          ))}
        </div>
      </Section>
      {legs.length ? (
        <Section title="Legs">
          <table className="blotter">
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="r">OOS Sharpe</th>
                <th className="r">Mean weight</th>
                <th className="r">N OOS</th>
              </tr>
            </thead>
            <tbody>
              {legs.map((l) => (
                <tr key={l.symbol}>
                  <td className="mono">{l.symbol}</td>
                  <td className={`num${(l.oos_sharpe ?? 0) < 0 ? ' neg' : ''}`}>{fmtNum(l.oos_sharpe, 2)}</td>
                  <td className="num">{fmtNum(l.weight, 3)}</td>
                  <td className="num">{l.n_oos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ) : null}
      {sugg.length ? (
        <Section title="Next steps">
          <SuggestionList items={sugg} onLaunch={onLaunch} />
        </Section>
      ) : null}
    </>
  )
}
