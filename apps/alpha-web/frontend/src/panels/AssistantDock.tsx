import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type ArchiveChartDataset } from '../api/client'
import { edgeApi, type AssistantAction, type AssistantSession } from '../api/edgeClient'
import { useLinked } from '../context/linked'
import { contextKey } from '../shell/edgeWorkspace'
import { useDeskRule } from '../state/deskRule'
import { openRuleBuilder } from './actions'

const ACTIONS: [AssistantAction, string][] = [
  ['explain_chart', 'Explain this chart'], ['explain_signal', 'Explain this signal'],
  ['challenge_thesis', 'Challenge this thesis'], ['explain_results', 'Explain these results'], ['draft_rules', 'Draft rules'],
]
export function AssistantDock({ archive }: { archive: ArchiveChartDataset | null }) {
  const linked = useLinked()
  const rule = useDeskRule()
  const key = `${contextKey(linked, archive)}:${rule.id}:${rule.hash ?? ''}`
  const evidence = useRef<HTMLDetailsElement>(null)
  const generation = useRef(0)
  const invalidate = useCallback(() => { generation.current++ }, [])
  const activeKey = useRef(key)
  activeKey.current = key
  const [session, setSession] = useState<AssistantSession | null>(null)
  const [sessionKey, setSessionKey] = useState('')
  const [message, setMessage] = useState('')
  const [action, setAction] = useState<AssistantAction>('explain_chart')
  const [ready, setReady] = useState<Awaited<ReturnType<typeof edgeApi.readiness>> | null>(null)
  const [busy, setBusy] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [applying, setApplying] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const stale = session !== null && key !== sessionKey
  useEffect(() => { let live = true; edgeApi.readiness().then(value => { if (live) setReady(value) }).catch(cause => { if (live) setError(String(cause)) }); return () => { live = false } }, [attempt])
  useEffect(() => {
    const request = ++generation.current
    setRestoring(true)
    setJobId(null); setBusy(false); setApplying(false)
    let id: string | null = null
    try { id = localStorage.getItem(`alpha.assistant.session:${key}`) } catch { /* History is server-side. */ }
    if (id) void edgeApi.session(id).then(value => {
      if (request !== generation.current) return
      setSession(value); setSessionKey(key)
      setJobId(value.active_job_id ?? null); setBusy(Boolean(value.active_job_id) || value.turns.some(turn => turn.status === 'running'))
    }).catch(cause => { if (request === generation.current) setError(String(cause)) })
      .finally(() => { if (request === generation.current) setRestoring(false) })
    else setRestoring(false)
    return invalidate
  }, [key, invalidate])
  const sessionId = session?.session_id
  const recordedRunning = session?.turns.some(turn => turn.status === 'running') ?? false
  useEffect(() => {
    if (!sessionId || restoring || stale || (!jobId && !recordedRunning)) return
    let live = true
    const request = generation.current
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        // The CLI journal survives a web restart; the in-memory job handle may not.
        const updated = await edgeApi.session(sessionId)
        if (!live || request !== generation.current) return
        let job: Awaited<ReturnType<typeof api.job>> | null = null
        let jobError: string | null = null
        if (jobId) {
          try { job = await api.job(jobId) } catch (cause) { jobError = String(cause) }
        }
        if (!live || request !== generation.current) return
        setSession(updated)
        const running = updated.turns.some(turn => turn.status === 'running')
        const activeJob = job !== null && ['running', 'queued'].includes(job.status)
        const latest = updated.turns.at(-1)
        if (job && !activeJob && !['done', 'succeeded'].includes(job.status)) {
          const detail = job.current_step || job.lines?.at(-1) || job.status
          setError(`Assistant job ${job.status}: ${detail}. Rescan or select current rules, then start a new conversation.`)
        } else if (jobError && running) {
          setError(`Web job status unavailable; checking the saved conversation. ${jobError}`)
        } else if (jobError && !latest) {
          setError('Web job status unavailable and no saved turn was recorded. Review the current rules and start a new conversation explicitly.')
        } else setError(null)
        setBusy(activeJob || running)
        if (!activeJob && !running) { setJobId(null); return }
        // A surviving CLI turn is bounded by the model watchdog. Poll its saved
        // outcome without starting another inference or inventing a terminal state.
        if (job && !activeJob) setJobId(null)
      } catch (cause) { if (live && request === generation.current) setError(`Connection interrupted; retrying status. ${String(cause)}`) }
      if (live && request === generation.current) timer = setTimeout(poll, 1200)
    }
    void poll()
    return () => { live = false; clearTimeout(timer) }
  }, [jobId, sessionId, recordedRunning, restoring, stale])
  const send = async () => {
    if (restoring || busy || stale) return
    const request = generation.current
    const currentRequest = () => request === generation.current && activeKey.current === key
    setBusy(true); setError(null)
    try {
      let current = session
      if (!current || stale) {
        current = await edgeApi.createSession({ symbol: archive?.instrument ?? linked.symbol ?? '',
          as_of: linked.end ? `${linked.end.slice(0, 10)}T23:59:59.999999Z` : rule.id && !archive && !linked.runId && !linked.snapshotId ? `${new Date(Date.now() - 86400000).toISOString().slice(0, 10)}T23:59:59.999999Z` : new Date().toISOString(),
          snapshot_id: archive ? null : linked.snapshotId, manifest_id: archive?.manifest_id ?? null,
          run_id: archive ? null : linked.runId, project_id: linked.projectId, rules_name: archive || linked.runId || linked.snapshotId ? null : rule.id || null,
          rules_sha256: archive || linked.runId || linked.snapshotId || !rule.id ? null : rule.hash })
        try { localStorage.setItem(`alpha.assistant.session:${key}`, current.session_id) } catch { /* No browser persistence is required for execution. */ }
        if (!currentRequest()) return
        setSession(current); setSessionKey(key)
      }
      if (!currentRequest()) return
      const job = await edgeApi.turn(current.session_id, action, message.trim())
      if (currentRequest()) setJobId(job.job_id)
    } catch (cause) { if (currentRequest()) { setError(String(cause)); setBusy(false) } }
  }
  const applyDraft = async (draft: Record<string, unknown>) => {
    if (!session || stale || applying) return
    const request = generation.current
    const currentRequest = () => request === generation.current && activeKey.current === key
    setError(null); setApplying(true)
    try {
      await edgeApi.check(session.session_id)
      if (!currentRequest()) return
      const checked = await api.ruleValidate(draft)
      if (!currentRequest()) return
      if (!checked.valid) throw new Error('Rule draft failed backend validation.')
      openRuleBuilder(draft)
    } catch (cause) { if (currentRequest()) setError(String(cause)) }
    finally { if (currentRequest()) setApplying(false) }
  }
  const reset = () => {
    generation.current++
    setSession(null); setSessionKey(''); setJobId(null); setBusy(false); setRestoring(false); setApplying(false)
    setError(null); setAttempt(value => value + 1)
    try { localStorage.removeItem(`alpha.assistant.session:${key}`) } catch { /* Optional history pointer. */ }
  }
  return <section className="assistant-dock" aria-label="Market assistant">
    <h2>Research assistant</h2><p className="muted">Find a testable edge. Challenge costs, baselines and weak evidence.</p>
    <p>{ready ? ready.available ? `Local Codex · ${ready.model}` : ready.reason : 'Checking Codex and isolation…'}</p>
    <small>Attached context is sent to your configured Codex service. Responses are advisory.</small>
    {error ? <p role="alert">{error}</p> : null}
    {stale ? <p role="status">Market context changed. Previous answers remain bound to their original inputs; start a new conversation.</p> : null}
    {session ? <details ref={evidence}><summary>Attached evidence · {session.attachments.length} sources</summary><p>Cutoff {session.context.as_of}</p><ul>{session.attachments.map(item => <li key={item.ref}><span>{item.label}</span> <code>{item.ref}</code> <small>{item.content_hash.slice(0, 12)}</small></li>)}</ul></details> : null}
    <div className="assistant-transcript" aria-live="polite">{session?.turns.map(turn => <article key={turn.turn_id}><strong>{ACTIONS.find(item => item[0] === turn.action)?.[1] ?? turn.action}</strong>{turn.message ? <p>{turn.message}</p> : null}{turn.answer ? <><p className="assistant-answer">{turn.answer.text}</p><div className="edge-actions"><small>Sources:</small>{turn.answer.citations.length ? turn.answer.citations.map(ref => <button className="btn" key={ref} aria-label={`Show attached source ${ref}`} onClick={() => { if (evidence.current) { evidence.current.open = true; evidence.current.scrollIntoView({ block: 'nearest' }); evidence.current.querySelector('summary')?.focus() } }}>{session.attachments.find(item => item.ref === ref)?.label ?? ref}</button>) : <small>No attached references</small>}</div>{turn.answer.rule_draft ? <button className="btn" disabled={stale || busy || restoring || applying} onClick={() => void applyDraft(turn.answer!.rule_draft!)}>Open draft in rule builder</button> : null}</> : <p role={turn.error ? 'alert' : 'status'}>{turn.error ?? turn.status}</p>}</article>)}</div>
    <label>Task<select className="field" aria-label="Assistant task" value={action} onChange={event => setAction(event.target.value as AssistantAction)}>{ACTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <textarea className="field" aria-label="Ask the market assistant" maxLength={4000} placeholder="What would invalidate this idea?" value={message} onChange={event => setMessage(event.target.value)} />
    <div className="edge-actions"><button className="btn primary" disabled={restoring || busy || !ready?.available || !(archive?.instrument || linked.symbol) || stale} onClick={() => void send()}>{restoring ? 'Restoring conversation…' : busy ? 'Working…' : 'Ask assistant'}</button>
      {jobId ? <button className="btn" onClick={() => { void api.cancel(jobId).then(response => { if (!response.ok) throw new Error('Cancellation failed'); }).catch(cause => setError(String(cause))) }}>Cancel assistant</button> : null}
      <button className="btn" disabled={busy} onClick={reset}>New conversation</button>
    </div>
  </section>
}
