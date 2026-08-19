// Live job console — streams a launched `alpha` run's output over SSE, links to the finished run,
// and can cancel a running job. Shared by Strategy Lab and the AI Console.

import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import { shortId } from '../util/format'

type Status = 'running' | 'done' | 'failed' | 'cancelled'

interface Props {
  jobId: string
  onRun?: (runId: string) => void
  onDone?: () => void
  embedded?: boolean
}

export function JobConsole({ jobId, onRun, onDone, embedded = false }: Props) {
  const [lines, setLines] = useState<string[]>([])
  const [status, setStatus] = useState<Status>('running')
  const [runId, setRunId] = useState<string | null>(null)
  const preRef = useRef<HTMLPreElement>(null)
  const onRunRef = useRef(onRun)
  onRunRef.current = onRun
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    setLines([])
    setStatus('running')
    setRunId(null)
    const es = new EventSource(api.streamUrl(jobId))
    es.addEventListener('line', (e) => setLines((l) => [...l, (e as MessageEvent<string>).data]))
    es.addEventListener('done', (e) => {
      const rid = (e as MessageEvent<string>).data
      setStatus('done')
      if (rid) {
        setRunId(rid)
        onRunRef.current?.(rid)
      }
      onDoneRef.current?.()
      es.close()
    })
    es.addEventListener('failed', () => {
      setStatus('failed')
      onDoneRef.current?.()
      es.close()
    })
    es.addEventListener('cancelled', () => {
      setStatus('cancelled')
      onDoneRef.current?.()
      es.close()
    })
    // Don't close on a transient error — let EventSource auto-reconnect; it resends Last-Event-ID
    // so the backend replays only the lines missed (a terminal event above already closed us).
    return () => es.close()
  }, [jobId])

  useEffect(() => {
    const pre = preRef.current
    if (pre) pre.scrollTop = pre.scrollHeight
  }, [lines])

  return (
    <div className="console">
      <div className="console-status">
        {embedded ? <span className="title">Live output</span> : <span className={`dot ${status === 'running' ? 'busy' : ''}`} />}
        <span className="mono">{embedded ? `${lines.length} lines` : status}</span>
        {!embedded && status === 'running' ? (
          <button className="btn" onClick={() => void api.cancel(jobId)}>
            cancel
          </button>
        ) : null}
        {runId ? (
          <button className="btn primary" onClick={() => onRunRef.current?.(runId)}>
            open run {shortId(runId)}
          </button>
        ) : null}
      </div>
      <pre ref={preRef} className={`console-out ${status}`}>
        {lines.length > 0
          ? lines.join('\n')
          : 'Waiting for process output… Runtime and job heartbeat remain visible above.'}
      </pre>
    </div>
  )
}
