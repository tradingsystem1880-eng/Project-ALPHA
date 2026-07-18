// Completion toasts: any run landing in the store (from the UI, the CLI, or Claude over MCP)
// raises a dismissable toast with an open-run action. Hosted once in the shell.

import { useEffect, useRef, useState } from 'react'

import type { RunListItem } from '../api/types'
import { useActivity } from '../state/activity'
import { shortId } from '../util/format'

interface Toast {
  id: number
  title: string
  detail: string
  runId?: string
  tone: 'good' | 'bad' | 'info'
}

const TOAST_MS = 9000

export function Toasts({ onOpenRun }: { onOpenRun: (runId: string) => void }) {
  const { feed } = useActivity()
  const [toasts, setToasts] = useState<Toast[]>([])
  const lastSeq = useRef(0)

  useEffect(() => {
    const fresh = feed.filter((e) => e.seq > lastSeq.current)
    if (!fresh.length) return
    lastSeq.current = feed[0]?.seq ?? lastSeq.current
    const next: Toast[] = []
    for (const e of fresh) {
      if (e.type === 'run_added' && e.run) {
        const r: RunListItem = e.run
        next.push({
          id: e.seq,
          title: `run ${shortId(r.run_id)} · ${r.kind}`,
          detail: `${r.label ?? ''}${r.verdict ? ` — verdict ${r.verdict}` : ''}${r.passed === false ? ' — FAILED gates' : r.passed === true ? ' — passed' : ''}`,
          runId: r.run_id,
          tone: r.passed === false ? 'bad' : 'good',
        })
      } else if (e.type === 'job_failed' && e.job) {
        next.push({
          id: e.seq,
          title: `job failed`,
          detail: e.job.command ?? '',
          tone: 'bad',
        })
      }
    }
    if (!next.length) return
    setToasts((t) => [...next, ...t].slice(0, 4))
    for (const t of next) {
      window.setTimeout(() => setToasts((all) => all.filter((x) => x.id !== t.id)), TOAST_MS)
    }
  }, [feed])

  if (!toasts.length) return null
  return (
    <div className="toasts">
      {toasts.map((t) => (
        <div key={t.id} className={`toast tone-${t.tone}`}>
          <div className="toast-body">
            <span className="toast-title mono">{t.title}</span>
            <span className="toast-detail">{t.detail}</span>
          </div>
          {t.runId ? (
            <button className="btn primary" onClick={() => onOpenRun(t.runId!)}>
              open
            </button>
          ) : null}
          <button
            className="btn ghost"
            onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
