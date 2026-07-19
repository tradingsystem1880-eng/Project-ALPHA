// Durable sandbox paper-session monitor. Sessions live outside deterministic research runs; this
// panel polls the low-volume journal, incrementally tails events, and cancels only the web job
// explicitly linked by session_id. A stale heartbeat is surfaced, never used as a PID-kill signal.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type {
  JsonScalar,
  PaperEvent,
  PaperJobSummary,
  PaperSession,
  SystemStatus,
} from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { shortId } from '../util/format'
import {
  eventSummary,
  latestPosition,
  matchingRunningJob,
  mergePaperEvents,
  nextEventCursor,
  paperDetailState,
  paperOverviewState,
  paperStatusTone,
} from './paperModel'

const OVERVIEW_POLL_MS = 4_000
const SESSION_POLL_MS = 2_000

function displayTime(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString()
}

function scalarText(value: JsonScalar): string {
  return value === null ? '—' : String(value)
}

function SessionList({
  sessions,
  selected,
  onSelect,
}: {
  sessions: PaperSession[]
  selected: string | null
  onSelect: (sessionId: string) => void
}) {
  if (!sessions.length) {
    return (
      <Placeholder big="no paper sessions">
        Opt in with <code>ALPHA_PAPER_ENABLED=true</code>, then launch <code>alpha paper run</code>.
      </Placeholder>
    )
  }
  return (
    <div className="paper-session-list">
      {sessions.map((session) => (
        <button
          className={`paper-session-row ${selected === session.session_id ? 'selected' : ''}`}
          key={session.session_id}
          onClick={() => onSelect(session.session_id)}
        >
          <span
            className={`dot ${
              session.stale || session.status === 'failed' || session.status === 'cancelled'
                ? 'down'
                : ['starting', 'running', 'stopping'].includes(session.status)
                  ? 'busy'
                  : ''
            }`}
          />
          <span className={`chip ${paperStatusTone(session.status)}`}>{session.status}</span>
          <span className="mono paper-session-symbol">{session.symbol}</span>
          <span className="mono muted">{session.strategy}</span>
          {session.stale ? <span className="chip fail">STALE</span> : null}
          <span className="spacer" />
          <span className="mono muted">{shortId(session.session_id)}</span>
        </button>
      ))}
    </div>
  )
}

function PositionSummary({ position }: { position: Record<string, JsonScalar> | null }) {
  if (!position) return <div className="muted">No position event recorded.</div>
  const entries = Object.entries(position)
  if (!entries.length) return <div className="muted">Latest position payload is empty.</div>
  return (
    <div className="metric-grid paper-position-grid">
      {entries.map(([name, value]) => (
        <div className="metric" key={name}>
          <span className="eyebrow">{name.replaceAll('_', ' ')}</span>
          <span className="metric-val mono">{scalarText(value)}</span>
        </div>
      ))}
    </div>
  )
}

function EventBlotter({ events }: { events: PaperEvent[] }) {
  const orderEvents = events.filter((event) =>
    ['order', 'fill', 'rejection'].includes(event.event_type),
  )
  if (!orderEvents.length) return <div className="muted">No order, fill, or rejection events.</div>
  return (
    <table className="blotter">
      <thead>
        <tr>
          <th className="r">Seq</th>
          <th>Recorded</th>
          <th>Type</th>
          <th>Event</th>
        </tr>
      </thead>
      <tbody>
        {orderEvents.map((event) => (
          <tr key={event.sequence}>
            <td className="num">{event.sequence}</td>
            <td className="mono muted">{displayTime(event.recorded_at)}</td>
            <td>
              <span className={`chip ${event.event_type === 'rejection' ? 'fail' : 'kind'}`}>
                {event.event_type}
              </span>
            </td>
            <td className="mono">{eventSummary(event)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EventLog({ events }: { events: PaperEvent[] }) {
  if (!events.length) return <div className="muted">No journal events yet.</div>
  return (
    <pre className="console-out paper-log">
      {events
        .map(
          (event) =>
            `${String(event.sequence).padStart(6, '0')} ${event.recorded_at} ${event.event_type.toUpperCase()} ${eventSummary(event)}`,
        )
        .join('\n')}
    </pre>
  )
}

export function PaperMonitor() {
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [sessions, setSessions] = useState<PaperSession[] | null>(null)
  const [jobs, setJobs] = useState<PaperJobSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [session, setSession] = useState<PaperSession | null>(null)
  const [events, setEvents] = useState<PaperEvent[]>([])
  const [overviewError, setOverviewError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const eventCursor = useRef(0)

  const loadOverview = useCallback(() => {
    void Promise.all([api.system(), api.paperSessions(), api.jobs()])
      .then(([status, journal, jobList]) => {
        setSystem(status)
        setSessions(journal)
        setJobs(jobList)
        setOverviewError(null)
        setSelectedId((current) => {
          if (current && journal.some((item) => item.session_id === current)) return current
          return journal[0]?.session_id ?? null
        })
      })
      .catch((reason: unknown) => setOverviewError(String(reason)))
  }, [])

  useEffect(() => {
    loadOverview()
    const timer = window.setInterval(loadOverview, OVERVIEW_POLL_MS)
    return () => window.clearInterval(timer)
  }, [loadOverview])

  useEffect(() => {
    eventCursor.current = 0
    setEvents([])
    setSession(null)
    setDetailError(null)
    if (!selectedId) return
    let live = true
    const poll = (): void => {
      const cursor = eventCursor.current
      void Promise.all([api.paperSession(selectedId), api.paperEvents(selectedId, cursor)])
        .then(([currentSession, nextEvents]) => {
          if (!live) return
          setSession(currentSession)
          setEvents((current) => {
            const merged = mergePaperEvents(current, nextEvents)
            eventCursor.current = nextEventCursor(merged)
            return merged
          })
          setDetailError(null)
        })
        .catch((reason: unknown) => live && setDetailError(String(reason)))
    }
    poll()
    const timer = window.setInterval(poll, SESSION_POLL_MS)
    return () => {
      live = false
      window.clearInterval(timer)
    }
  }, [selectedId])

  const position = useMemo(() => latestPosition(events), [events])
  const runningJob = session ? matchingRunningJob(jobs, session.session_id) : null
  const overviewState = paperOverviewState(system, sessions, overviewError)
  const detailState = paperDetailState(selectedId, session, detailError)

  async function cancelSession(): Promise<void> {
    if (!runningJob) return
    setCancelling(true)
    setCancelError(null)
    try {
      const response = await api.cancel(runningJob.job_id)
      if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
      loadOverview()
    } catch (reason) {
      setCancelError(String(reason))
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Paper Monitor</span>
        {system ? (
          <span className={`chip ${system.paper_enabled ? 'pass' : 'fail'}`}>
            {system.paper_enabled ? 'ENABLED' : 'DISABLED'}
          </span>
        ) : null}
        {sessions ? <span className="count">{sessions.length} sessions</span> : null}
        <div className="spacer" />
        <span className="muted mono">event cursor {eventCursor.current}</span>
        <button className="btn" onClick={loadOverview}>
          refresh
        </button>
      </div>
      <div className="sandbox-banner" role="status">
        SANDBOX · PUBLIC BINANCE DATA · NO REAL ORDER ROUTING · SANDBOX
      </div>
      <div className="panel-body paper-monitor" data-state={overviewState}>
        {overviewError ? <div className="leak paper-overview-error">⚠ {overviewError}</div> : null}
        {system && !system.paper_enabled ? (
          <div className="paper-disabled">
            <strong>PAPER DISABLED</strong>
            <span>
              Set <code>ALPHA_PAPER_ENABLED=true</code> explicitly before launching a new session.
              Historical journals remain readable.
            </span>
          </div>
        ) : null}
        <section className="paper-sessions">
          <div className="rd-head">Sessions</div>
          {sessions === null ? (
            <Placeholder>loading sessions…</Placeholder>
          ) : (
            <SessionList sessions={sessions} selected={selectedId} onSelect={setSelectedId} />
          )}
        </section>
        {detailError ? (
          <Placeholder big="session unavailable">{detailError}</Placeholder>
        ) : !selectedId ? null : session === null ? (
          <Placeholder>loading session journal…</Placeholder>
        ) : (
          <div className="paper-detail" data-state={detailState}>
            {session.stale ? (
              <div className="paper-stale">
                STALE HEARTBEAT · last observed {displayTime(session.heartbeat_at)} · recorded PID will
                not be killed automatically
              </div>
            ) : null}
            {session.terminal_error ? <div className="leak">⚠ {session.terminal_error}</div> : null}
            {cancelError ? <div className="leak">⚠ cancel failed: {cancelError}</div> : null}
            <section>
              <div className="paper-detail-head">
                <div className="rd-head">Session status</div>
                <button
                  className="btn"
                  disabled={!runningJob || cancelling}
                  onClick={() => void cancelSession()}
                  title={
                    runningJob
                      ? `Cancel linked web job ${runningJob.job_id}`
                      : 'No running web job is linked to this session'
                  }
                >
                  {cancelling ? 'cancelling…' : 'cancel session'}
                </button>
              </div>
              <div className="meta-grid paper-meta">
                <div>
                  <span className="eyebrow">Status</span>
                  <div>
                    <span className={`chip ${paperStatusTone(session.status)}`}>
                      {session.status}
                    </span>
                  </div>
                </div>
                <div>
                  <span className="eyebrow">Symbol · instrument</span>
                  <div className="mono">{session.symbol} · {session.instrument_id}</div>
                </div>
                <div>
                  <span className="eyebrow">Strategy</span>
                  <div className="mono">{session.strategy}</div>
                </div>
                <div>
                  <span className="eyebrow">Provider</span>
                  <div className="mono">{session.provider} · SANDBOX</div>
                </div>
                <div>
                  <span className="eyebrow">Snapshot</span>
                  <div className="mono">{session.snapshot_id}</div>
                </div>
                <div>
                  <span className="eyebrow">Heartbeat</span>
                  <div className={`mono ${session.stale ? 'neg' : 'pos'}`}>
                    {displayTime(session.heartbeat_at)}
                  </div>
                </div>
                <div>
                  <span className="eyebrow">Started</span>
                  <div className="mono">{displayTime(session.started_at)}</div>
                </div>
                <div>
                  <span className="eyebrow">Ended</span>
                  <div className="mono">{displayTime(session.ended_at)}</div>
                </div>
                <div>
                  <span className="eyebrow">Process</span>
                  <div className="mono">PID {session.pid ?? '—'}</div>
                </div>
                <div>
                  <span className="eyebrow">Parameters</span>
                  <div className="mono paper-json">{JSON.stringify(session.strategy_params)}</div>
                </div>
              </div>
            </section>
            <section>
              <div className="rd-head">Position summary</div>
              <PositionSummary position={position} />
            </section>
            <section>
              <div className="rd-head">Order event blotter</div>
              <div className="paper-blotter-scroll">
                <EventBlotter events={events} />
              </div>
            </section>
            <section>
              <div className="rd-head">Session log · lifecycle and execution journal</div>
              <EventLog events={events} />
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
