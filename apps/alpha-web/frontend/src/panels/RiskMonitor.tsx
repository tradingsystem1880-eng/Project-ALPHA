// Risk — stress a run's realized returns under vol-scaling and tail-shock scenarios and see how
// Sharpe / vol / drawdown / VaR / CVaR move. Follows the linked run (selected in the Run Browser).

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RiskScenario } from '../api/types'
import { useLinkedField } from '../context/linked'
import { fmtNum, fmtPct } from '../util/format'
import { Placeholder } from '../components/Placeholder'

export function RiskMonitor() {
  const [runId, setRunId] = useLinkedField('runId', '')
  const [scenarios, setScenarios] = useState<RiskScenario[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) {
      setScenarios(null)
      return
    }
    let live = true
    setError(null)
    setScenarios(null)
    api
      .riskScenario(runId)
      .then((r) => live && setScenarios(r.scenarios))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [runId])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Risk · Scenarios</span>
        <input
          className="field sym-input"
          style={{ width: 132 }}
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          placeholder="run id"
          spellCheck={false}
        />
      </div>
      <div className="panel-body">
        {error ? (
          <Placeholder big="no data">{error}</Placeholder>
        ) : !runId ? (
          <Placeholder big="no run">Select a run in the browser (or paste a run id)</Placeholder>
        ) : !scenarios ? (
          <Placeholder>loading…</Placeholder>
        ) : (
          <table className="blotter">
            <thead>
              <tr>
                <th>Scenario</th>
                <th className="r">Sharpe</th>
                <th className="r">Ann Vol</th>
                <th className="r">Max DD</th>
                <th className="r">VaR</th>
                <th className="r">CVaR</th>
                <th className="r">Total</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((s) => (
                <tr key={s.name} className={s.name === 'base' ? 'sel' : ''}>
                  <td className="mono">{s.name}</td>
                  <td className="num">{s.sharpe == null ? '—' : fmtNum(s.sharpe, 2)}</td>
                  <td className="num">{fmtPct(s.annual_vol)}</td>
                  <td className="num neg">{fmtPct(s.max_drawdown)}</td>
                  <td className="num">{fmtPct(s.value_at_risk)}</td>
                  <td className="num">{fmtPct(s.expected_shortfall)}</td>
                  <td className={`num ${s.total_return >= 0 ? 'pos' : 'neg'}`}>
                    {fmtPct(s.total_return)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
