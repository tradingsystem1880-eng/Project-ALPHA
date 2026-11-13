import { useEffect, useRef, useState, type FormEvent } from 'react'
import { fetchNativeJobResult, isNativeJobId, type NativeJobEvidence } from '../api/nativeResults'
import './nativeJobResult.css'

export function NativeJobResult() {
  const [job, setJob] = useState('')
  const [result, setResult] = useState<NativeJobEvidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const generation = useRef(0)
  const active = useRef<AbortController | null>(null)
  function clear() {
    generation.current += 1
    active.current?.abort()
    active.current = null
    setResult(null); setError(null); setLoading(false)
  }
  useEffect(() => () => { generation.current += 1; active.current?.abort() }, [])
  function lookup(event: FormEvent) {
    event.preventDefault()
    clear()
    const identity = job.trim()
    if (!isNativeJobId(identity)) { setError('Enter a valid native job UUID.'); return }
    const current = generation.current
    const controller = new AbortController()
    active.current = controller
    setLoading(true)
    fetchNativeJobResult(identity, controller.signal).then(
      evidence => { if (current === generation.current) { setResult(evidence); setLoading(false) } },
      () => { if (current === generation.current) { setError('Native result read failed. Check the local backend and retry.'); setLoading(false) } },
    )
  }
  return <div className="panel native-job-result">
    <div className="panel-toolbar"><span className="title">Native job result</span><span className="chip kind">SYNTHETIC · UNQUALIFIED</span></div>
    <div className="panel-body panel-pad workbench" aria-label="Native job result lookup">
      <p>Read retained native RD-Agent fixture evidence by its exact job UUID. Enter the identity from the original owner receipt or CLI output. Native jobs are not listed by the transient job monitor.</p>
      <p className="workbench-notice" role="note">Read-only synthetic evidence. No model inference, accepted research, economic validity or permission to launch or resume. The server selects the recorded profile; this view cannot change it.</p>
      <form onSubmit={lookup} aria-label="Native job lookup form">
        <label htmlFor="native-result-job">Native job UUID</label>
        <div className="native-job-input-row"><input id="native-result-job" className="field mono" value={job} autoComplete="off" spellCheck={false} maxLength={64} onChange={event => { clear(); setJob(event.target.value) }} aria-describedby="native-result-help" /><button className="btn" type="submit" disabled={loading}>{loading ? 'Reading…' : error || result ? 'Retry read' : 'Read result'}</button></div>
        <p className="muted" id="native-result-help">UUID lookup only. No paths, credentials, run-manifest identity or profile selectors. Editing the identity clears the previous evidence.</p>
      </form>
      {loading && <p role="status">Reading native result…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !result && <p>Enter a native job UUID to read its retained evidence.</p>}
      {result && <section aria-label="Native result evidence" aria-live="polite">
        <h3>{result.status === 'completed' ? 'Completed — verified retained evidence' : result.status === 'invalid' ? 'Invalid evidence' : 'Evidence unavailable'}</h3>
        <p>Server evidence status: <strong>{result.status}</strong>. <span className="mono">{result.reason}</span></p>
        {result.status !== 'completed' ? <p>No verified result is available. Check the original owner evidence and server deployment configuration, then retry this read. This view cannot repair or rerun a job.</p> : <>
          <h4>Bound native dispatch</h4>
          <dl>{Object.entries(result.dispatch).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><code>{value}</code></dd></div>)}</dl>
          <h4>Synthetic result</h4>
          <p>Fixture score: <strong>{String(result.result.synthetic_score)}</strong> ({result.result.unit}). This is a deterministic fixture value, not market performance.</p>
          <p>Feedback decision: false · acceptable: false · scientific acceptance: not admitted · resume allowed: false.</p>
          <h4>Recorded native stages</h4>
          <ol>{result.receipt.charged_stages.map(stage => <li key={stage}><code>{stage}</code></li>)}</ol>
          <p>{result.receipt.fake_model_attempts} fake model attempts · {result.receipt.fake_tool_attempts} fake tool attempts · {result.receipt.actual_model_calls} actual model calls. Checkpoint continued without repeating charged stages; replay rejected.</p>
          <h4>Exact artifact provenance</h4>
          <p>The server verified the receipt against its durable owner observation. Hashes identify original artifact bytes; they do not hash this display.</p>
          <dl>{Object.entries(result.provenance).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><code>{value}</code></dd></div>)}<div><dt>fixture source sha256</dt><dd><code>{result.receipt.source_sha256}</code></dd></div></dl>
        </>}
      </section>}
    </div>
  </div>
}
