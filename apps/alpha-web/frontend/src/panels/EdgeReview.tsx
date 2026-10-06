/** Evidence summary over immutable run detail and existing native analytics projections. */
import { Fragment, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { NativeTearSheetProjection, RunDetail } from '../api/types'
import { useLinked } from '../context/linked'
import { edgeReviewRows } from './edgeReviewModel'
import '../components/researchTools.css'

export function EdgeReview({ runId: selected }: { runId?: string | null }) {
  const linked = useLinked()
  const runId = selected === undefined ? linked.runId : selected
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [native, setNative] = useState<NativeTearSheetProjection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyticsError, setAnalyticsError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let live = true
    setDetail(null); setNative(null); setError(null); setAnalyticsError(null)
    if (!runId) return
    api.run(runId).then(result => {
      if (!live) return
      setDetail(result)
      if (result.has_equity) api.nativeTearsheet(runId).then(value => { if (live) setNative(value) }).catch(cause => { if (live) setAnalyticsError(String(cause)) })
    }).catch(cause => { if (live) setError(String(cause)) })
    return () => { live = false }
  }, [runId, attempt])
  return <section className="edge-review" aria-label="Edge review">
    <h2>Edge review</h2>
    {!runId ? <p>Select a recorded run to review its evidence.</p> : error ? <div role="alert">{error}<button className="btn" onClick={() => setAttempt(value => value + 1)}>Retry edge review</button></div> : !detail || detail.run_id !== runId ? <p role="status">Loading recorded evidence…</p> : <>
      <h3>{detail.display_name}</h3><p className="mono">Run {detail.run_id}</p>
      {detail.run_context_watermark ? <p>{detail.run_context_watermark}</p> : null}
      {detail.research_gate_watermark ? <p>{detail.research_gate_watermark}</p> : null}
      <dl>{edgeReviewRows(detail.manifest, native).map(row => <Fragment key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></Fragment>)}</dl>
      {analyticsError ? <p role="alert">Native analytics unavailable: {analyticsError}<button className="btn" onClick={() => setAttempt(value => value + 1)}>Retry analytics</button></p> : null}
      <p className="muted">Returns and validation are the recorded backend results. Fee and slippage assumptions are not realized cost totals. No missing metric is estimated, and this summary grants no research or trading approval.</p>
    </>}
  </section>
}
