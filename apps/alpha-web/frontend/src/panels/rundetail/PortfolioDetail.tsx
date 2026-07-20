// Portfolio / cross-sectional layout: combined metrics, per-leg breakdown, diversification story.

import { useMemo } from 'react'

import type { EquitySeries, PortfolioAnalyticsProjection } from '../../api/types'
import { EquityChart } from '../../components/charts/EquityChart'
import { IntervalBar } from '../../components/charts/IntervalBar'
import { portfolioStories, portfolioSuggestions } from '../../explain/portfolio'
import type { PortfolioManifest } from '../../explain/types'
import { fmtNum, fmtPct } from '../../util/format'
import { buildCorrelationMatrix, latestAllocationRows } from '../portfolioModels'
import { ExplainCard, MetricGrid, Section, SuggestionList } from './common'
import { asObj } from './commonUtils'

export function PortfolioDetail({
  manifest,
  eq,
  analytics,
  analyticsError,
  analyticsLoading,
  onLaunch,
}: {
  manifest: PortfolioManifest
  eq: EquitySeries | null
  analytics: PortfolioAnalyticsProjection | null
  analyticsError: string | null
  analyticsLoading: boolean
  onLaunch?: (command: string, args: string) => void
}) {
  const stories = useMemo(() => portfolioStories(manifest), [manifest])
  const sugg = useMemo(() => portfolioSuggestions(manifest), [manifest])
  const metrics = asObj(manifest.metrics)
  const legs = manifest.legs ?? []
  const ci = manifest.sharpe_ci
  const latestAllocations = useMemo(
    () => latestAllocationRows(analytics?.allocations ?? []),
    [analytics],
  )
  const correlationMatrix = useMemo(
    () => buildCorrelationMatrix(analytics?.correlations ?? []),
    [analytics],
  )
  const correlationDetails = useMemo(
    () => new Map(
      (analytics?.correlations ?? []).map((row) => [
        `${row.asset_a}\u0000${row.asset_b}`,
        `n=${row.sample_count}; OOS ${row.oos_start ?? 'unavailable'} to ${row.oos_end ?? 'unavailable'}; exact pairwise timestamp intersection; ${analytics?.provenance.association_label ?? 'association, not causation'}`,
      ]),
    ),
    [analytics],
  )
  const latestExposure = analytics?.exposure.length
    ? analytics.exposure[analytics.exposure.length - 1]
    : null
  const isPortfolio = manifest.command === 'backtest_portfolio'

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
      {analytics ? (
        <Section title="Artifact-derived portfolio evidence">
          <div className="portfolio-provenance" aria-label="portfolio evidence provenance">
            <span className="chip">as-of {analytics.provenance.as_of == null ? '—' : new Date(analytics.provenance.as_of * 1000).toISOString().slice(0, 10)}</span>
            <span className="chip">UTC · {analytics.provenance.frequency}</span>
            <span className="chip">snapshot {analytics.provenance.snapshot_id ?? 'live / unfrozen'}</span>
            <span className="chip mono" title={analytics.provenance.snapshot_hash ?? ''}>
              hash {analytics.provenance.snapshot_hash?.slice(0, 12) ?? 'none'}
            </span>
            <span className="chip warn">{analytics.provenance.association_label}</span>
            {analytics.bounds.allocation_timestamps.truncated || analytics.bounds.symbols.truncated ? (
              <span className="chip warn">
                bounded view · {analytics.bounds.allocation_timestamps.returned}/{analytics.bounds.allocation_timestamps.original} timestamps · {analytics.bounds.symbols.returned}/{analytics.bounds.symbols.original} symbols
              </span>
            ) : null}
          </div>
          {latestAllocations.length ? (
            <div className="portfolio-evidence-grid">
              <div>
                <div className="section-kicker">
                  Causal sleeve allocation · {new Date(latestAllocations[0].ts * 1000).toISOString().slice(0, 10)}
                </div>
                <table className="blotter" aria-label="latest causal sleeve allocation">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th className="r">Weight</th>
                      <th className="r">Return</th>
                      <th className="r">Contribution</th>
                      <th className="r">Gross exp.</th>
                      <th className="r">Net exp.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {latestAllocations.map((row) => (
                      <tr key={row.symbol}>
                        <td className="mono">{row.symbol}</td>
                        <td className="num">{fmtPct(row.weight)}</td>
                        <td className={`num ${row.leg_return >= 0 ? 'pos' : 'neg'}`}>{fmtPct(row.leg_return)}</td>
                        <td className={`num ${row.contribution >= 0 ? 'pos' : 'neg'}`}>{fmtPct(row.contribution)}</td>
                        <td className="num">{fmtNum(row.weighted_gross_exposure, 3)}</td>
                        <td className={`num ${row.weighted_net_exposure >= 0 ? 'pos' : 'neg'}`}>{fmtNum(row.weighted_net_exposure, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div className="section-kicker">Portfolio exposure · interval start</div>
                <table className="blotter" aria-label="latest portfolio exposure">
                  <thead><tr><th>Measure</th><th className="r">Value</th><th>Status</th></tr></thead>
                  <tbody>
                    <tr><td>Gross exposure</td><td className="num">{fmtNum(latestExposure?.gross_exposure, 3)}</td><td>{latestExposure?.exposure_available ? 'engine observed' : 'unavailable'}</td></tr>
                    <tr><td>Net exposure</td><td className="num">{fmtNum(latestExposure?.net_exposure, 3)}</td><td>{latestExposure?.exposure_available ? 'engine observed' : 'unavailable'}</td></tr>
                    <tr><td>Overlay turnover</td><td className="num">{fmtNum(latestExposure?.turnover, 3)}</td><td>{latestExposure?.turnover_available ? 'available' : 'not modeled'}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
          {correlationMatrix.symbols.length ? (
            <div className="portfolio-matrix-wrap">
              <div className="section-kicker">Aligned OOS Pearson correlation · coefficient</div>
              <table className="blotter correlation-matrix" aria-label="aligned OOS correlation matrix">
                <thead><tr><th>Asset</th>{correlationMatrix.symbols.map((symbol) => <th className="r mono" key={symbol}>{symbol}</th>)}</tr></thead>
                <tbody>
                  {correlationMatrix.symbols.map((assetA, rowIndex) => (
                    <tr key={assetA}>
                      <th className="mono">{assetA}</th>
                      {correlationMatrix.values[rowIndex].map((value, columnIndex) => (
                        <td
                          className={`num ${value == null ? '' : value >= 0 ? 'pos' : 'neg'}`}
                          key={correlationMatrix.symbols[columnIndex]}
                          title={correlationDetails.get(`${assetA}\u0000${correlationMatrix.symbols[columnIndex]}`)}
                          aria-label={`${assetA} to ${correlationMatrix.symbols[columnIndex]} correlation ${value == null ? 'unavailable' : fmtNum(value, 3)}; ${correlationDetails.get(`${assetA}\u0000${correlationMatrix.symbols[columnIndex]}`) ?? ''}`}
                        >
                          {value == null ? '—' : fmtNum(value, 3)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="muted small">
                Exact pairwise OOS timestamp intersection. Sample counts and OOS bounds remain in correlations.parquet; coefficients are rendered verbatim.
              </div>
            </div>
          ) : null}
          <div className="artifact-hashes mono small">
            {Object.entries(analytics.provenance.artifact_sha256).map(([name, hash]) => (
              <span key={name} title={hash}>{name} · {hash.slice(0, 12)}</span>
            ))}
          </div>
        </Section>
      ) : analyticsLoading ? (
        <Section title="Portfolio evidence">
          <div className="portfolio-gap">Validating immutable allocation, exposure, and correlation artifacts…</div>
        </Section>
      ) : analyticsError ? (
        <Section title="Portfolio evidence · fail closed">
          <div className="portfolio-gap">The run declares portfolio analytics, but ALPHA could not validate or load the typed projection: {analyticsError}</div>
        </Section>
      ) : isPortfolio ? (
        <Section title="Portfolio evidence">
          <div className="portfolio-gap">Legacy run: causal allocation, exposure, and aligned-OOS correlation artifacts are unavailable. Rerun for portfolio analytics; ALPHA will not reconstruct them from hindsight.</div>
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
