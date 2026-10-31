import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { DailyRuleEvidence, DailyRuleRole, DailyRuleRoleSummary } from '../api/dailyRule'
import type { TradeRow } from '../api/types'
import type { PanelParameterHandle } from '../context/panelHandle'
import { Placeholder } from '../components/Placeholder'
import { createChartLinkRegistry } from '../shell/chartLinkRegistry'
import { openRunDetail } from './actions'
import { PriceChart } from './PriceChart'
import { RecordedPanel } from './RecordedPanel'
import { TradesTab } from './rundetail/TradesTab'

const ROLES: DailyRuleRole[] = ['baseline', 'control']
const SUMMARY: { key: keyof Omit<DailyRuleRoleSummary, 'run_id' | 'terminal'>; label: string }[] = [
  { key: 'starting_equity', label: 'Starting equity' },
  { key: 'final_equity', label: 'Final equity' },
  { key: 'gross_pnl', label: 'PnL before commissions (spread/slippage included)' },
  { key: 'net_pnl', label: 'Net P&L' },
  { key: 'fees_total', label: 'Fees' },
  { key: 'orders', label: 'Orders' },
  { key: 'fills', label: 'Fills' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'n_trades', label: 'Closed trades' },
]

function recorded(value: unknown): string {
  return value === null || value === undefined || value === '' ? 'not recorded'
    : typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function TerminalValuation({ terminal }: { terminal: DailyRuleRoleSummary['terminal'] }) {
  if (!terminal) return <div>Terminal valuation not recorded.</div>
  return <div style={{ textAlign: 'left', whiteSpace: 'normal', overflowWrap: 'anywhere' }}>
    <div>{terminal.valuation_basis === 'last_admitted_open_quote'
      ? 'Last admitted opening quote' : 'Valuation basis not recorded'}: {recorded(terminal.opening_quote_at)}</div>
    <div>Valuation event: {recorded(terminal.valuation_at)} (simulation ordering).</div>
    <div>{terminal.terminal_liquidation === false ? 'No forced liquidation.' : 'Liquidation policy not recorded.'}</div>
    <div>{terminal.terminal_decision === 'unfilled_without_next_admitted_quote' && terminal.final_decision_at
      ? <>Final decision {terminal.final_decision_at}: no next admitted quote recorded; no fill inferred.</>
      : 'Final decision not recorded.'}</div>
  </div>
}

export function DailyRuleSummary({ evidence }: { evidence: DailyRuleEvidence }) {
  const rejected = evidence.outcome === 'accounting_rejection_inconclusive'
  const outcome = rejected ? 'Inconclusive: accounting rejection.'
    : evidence.outcome === 'exploratory_complete' ? 'Exploratory recorded results.'
    : 'Outcome not recorded.'
  return <section aria-label="Daily rule comparison">
    <h2>Daily rule and control</h2>
    <p role="status">{evidence.watermark}</p>
    <p>Claim: {evidence.claim_scope} · Data origin: {evidence.data_origin}</p>
    <p role="status" aria-label="Daily study outcome">{outcome} No promotion or trading approval.</p>
    {rejected ? <div>
      <p>Rejected orders prevent a valid baseline/control comparison. <a href="#daily-rejected-counts"
        onClick={event => { event.preventDefault(); document.getElementById('daily-rejected-counts')?.scrollIntoView({ block: 'center' }) }}>Inspect rejected-order counts</a>.</p>
      <ul>{ROLES.filter(role => evidence.roles[role].rejected > 0).map(role => <li key={role}>
        {role}: {evidence.roles[role].rejected} rejected order(s), {evidence.roles[role].fills} fills.
        {' '}Accounting prevented the declared exposure.
      </li>)}</ul>
    </div> : null}
    <table className="blotter"><caption>Recorded baseline and control · units are in provenance</caption>
      <thead><tr><th scope="col">Recorded measure</th><th scope="col">Baseline</th><th scope="col">Control</th></tr></thead>
      <tbody><tr><th scope="row">Canonical run</th>{ROLES.map(role => <td key={role}>
        <button className="btn mono" onClick={() => openRunDetail(evidence.roles[role].run_id)}>
          {evidence.roles[role].run_id}
        </button>
      </td>)}</tr>{SUMMARY.map(item => <tr key={item.key} id={item.key === 'rejected' ? 'daily-rejected-counts' : undefined}><th scope="row">{item.label}</th>
        {ROLES.map(role => <td className="num" key={role}>{recorded(evidence.roles[role][item.key])}
          {item.key === 'final_equity' ? <TerminalValuation terminal={evidence.roles[role].terminal}/> : null}
        </td>)}
      </tr>)}</tbody>
    </table>
  </section>
}

export function DailyRuleInspector({ evidence, role, offset, onPage }: {
  evidence: DailyRuleEvidence; role: DailyRuleRole; offset: number; onPage: (offset: number) => void
}) {
  const page = evidence.accounting.role === role ? evidence.accounting : null
  const columns = [...new Set((page?.rows ?? []).flatMap(row => Object.keys(row)))]
  return <section aria-label="Daily study evidence inspector">
    <h3>Evidence inspector</h3>
    <details><summary>Query, snapshot, clocks and units</summary><pre>{JSON.stringify(evidence.provenance, null, 2)}</pre></details>
    <details><summary>Canonical selectors</summary><pre>{JSON.stringify(evidence.selectors, null, 2)}</pre></details>
    <details><summary>Artifact SHA-256</summary><pre>{JSON.stringify(evidence.artifact_sha256, null, 2)}</pre></details>
    <h4>{role} cash, positions and fees · recorded accounting rows</h4>
    {!page ? <p>No accounting page recorded for this role.</p> : !page.rows.length ? <p>No accounting rows on this page.</p>
      : <div style={{ overflowX: 'auto' }}><table className="blotter"><caption>{role} accounting · offset {offset}</caption>
        <thead><tr>{columns.map(key => <th scope="col" key={key}>{key.replaceAll('_', ' ')}</th>)}</tr></thead>
        <tbody>{page.rows.map((row, index) => <tr key={index}>{columns.map(key => <td className="mono" key={key}>{recorded(row[key])}</td>)}</tr>)}</tbody>
      </table></div>}
    <button className="btn" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - 100))}>Previous accounting page</button>
    <button className="btn" disabled={!page?.has_more || page.next_offset === null}
      onClick={() => { if (page?.next_offset !== null && page?.next_offset !== undefined) onPage(page.next_offset) }}>Next accounting page</button>
    {page?.has_more ? <p>More accounting rows exist. This page contains at most 100 rows.</p> : null}
  </section>
}

type EvidenceRead = { key: string; evidence?: DailyRuleEvidence; error?: string }
type TradeRead = { runId: string; rows?: TradeRow[]; error?: string }

export function DailyRuleReport({ runId, panelApi }: { runId: string; panelApi: PanelParameterHandle }) {
  const [role, setRole] = useState<DailyRuleRole>('baseline')
  const [offset, setOffset] = useState(0)
  const [read, setRead] = useState<EvidenceRead | null>(null)
  const [tradeRead, setTradeRead] = useState<TradeRead | null>(null)
  const epoch = useRef(0)
  const [registry] = useState(() => {
    const value = createChartLinkRegistry()
    value.configure(true, true)
    return value
  })
  const key = `${runId}:${role}:${offset}`
  useEffect(() => {
    const token = ++epoch.current
    let live = true
    api.dailyRuleEvidence(runId, role, offset).then(evidence => {
      if (evidence.schema !== 'DailyRuleEvidenceV1' || evidence.run_id !== runId) {
        throw new Error('Daily study evidence belongs to another run or schema')
      }
      if (evidence.available && evidence.accounting.role !== role) {
        throw new Error('Daily study accounting belongs to another role')
      }
      if (live && token === epoch.current) setRead({ key, evidence })
    }).catch(cause => { if (live && token === epoch.current) setRead({ key, error: String(cause) }) })
    return () => { live = false }
  }, [runId, role, offset, key])
  // Identity-tagged reads never display a prior run, role, or accounting page.
  const selected = read?.key === key ? read : null
  const evidence = selected?.evidence
  const roleRun = evidence?.available ? evidence.roles[role].run_id : null
  useEffect(() => {
    if (!roleRun) return
    let live = true
    api.trades(roleRun).then(rows => { if (live) setTradeRead({ runId: roleRun, rows }) })
      .catch(cause => { if (live) setTradeRead({ runId: roleRun, error: String(cause) }) })
    return () => { live = false }
  }, [roleRun])
  if (selected?.error) return <Placeholder big="Daily study unavailable"><span role="alert">{selected.error}</span></Placeholder>
  if (!evidence) return <Placeholder><span role="status">Loading daily study evidence…</span></Placeholder>
  if (!evidence.available) return <Placeholder big="Daily study evidence unavailable">{evidence.watermark}</Placeholder>
  const trades = tradeRead?.runId === roleRun ? tradeRead : null
  return <div className="daily-rule-report">
    <DailyRuleSummary evidence={evidence}/>
    <label>Recorded role <select aria-label="Daily study role" value={role} onChange={event => {
      setRole(event.target.value as DailyRuleRole); setOffset(0)
    }}><option value="baseline">Baseline</option><option value="control">Control</option></select></label>
    {roleRun ? <>
      <h3>{role} · linked price, trades and recorded curves</h3>
      <div style={{ minHeight: 450 }}><PriceChart key={`price:${roleRun}`} api={panelApi}
        params={{ source: { kind: 'run', runId: roleRun }, panelId: 'daily-price', registry }}/></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
        {(['equity', 'benchmark', 'drawdown', 'exposure'] as const).map(kind => <div key={`${roleRun}:${kind}`} style={{ minHeight: 220 }}>
          <RecordedPanel runId={roleRun} kind={kind} panelId={`daily-${kind}`} registry={registry}/>
        </div>)}
      </div>
      {!trades ? <p role="status">Loading {role} trades…</p> : trades.error ? <p role="alert">Trades unavailable: {trades.error}</p>
        : <TradesTab key={roleRun} trades={trades.rows ?? []} runId={roleRun}/>}
    </> : null}
    <DailyRuleInspector evidence={evidence} role={role} offset={offset} onPage={setOffset}/>
  </div>
}
