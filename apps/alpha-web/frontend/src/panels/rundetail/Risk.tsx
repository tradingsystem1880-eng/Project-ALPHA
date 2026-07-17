// Risk tab: tail metrics + the on-demand scenario stress (vol scaling + tail shocks) for this
// run's realized return stream.

import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { RiskReport } from '../../api/types'
import { Term } from '../../components/Term'
import type { ValidateManifest } from '../../explain/types'
import { fmtNum, fmtPct } from '../../util/format'
import { Metric, Section, asObj } from './common'

export function Risk({ manifest, runId }: { manifest: ValidateManifest; runId: string }) {
  const oos = asObj(manifest.oos_metrics)
  const [report, setReport] = useState<RiskReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .riskScenario(runId)
      .then((r) => live && setReport(r))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [runId])

  return (
    <>
      {oos ? (
        <Section title="Tail metrics">
          <div className="metric-grid">
            <Metric label="VaR 95%" value={oos.value_at_risk} pct term="value_at_risk" />
            <Metric label="ES 95%" value={oos.expected_shortfall} pct term="expected_shortfall" />
            <Metric label="Risk of ruin" value={oos.risk_of_ruin} pct term="risk_of_ruin" />
            <Metric label="Max DD" value={oos.max_drawdown} pct term="max_drawdown" />
            <Metric label="Ann. vol" value={oos.annualized_vol} pct term="annualized_vol" />
          </div>
        </Section>
      ) : null}
      <Section
        title="Scenario stress"
        right={<Term k="stationary_bootstrap">what-if on the realized stream</Term>}
      >
        {error ? (
          <div className="muted">stress unavailable for this run ({error.slice(0, 120)})</div>
        ) : !report ? (
          <div className="skeleton" style={{ height: 120 }} />
        ) : (
          <table className="blotter">
            <thead>
              <tr>
                <th>Scenario</th>
                <th className="r">Sharpe</th>
                <th className="r">Ann. vol</th>
                <th className="r">Max DD</th>
                <th className="r">VaR</th>
                <th className="r">ES</th>
                <th className="r">Total</th>
              </tr>
            </thead>
            <tbody>
              {report.scenarios.map((s) => (
                <tr key={s.name}>
                  <td className="mono">{s.name}</td>
                  <td className="num">{fmtNum(s.sharpe, 2)}</td>
                  <td className="num">{fmtPct(s.annual_vol, 1)}</td>
                  <td className="num neg">{fmtPct(s.max_drawdown, 1)}</td>
                  <td className="num">{fmtPct(s.value_at_risk, 2)}</td>
                  <td className="num">{fmtPct(s.expected_shortfall, 2)}</td>
                  <td className={`num${s.total_return < 0 ? ' neg' : ''}`}>{fmtPct(s.total_return, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </>
  )
}
