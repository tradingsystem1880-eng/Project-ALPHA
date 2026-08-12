// AI Research — a $0 research desk over the CLI: a one-click multi-strategy "analyst lanes"
// leaderboard, a bridge to the MCP server (the real conversational path), and a free-form console.
// No in-app LLM / API key — the AI lives in the MCP + Claude client.

import { useState } from 'react'

import { api, runContextForProject } from '../api/client'
import type { ResearchRow } from '../api/types'
import { useLinked, useLinkedField } from '../context/linked'
import { JobConsole } from '../components/JobConsole'
import { fmtNum, fmtPct } from '../util/format'

export function AiConsole() {
  const linked = useLinked()
  const [symbol, setSymbol] = useLinkedField('symbol', 'SPY')
  const [ranked, setRanked] = useState<ResearchRow[] | null>(null)
  const [preferredStrategy, setPreferredStrategy] = useState<string | null>(null)
  const [comparisonReason, setComparisonReason] = useState<string | null>(null)
  const [researching, setResearching] = useState(false)
  const [researchErr, setResearchErr] = useState<string | null>(null)
  const [args, setArgs] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)

  function research(): void {
    const s = symbol.trim()
    if (!s || researching) return
    setResearching(true)
    setRanked(null)
    setPreferredStrategy(null)
    setComparisonReason(null)
    setResearchErr(null)
    api
      .researchCompare(s, runContextForProject(linked.projectId))
      .then((r) => {
        setRanked(r.ranked)
        setPreferredStrategy(r.preferred_strategy)
        setComparisonReason(r.preference_reason)
      })
      .catch((e: unknown) => setResearchErr(String(e)))
      .finally(() => setResearching(false))
  }

  function run(): void {
    const a = args.trim()
    if (!a) return
    api
      .launch('', a, runContextForProject(linked.projectId))
      .then((r) => setJobId(r.job_id))
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">AI Research</span>
      </div>
      <div className="panel-body panel-pad ai">
        <div className="rd-head">Strategy comparison</div>
        <div className="ai-input">
          <input
            className="field"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && research()}
            placeholder="symbol (must have stored bars)"
            spellCheck={false}
          />
          <button className="btn primary" onClick={research} disabled={researching}>
            {researching ? 'running…' : 'Compare strategies'}
          </button>
        </div>
        {researchErr ? <div className="leak">⚠ {researchErr}</div> : null}
        {ranked ? (
          <>
            {comparisonReason ? (
              <div className="ai-note">No preferred strategy: {comparisonReason}.</div>
            ) : null}
            <table className="blotter">
            <thead>
              <tr>
                <th>Strategy</th>
                <th className="r">Total Return</th>
                <th className="r">Trades</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((r) => (
                <tr key={r.strategy} className={r.strategy === preferredStrategy ? 'sel' : ''}>
                  <td className="mono">{r.strategy}</td>
                  <td className="num">
                    {r.error ? (
                      <span className="muted">skipped</span>
                    ) : (
                      <span className={(r.total_return ?? 0) >= 0 ? 'pos' : 'neg'}>
                        {fmtPct(r.total_return)}
                      </span>
                    )}
                  </td>
                  <td className="num">{r.error ? '—' : fmtNum(r.n_trades, 0)}</td>
                </tr>
              ))}
            </tbody>
            </table>
          </>
        ) : null}

        <div className="ai-note">
          For true conversational, multi-agent research, pair the <strong>alpha MCP server</strong>{' '}
          with a Claude client (<code>uv run alpha-mcp</code>; the repo ships <code>.mcp.json</code>
          ) — it drives the same CLI tools in plain language, $0 and no API key.
        </div>

        <div className="rd-head">Command console</div>
        <div className="ai-note">
          Governed Research Case approvals, rejections, decisions, and empirical runs are blocked
          from this console. Use the Research Cockpit for bounded case actions and the trusted-local
          CLI for owner-only decisions.
        </div>
        <div className="ai-input">
          <span className="ai-prompt mono">alpha</span>
          <input
            className="field"
            value={args}
            onChange={(e) => setArgs(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="validate SPY --strategy ma_crossover"
            spellCheck={false}
          />
          <button className="btn primary" onClick={run}>
            Run
          </button>
        </div>
        {jobId ? <JobConsole jobId={jobId} /> : null}
      </div>
    </div>
  )
}
