import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { investigations, type Draft, type Eligibility, type Investigation, type Proxy } from '../api/investigations'

function ownsEpoch(mounted: {current: boolean}, generation: {current: number}, token: number, live = true): boolean {
  return mounted.current && live && token === generation.current
}

/** Key by runId at the caller: responses from a previous run cannot replace this panel. */
export function RunInvestigation({ runId }: { runId: string }) {
  const [eligibility, setEligibility] = useState<Eligibility | null>(null)
  const [cases, setCases] = useState<Investigation[]>([])
  const [current, setCurrent] = useState<Investigation | null>(null)
  const [question, setQuestion] = useState('Investigate this run’s losses, execution quality and what to test next.')
  const [followup, setFollowup] = useState('')
  const [proxies, setProxies] = useState<Proxy[]>([{symbol: 'SPY', asset_class: 'etf', role: 'market'}])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  // Restart the selected record's poll when invalidation leaves its id unchanged.
  const [pollRevision, setPollRevision] = useState(0)
  const mounted = useRef(true)
  const generation = useRef(0)
  const advanceGeneration = () => {
    generation.current++
    setPollRevision(revision => revision + 1)
    return generation.current
  }
  useEffect(() => {
    mounted.current = true
    let live = true
    const epoch = generation.current
    const epochRef = generation
    Promise.all([investigations.eligibility(runId), investigations.list(runId)]).then(([eligible, rows]) => {
      if (!ownsEpoch(mounted, generation, epoch, live)) return
      setEligibility(eligible); setCases(rows); setCurrent(rows[0] ?? null); setDraft(rows[0]?.comparison_draft ?? null)
    }).catch(cause => { if (ownsEpoch(mounted, generation, epoch, live)) setError(String(cause)) })
    return () => { live = false; mounted.current = false; epochRef.current++ }
  }, [runId])
  const id = current?.id
  useEffect(() => {
    if (!id) return
    let live = true
    let timer: ReturnType<typeof setTimeout>
    const epoch = generation.current
    const ownsPoll = () => ownsEpoch(mounted, generation, epoch, live)
    const poll = async () => {
      try {
        const value = await investigations.show(id)
        if (!ownsPoll()) return
        setCurrent(value); setPollError(null)
        if (value.active_job_id) setJobId(value.active_job_id)
        else if (jobId) {
          if (['completed', 'failed', 'interrupted', 'blocked'].includes(value.status)) {
            setJobId(null)
          } else {
            const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`)
            if (!ownsPoll()) return
            if (response.status === 404) setJobId(null)
            else {
              if (!response.ok) throw new Error(`Job status unavailable (${response.status})`)
              const job = await response.json() as {status: string}
              if (ownsPoll() && !['running', 'queued'].includes(job.status)) setJobId(null)
            }
          }
        }
      } catch (cause) { if (ownsPoll()) setPollError(String(cause)) }
      if (ownsPoll()) timer = setTimeout(poll, 1500)
    }
    void poll()
    return () => { live = false; clearTimeout(timer) }
  }, [id, jobId, pollRevision])
  const running = busy || Boolean(current?.active_job_id) || current?.status === 'running' || Boolean(jobId)
  const act = async (operation: (isCurrent: () => boolean, advance: () => number) => Promise<void>) => {
    let token = generation.current
    const ownsAction = () => ownsEpoch(mounted, generation, token)
    const advance = () => { token = advanceGeneration(); return token }
    setBusy(true); setError(null)
    try { await operation(ownsAction, advance) } catch (cause) { if (ownsAction()) setError(String(cause)) }
    finally { if (ownsAction()) setBusy(false) }
  }
  const select = (value: Investigation | null) => {
    advanceGeneration(); setBusy(false); setCurrent(value); setDraft(value?.comparison_draft ?? null); setJobId(value?.active_job_id ?? null); setError(null); setPollError(null)
  }
  const start = () => act(async (_ownsAction, advance) => {
    advance() // Retire the poll already in flight while the new record is created.
    const value = await investigations.create(runId, question.trim())
    if (!_ownsAction()) return
    advance() // Retire the replacement poll before switching to the created record.
    setCases(rows => [value, ...rows]); setCurrent(value)
    const job = await investigations.turn(value.id)
    if (_ownsAction()) setJobId(job.job_id)
  })
  const turn = (message?: string) => act(async ownsAction => {
    if (!current) return
    const job = await investigations.turn(current.id, message)
    if (ownsAction()) { setJobId(job.job_id); setFollowup('') }
  })
  return <section aria-label="Run investigation" style={{ padding: 12, minWidth: 0, overflowWrap: 'anywhere' }}>
    <h2>Investigate this run</h2>
    <p>Codex examines verified recorded evidence. Findings are advisory; hypotheses and proposed tests are not established causes or trading approval.</p>
    {error ? <p role="alert">{error}</p> : null}
    {pollError ? <p role="status">Status temporarily unavailable; retrying. {pollError}</p> : null}
    {!eligibility ? <p role="status">Checking recorded-run eligibility…</p> : !eligibility.eligible ? <p role="status">Unavailable for this run: {eligibility.reason}. Historical manifests are not rewritten.</p> : <>
      <label>Research question<textarea className="field" aria-label="Investigation question" value={question} maxLength={8000} onChange={event => setQuestion(event.target.value)} /></label>
      <button className="btn" disabled={running || !question.trim()} onClick={() => void start()}>Start new investigation</button>
    </>}
    {cases.length ? <label>Saved investigations<select className="field" aria-label="Saved investigations" disabled={running} value={current?.id ?? ''} onChange={event => select(cases.find(item => item.id === event.target.value) ?? null)}>{cases.map(item => <option key={item.id} value={item.id}>{item.question} · {item.id.slice(0, 8)}</option>)}</select></label> : null}
    {current ? <>
      <p role="status">{current.status} · cutoff {current.cutoff} · {current.turns_remaining} model turns and {current.requests_remaining} tool requests remaining</p>
      {current.error ? <p role="alert">{current.error}</p> : null}
      {current.progress.length ? <ol>{current.progress.map((item, index) => <li key={index}>{item.message}</li>)}</ol> : null}
      {jobId ? <button className="btn" onClick={() => void act(async ownsAction => { const response = await api.cancel(jobId); if (!ownsAction()) return; if (!response.ok) throw new Error('Cancellation failed') })}>Cancel investigation</button> : null}
      {current.can_resume ? <button className="btn" disabled={running} onClick={() => void turn()}>Resume investigation</button> : null}
      {current.report ? <>
        <h3>{current.status === 'completed' ? 'Findings' : 'Previous verified report'}</h3>{current.status !== 'completed' ? <p>The latest operation has not completed successfully. This report is retained from the previous completed turn.</p> : null}<ul>{current.report.findings.map((item, index) => <li key={index}>{item.observation}<small> Evidence: {item.receipt_ids.join(', ')}</small></li>)}</ul>
        <h3>Hypotheses to test</h3><ul>{current.report.hypotheses.map((item, index) => <li key={index}>{item}</li>)}</ul>
        <h3>Proposed next tests</h3><ul>{current.report.next_tests.map((item, index) => <li key={index}>{item}</li>)}</ul>
        <h3>Limitations</h3><ul>{current.report.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
      </> : null}
      <details><summary>Verified evidence · {current.receipts.length} receipts</summary><pre style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{JSON.stringify(current.receipts, null, 2)}</pre></details>
      {current.can_followup ? <><label>Follow-up question<textarea className="field" aria-label="Investigation follow-up" value={followup} maxLength={8000} onChange={event => setFollowup(event.target.value)} /></label><button className="btn" disabled={running || !followup.trim()} onClick={() => void turn(followup.trim())}>Ask follow-up</button></> : null}
      <details><summary>Acquire comparison evidence</summary><p>Explicit Tiingo US stock/ETF proxies in USD, XNYS calendar. Suitability is your selection; no automatic substitution or retries.</p>
        {proxies.map((proxy, index) => <fieldset key={index} disabled={running}><legend>Comparison {index + 1}</legend><label>Symbol<input className="field" aria-label={`Comparison symbol ${index + 1}`} value={proxy.symbol} onChange={event => {setDraft(null); setProxies(rows => rows.map((row, i) => i === index ? {...row, symbol: event.target.value.toUpperCase()} : row))}} /></label><label>Asset class<select aria-label={`Comparison asset class ${index + 1}`} value={proxy.asset_class} onChange={event => {setDraft(null); setProxies(rows => rows.map((row, i) => i === index ? {...row, asset_class: event.target.value as Proxy['asset_class']} : row))}}><option value="etf">ETF</option><option value="stock">Stock</option></select></label><label>Role<select aria-label={`Comparison role ${index + 1}`} value={proxy.role} onChange={event => {setDraft(null); setProxies(rows => rows.map((row, i) => i === index ? {...row, role: event.target.value as Proxy['role']} : row))}}>{['asset', 'market', 'sector', 'other'].map(role => <option key={role}>{role}</option>)}</select></label>{proxies.length > 1 ? <button onClick={() => {setDraft(null); setProxies(rows => rows.filter((_, i) => i !== index))}}>Remove comparison</button> : null}</fieldset>)}
        <button className="btn" disabled={running || proxies.length >= 4} onClick={() => {setDraft(null); setProxies(rows => [...rows, {symbol: '', asset_class: 'etf', role: 'other'}])}}>Add comparison</button>
        <button className="btn" disabled={running || current.acquisition_status !== 'not_started'} onClick={() => void act(async ownsAction => { const value = await investigations.draft(current.id, proxies); if (ownsAction()) setDraft(value) })}>Preview acquisition plan</button>
        {(draft) ? <><section aria-label="Comparison acquisition preview"><h4>Comparison acquisition plan</h4><p>{draft.provider} · {draft.start} to {draft.end}</p><p>{draft.currency} · venue {draft.venue} · calendar {draft.calendar}</p><ul>{draft.series.map(series => <li key={series.symbol}>{series.symbol} · {series.asset_class.toUpperCase()} · {series.role}</li>)}</ul><p>{draft.limitation}</p></section><button className="btn" disabled={running || current.acquisition_status !== 'not_started'} onClick={() => void act(async ownsAction => {const value = draft; if (!value) return; const job = await investigations.acquire(current.id, value.plan_sha256); if (ownsAction()) setJobId(job.job_id)})}>Acquire this comparison plan</button></> : null}
        <p>Acquisition: {current.acquisition_status}</p>
        {current.acquisition_status === 'succeeded' && !current.comparison_child_id && current.comparison_draft ? <button className="btn" disabled={running} onClick={() => void act(async ownsAction => {const value = current.comparison_draft; if (!value) return; const job = await investigations.acquire(current.id, value.plan_sha256); if (ownsAction()) setJobId(job.job_id)})}>Finish comparison handoff</button> : null}
        {current.comparison_child_id ? <button className="btn" disabled={running} onClick={() => void act(async ownsAction => {const value = await investigations.show(current.comparison_child_id!); if (ownsAction()) {setCases(rows => rows.some(row => row.id === value.id) ? rows : [value, ...rows]); select(value)}})}>Open comparison investigation</button> : null}
      </details>
    </> : null}
  </section>
}
