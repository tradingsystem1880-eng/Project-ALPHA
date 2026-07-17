// Live job console — streams a launched `alpha` run's output over SSE, links to the finished run,
// and can cancel a running job. Shared by Strategy Lab and the AI Console.

import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'

type Status = 'running' | 'done' | 'failed' | 'cancelled'

interface Props {
  jobId: string
  onRun?: (runId: string) => void
}

export function JobConsole({ jobId, onRun }: Props) {
  const [lines, setLines] = useState<string[]>([])
  const [status, setStatus] = useState<Status>('running')
  const [runId, setRunId] = useState<string | null>(null)
  const preRef = useRef<HTMLPreElement>(null)
  const onRunRef = useRef(onRun)
  onRunRef.current = onRun

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
      es.close()
    })
    es.addEventListener('failed', () => {
      setStatus('failed')
      es.close()
    })
    es.addEventListener('cancelled', () => {
      setStatus('cancelled')
      es.close()
    })
    es.onerror = () => es.close()
    return () => es.close()
  }, [jobId])

  useEffect(() => {
    const pre = preRef.current
    if (pre) pre.scrollTop = pre.scrollHeight
  }, [lines])

  return (
    <div className="console">
      <div className="console-status">
        <span className={`dot ${status === 'running' ? 'busy' : ''}`} />
        <span className="mono">{status}</span>
        {status === 'running' ? (
          <button className="btn" onClick={() => void api.cancel(jobId)}>
            cancel
          </button>
        ) : null}
        {runId ? (
          <button className="btn primary" onClick={() => onRunRef.current?.(runId)}>
            open run {runId.slice(0, 8)}
          </button>
        ) : null}
      </div>
      <pre ref={preRef} className={`console-out ${status}`}>
        {lines.join('\n')}
      </pre>
    </div>
  )
}
