// Job Monitor — every job this server session has run, live-updating; expand a row to attach
// its streaming console (consoles are global now, not trapped in the launching panel).

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { JobSummary } from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { Placeholder } from '../components/Placeholder'
import { useActivityField } from '../state/activity'
import { fmtTime, shortId } from '../util/format'
import { openRunDetail } from './actions'
import { jobProgressView } from './jobProgress'
import type { PanelHandleProps } from '../context/panelHandle'

export function JobMonitor(_props: PanelHandleProps) {
  const jobsVersion = useActivityField('jobsVersion')
  const runningJobs = useActivityField('runningJobs')
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nowSeconds, setNowSeconds] = useState(() => Date.now() / 1000)

  const loadJobs = useCallback(() => {
    let live = true
    api
      .jobs()
      .then((j) => {
        if (live) {
          setJobs(j)
          setError(null)
        }
      })
      .catch((e: unknown) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [])

  useEffect(() => {
    return loadJobs()
  }, [jobsVersion, loadJobs])

  useEffect(() => {
    if (!jobs?.some((job) => job.status === 'running')) return
    const timer = window.setInterval(() => {
      setNowSeconds(Date.now() / 1000)
    }, 1_000)
    const poll = window.setInterval(loadJobs, 3_000)
    return () => {
      window.clearInterval(timer)
      window.clearInterval(poll)
    }
  }, [jobs, loadJobs])

  const orderedJobs = jobs
    ? [...jobs].sort(
        (left, right) =>
          Number(right.status === 'running') - Number(left.status === 'running') ||
          right.created_at - left.created_at,
      )
    : null

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
            {orderedJobs!.map((j) => {
              const progress = jobProgressView(j, nowSeconds)
              return (
                <div key={j.job_id} className="job-row-wrap">
                <div
                  className={`job-row ${open === j.job_id ? 'open' : ''}`}
                  onClick={() => setOpen(open === j.job_id ? null : j.job_id)}
                >
                  <div className="job-primary">
                    <span
                      className={`dot ${j.status === 'running' ? 'busy' : j.status === 'done' ? '' : 'down'}`}
                    />
                    <span className={`chip ${j.status === 'done' ? 'pass' : j.status === 'running' ? 'kind' : 'fail'}`}>
                      {j.status}
                    </span>
                    <span className="mono job-cmd">alpha {j.command}</span>
                    <span className="num muted job-started">{fmtTime(j.created_at)}</span>
                    {j.run_id ? (
                      <button
                        className="btn primary"
                        onClick={(e) => {
                          e.stopPropagation()
                          openRunDetail(j.run_id!)
                        }}
                      >
                        run {shortId(j.run_id)}
                      </button>
                    ) : null}
                    <button
                      className="btn job-expand"
                      onClick={(event) => {
                        event.stopPropagation()
                        setOpen(open === j.job_id ? null : j.job_id)
                      }}
                      aria-expanded={open === j.job_id}
                    >
                      {open === j.job_id ? 'hide log' : 'live log'}
                    </button>
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
                  <div className="job-progress-meta">
                    <span><b>Elapsed</b> <span className="num">{progress.elapsedLabel}</span></span>
                    <span title={progress.estimateBasis}><b>ETA</b> <span className="num">{progress.etaLabel}</span></span>
                    <span><b>Output</b> <span className="num">{j.n_lines} lines</span></span>
                    <span className="job-current-step" title={progress.currentStep}><b>Now</b> {progress.currentStep}</span>
                  </div>
                  <div
                    className={`job-progress-track ${progress.fraction === null ? 'indeterminate' : ''} status-${j.status}`}
                    role="progressbar"
                    aria-label={`Job ${progress.commandPath} progress`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progress.fraction === null ? undefined : Math.round(progress.fraction * 100)}
                    aria-valuetext={progress.fraction === null ? `Elapsed ${progress.elapsedLabel}; ETA estimating` : `Elapsed ${progress.elapsedLabel}; ETA ${progress.etaLabel}`}
                  >
                    <span style={progress.fraction === null ? undefined : { width: `${progress.fraction * 100}%` }} />
                  </div>
                </div>
                {open === j.job_id ? (
                  <JobConsole
                    jobId={j.job_id}
                    onRun={(rid) => openRunDetail(rid)}
                    embedded
                  />
                ) : null}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
