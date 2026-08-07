// Risk — stress a run's realized returns under vol-scaling and tail-shock scenarios and see how
// Sharpe / vol / drawdown / VaR / CVaR move. Follows the linked run (selected in the Run Browser).

import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RiskReport } from '../api/types'
import { usePanelLinked } from '../context/usePanelLinked'
import { fmtNum, fmtPct } from '../util/format'
import { Placeholder } from '../components/Placeholder'
import { matchesRunScope, runScopeFromParams, runScopeLabel } from './v3Models'
import type { PanelHandleProps } from '../context/panelHandle'

export function RiskMonitor(props: PanelHandleProps) {
  const panelLink = usePanelLinked(props)
  const runId = panelLink.linked.runId ?? ''
  const [runInput, setRunInput] = useState(runId)
  const [report, setReport] = useState<RiskReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [compatibility, setCompatibility] = useState<string | null>(null)
  const runScope = runScopeFromParams(props.params)

  useEffect(() => setRunInput(runId), [runId])

  useEffect(() => {
    if (!runId) {
      setReport(null)
      setCompatibility(null)
      return
    }
    let live = true
    setError(null)
    setReport(null)
    setCompatibility(null)
    api
      .run(runId)
      .then(async (detail) => {
        if (!live) return
        if (!matchesRunScope(detail, runScope)) {
          setCompatibility(`Select a ${runScopeLabel(runScope)} run for this workspace.`)
          return
        }
        if (!detail.has_equity) {
          setCompatibility('This run has no realized equity stream. Rerun it with v3 artifacts or select an eligible run.')
          return
        }
        const value = await api.riskScenario(runId)
        if (live) setReport(value)
      })
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [runId, runScope])

  function commitRun(): void {
    const next = runInput.trim()
    if (next !== runId) panelLink.setLinked({ runId: next || null })
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Risk · Scenarios</span>
        <input
          className="field sym-input"
          style={{ width: 132 }}
          value={runInput}
          onChange={(e) => setRunInput(e.target.value)}
          onBlur={commitRun}
          onKeyDown={(e) => e.key === 'Enter' && commitRun()}
          placeholder="run id"
          spellCheck={false}
        />
      </div>
      <div className="panel-body">
        {error ? (
          <Placeholder big="no data">{error}</Placeholder>
        ) : compatibility ? (
          <Placeholder big="UNAVAILABLE">{compatibility}</Placeholder>
        ) : !runId ? (
          <Placeholder big="no run">Select a run in the browser (or paste a run id)</Placeholder>
        ) : !report ? (
          <Placeholder>loading…</Placeholder>
        ) : (
          <>
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
              {report.scenarios.map((s) => (
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
          <div className="risk-provenance">
            <span>source <b className="mono">{report.provenance.source_run_id}</b></span>
            <span>{report.provenance.source_command ?? 'unknown command'}</span>
            <span>snapshot {report.provenance.snapshot_id ?? 'live / unfrozen'}</span>
            <span>cutoff {report.provenance.research_cutoff ?? 'none'}</span>
            <span>as-of {report.provenance.as_of ?? '—'} · UTC</span>
            <span className="mono" title={report.provenance.source_artifact_sha256}>
              equity sha256 {report.provenance.source_artifact_sha256.slice(0, 12)}
            </span>
            <span>deterministic derived projection · {report.provenance.metric_namespace}</span>
          </div>
          </>
        )}
      </div>
    </div>
  )
}
