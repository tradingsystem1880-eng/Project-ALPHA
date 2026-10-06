import { useEffect, useState } from 'react'
import { api, type ArchiveChartDataset } from '../api/client'
import { edgeApi, type RuleExplanation } from '../api/edgeClient'
import type { RuleSummary } from '../api/types'
import { useLinked } from '../context/linked'
import { contextKey, evaluationUnavailable } from '../shell/edgeWorkspace'
import { selectDeskRule, useDeskRule } from '../state/deskRule'
import { openRuleBuilder, openScanner } from './actions'

export function ConditionChecklist({ archive }: { archive: ArchiveChartDataset | null }) {
  const linked = useLinked()
  const rule = useDeskRule()
  const key = contextKey(linked, archive)
  const unavailable = evaluationUnavailable(linked, archive)
  const [rules, setRules] = useState<RuleSummary[]>([])
  const [result, setResult] = useState<{ key: string; id: string; value: RuleExplanation } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => { let live = true; api.rules().then(value => { if (live) setRules(value.rules) }).catch(cause => { if (live) setError(String(cause)) }); return () => { live = false } }, [attempt])
  useEffect(() => {
    let live = true
    setResult(null); setError(null)
    if (unavailable || !rule.id || !linked.symbol) return
    edgeApi.evaluate(rule.id, linked.symbol, linked.end).then(value => { if (live) setResult({ key, id: rule.id, value }) }).catch(cause => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [key, linked.symbol, linked.end, rule.id, unavailable, attempt])
  const current = result?.key === key && result.id === rule.id ? result.value : null
  const changed = Boolean(rule.hash && current?.rules_sha256 && rule.hash !== current.rules_sha256)
  return <section className="condition-checklist" aria-label="Condition checklist">
    <h2>Why this market matches</h2>
    <label>Saved conditions<select className="field" aria-label="Saved conditions" value={rule.id} onChange={event => selectDeskRule(event.target.value)}><option value="">Choose a rule set…</option>{rules.map(item => <option key={item.name} value={item.name}>{item.spec_name || item.name}</option>)}</select></label>
    {unavailable ? <p role="status">{unavailable}</p> : !rule.id ? <p>Choose saved conditions or draft them in the rule builder.</p> : !current && !error ? <p role="status">Evaluating recorded bars…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {changed ? <p role="alert">Rules changed since this scan. <button className="btn" onClick={() => selectDeskRule(rule.id)}>Use current rules</button></p> : null}
    {current && !changed ? <>
      <p>{current.symbol} · {current.bar_ts ? new Date(current.bar_ts * 1000).toISOString().slice(0, 10) : 'No evaluated bar'} · {current.signal === 1 ? 'Long condition' : current.signal === -1 ? 'Short condition' : current.signal === 0 ? 'Flat / no direction' : 'Unavailable'}</p>
      {current.error ? <p role="alert">{current.error}</p> : null}
      <ul className="condition-rows">{current.conditions.map(row => <li key={`${row.side}:${row.index}`}><strong>{row.side} · {row.status}</strong><span className="mono">{row.label}</span><span>{row.left ?? '—'} / {row.right ?? '—'}</span>{row.reason ? <small>{row.reason}</small> : null}</li>)}</ul>
      <small className="mono">Rules {current.rules_sha256?.slice(0, 12) ?? 'unavailable'} · cutoff {current.as_of ?? 'latest stored'}</small>
    </> : null}
    <div className="edge-actions"><button className="btn" onClick={() => setAttempt(value => value + 1)}>Refresh conditions</button><button className="btn" onClick={() => openRuleBuilder()}>Edit / test rules</button><button className="btn" onClick={openScanner}>Scan markets</button></div>
    <p className="muted">A matching setup is an observation. Test after costs and against a baseline before calling it an edge.</p>
  </section>
}
