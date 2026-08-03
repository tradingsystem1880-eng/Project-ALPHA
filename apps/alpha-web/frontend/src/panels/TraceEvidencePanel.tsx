import { useEffect, useMemo, useState } from 'react'

import type { ChartBundle, ChartTraceEvent } from '../api/types'
import { CHART_TRACE_PAGE_SIZE, chartTracePage } from './chartTableModel'
import { evidenceForDecision } from './v3Models'

function utc(ts: number | null): string {
  return ts === null ? '—' : new Date(ts * 1_000).toISOString().replace('.000Z', 'Z')
}

function eventPrice(event: ChartTraceEvent): number | null {
  return event.price ?? event.exit_price ?? event.entry_price
}

export function TraceEvidencePanel({
  bundle,
  selected,
  selectedSequenceId,
  onSelectEvidence,
}: {
  bundle: ChartBundle
  selected: ChartTraceEvent | null
  selectedSequenceId: number | null
  onSelectEvidence: (sequenceId: number) => void
}) {
  const [page, setPage] = useState(0)
  const window = useMemo(() => chartTracePage(bundle.trace, page), [bundle.trace, page])
  const decisionEvidence = useMemo(
    () => evidenceForDecision(bundle, selected?.sequence_id ?? -1),
    [bundle, selected],
  )

  useEffect(() => setPage(0), [bundle.run_id])
  useEffect(() => {
    if (selectedSequenceId === null) return
    const index = bundle.trace.findIndex((event) => event.sequence_id === selectedSequenceId)
    if (index >= 0) setPage(Math.floor(index / CHART_TRACE_PAGE_SIZE))
  }, [bundle.trace, selectedSequenceId])

  return (
    <div className="trace-strip">
      <div className="trace-list-column">
        <div className="trace-page-toolbar mono">
          <button
            className="btn"
            aria-label="Previous trace page"
            disabled={window.page === 0}
            onClick={() => setPage((value) => Math.max(0, value - 1))}
          >
            Previous
          </button>
          <span aria-live="polite">
            {window.start}–{window.end} / {window.total} RETURNED EVENTS · PAGE {window.page + 1}/{window.pages}
          </span>
          <button
            className="btn"
            aria-label="Next trace page"
            disabled={window.page >= window.pages - 1}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </button>
          <span className={bundle.truncated.trace ? 'chart-bound-warning' : 'muted'}>
            {bundle.truncated.trace
              ? 'BACKEND PROJECTION TRUNCATED · MORE TRACE EVENTS EXIST'
              : 'RETURNED WINDOW COMPLETE'}
          </span>
        </div>
        <div className="trace-strip-list" role="group" aria-label="Causal trace events">
          {window.rows.map((event) => (
            <button
              key={event.sequence_id}
              className={`trace-event${event.sequence_id === selectedSequenceId ? ' selected' : ''}`}
              onClick={() => onSelectEvidence(event.sequence_id)}
              title={event.decision_reason ?? event.status ?? event.event_type}
            >
              <span className="trace-seq mono">{String(event.sequence_id).padStart(4, '0')}</span>
              <span className={`trace-kind ${event.event_type}`}>{event.event_type}</span>
              <span className="mono">{utc(event.ts)}</span>
              <span className="mono">
                {event.side ?? (event.signal === null ? '—' : `signal ${event.signal}`)}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="trace-inspector" aria-live="polite" tabIndex={0} aria-label="Selected causal event inspector">
        {selected ? (
          <>
            <div><span className="eyebrow">event</span><span className="mono">{selected.event_type} · #{selected.sequence_id}</span></div>
            <div><span className="eyebrow">exact UTC</span><span className="mono">{utc(selected.ts)}</span></div>
            <div><span className="eyebrow">price / qty</span><span className="mono">{eventPrice(selected)?.toFixed(4) ?? '—'} / {selected.filled_quantity ?? selected.quantity ?? '—'}</span></div>
            <div><span className="eyebrow">reason / status</span><span>{selected.decision_reason ?? selected.status ?? '—'}</span></div>
            <div><span className="eyebrow">causal indicators</span><span className="mono">{decisionEvidence.indicators.map((row) => `${row.name} ${row.value.toFixed(4)} ${row.unit}`).join(' · ') || '—'}</span></div>
            <div><span className="eyebrow">vector annotations</span><span>{decisionEvidence.annotations.map((row) => `${row.label}: ${row.reason}`).join(' · ') || '—'}</span></div>
          </>
        ) : (
          <span className="muted">Select a chart marker or trace row to inspect the exact artifact record.</span>
        )}
      </div>
    </div>
  )
}
