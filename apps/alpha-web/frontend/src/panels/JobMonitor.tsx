// Job Monitor — every job this server session has run, live-updating; expand a row to attach
// its streaming console (consoles are global now, not trapped in the launching panel).

import type { IDockviewPanelProps } from 'dockview-react'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { JobSummary } from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { Placeholder } from '../components/Placeholder'
import { useActivityField } from '../state/activity'
import { fmtTime, shortId } from '../util/format'
import { openRunDetail } from './actions'

export function JobMonitor(props: IDockviewPanelProps) {
  const jobsVersion = useActivityField('jobsVersion')
  const runningJobs = useActivityField('runningJobs')
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .jobs()
      .then((j) => live && setJobs(j))
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [jobsVersion])

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Jobs</span>
        {runningJobs > 0 ? <span className="chip kind">{runningJobs} running</span> : null}
        <span className="muted">this server session · durable record lives in Runs</span>
      </div>
      <div className="panel-body">
        {error ? (
          <Placeholder big="error">{error}</Placeholder>
        ) : jobs === null ? (
          <Placeholder>loading…</Placeholder>
        ) : jobs.length === 0 ? (
          <Placeholder big="no jobs yet">Anything launched from the UI lands here.</Placeholder>
        ) : (
          <div className="jobs">
            {jobs.map((j) => (
              <div key={j.job_id} className="job-row-wrap">
                <div
                  className={`job-row ${open === j.job_id ? 'open' : ''}`}
                  onClick={() => setOpen(open === j.job_id ? null : j.job_id)}
                >
                  <span className={`dot ${j.status === 'running' ? 'busy' : ''}`} />
                  <span className={`chip ${j.status === 'done' ? 'pass' : j.status === 'running' ? 'kind' : 'fail'}`}>
                    {j.status}
                  </span>
                  <span className="mono job-cmd">alpha {j.command}</span>
                  <span className="num muted">{fmtTime(j.created_at)}</span>
                  {j.run_id ? (
                    <button
                      className="btn primary"
                      onClick={(e) => {
                        e.stopPropagation()
                        openRunDetail(props.containerApi, j.run_id!)
                      }}
                    >
                      run {shortId(j.run_id)}
                    </button>
                  ) : null}
                  {j.status === 'running' ? (
                    <button
                      className="btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        void api.cancel(j.job_id)
                      }}
                    >
                      cancel
                    </button>
                  ) : null}
                </div>
                {open === j.job_id ? (
                  <JobConsole
                    jobId={j.job_id}
                    onRun={(rid) => openRunDetail(props.containerApi, rid)}
                  />
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
