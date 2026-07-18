// Activity Feed — the desk tape: every run landing in the store and every job lifecycle change,
// live, regardless of origin (UI, CLI, Claude via MCP). Click a run event to open it.

import type { IDockviewPanelProps } from 'dockview-react'

import { Placeholder } from '../components/Placeholder'
import { useActivity, type ActivityEvent } from '../state/activity'
import { fmtTime, shortId } from '../util/format'
import { openRunDetail } from './actions'

const EVENT_LABEL: Record<ActivityEvent['type'], string> = {
  run_added: 'RUN',
  run_updated: 'UPD',
  job_started: 'JOB',
  job_done: 'END',
  job_failed: 'ERR',
  job_cancelled: 'CXL',
}

function eventTone(t: ActivityEvent['type']): string {
  if (t === 'run_added') return 'good'
  if (t === 'job_failed') return 'bad'
  if (t === 'job_cancelled') return 'warn'
  return 'info'
}

export function ActivityFeed(props: IDockviewPanelProps) {
  const { feed, connection } = useActivity()

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Activity</span>
        <span className={`chip ${connection === 'live' ? 'pass' : 'fail'}`}>{connection}</span>
        <span className="muted">everything hitting the store — UI, CLI, or Claude via MCP</span>
      </div>
      <div className="panel-body">
        {feed.length === 0 ? (
          <Placeholder big="quiet desk">
            Launch something — from the Strategy Lab, a terminal (<code>alpha validate SPY</code>),
            or Claude over MCP — and it appears here live.
          </Placeholder>
        ) : (
          <div className="feed">
            {feed.map((e) => (
              <button
                key={e.seq}
                className={`feed-row tone-${eventTone(e.type)}`}
                onClick={() => e.run && openRunDetail(props.containerApi, e.run.run_id)}
                disabled={!e.run}
              >
                <span className="feed-time num">{fmtTime(e.at).slice(11)}</span>
                <span className={`feed-tag mono t-${eventTone(e.type)}`}>{EVENT_LABEL[e.type]}</span>
                {e.run ? (
                  <>
                    <span className="mono">{shortId(e.run.run_id)}</span>
                    <span className="chip kind">{e.run.kind}</span>
                    <span className="mono">{e.run.label ?? ''}</span>
                    {e.run.verdict ? <span className={`verdict g-${e.run.verdict}`}>{e.run.verdict}</span> : null}
                    {e.run.passed !== null && e.run.passed !== undefined ? (
                      <span className={`chip ${e.run.passed ? 'pass' : 'fail'}`}>
                        {e.run.passed ? 'PASS' : 'FAIL'}
                      </span>
                    ) : null}
                  </>
                ) : e.job ? (
                  <span className="mono feed-cmd">{e.job.command}</span>
                ) : null}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
