// Job Monitor — every job this server session has run, one dense table (artboard 1-Terminal:
// Time · Job · Status · Detail · ✓), live-updating; expand a row to attach its streaming console
// beneath it (consoles are global, not trapped in the launching panel). Detail carries the
// progress bar, elapsed and ETA for a running job and the CLI's own message for a failed one.

import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { JobSummary } from '../api/types'
import { JobConsole } from '../components/JobConsole'
import { Placeholder } from '../components/Placeholder'
import { useActivityField } from '../state/activity'
import { shortId } from '../util/format'
import { openRunDetail } from './actions'
import { isDataJob, jobRows } from './jobTableModel'
import type { PanelHandleProps } from '../context/panelHandle'

export function DataPulls(props: PanelHandleProps) {
  return <JobMonitor {...props} only="data" />
}

export function JobMonitor({ only }: PanelHandleProps & { only?: 'data' }) {
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

  const toggle = (jobId: string) => setOpen((current) => (current === jobId ? null : jobId))

  return (
    <div className="panel jobs-panel">
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
          <table className="blotter jobs-table">
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Job</th>
                <th scope="col">Status</th>
                <th scope="col" className="r">Elapsed</th>
                <th scope="col" className="r">ETA</th>
                <th scope="col">Progress</th>
                <th scope="col">Detail</th>
                <th scope="col" aria-label="Done">✓</th>
              </tr>
            </thead>
            <tbody>
              {jobRows(only === 'data' ? jobs.filter((job) => isDataJob(job.command)) : jobs, nowSeconds).flatMap((row) => {
                const isOpen = open === row.jobId
                const rows = [
                  <tr key={row.jobId} className={isOpen ? 'sel' : undefined} onClick={() => toggle(row.jobId)}>
                    <td className="num muted" title={row.started}>
                      {row.time}
                    </td>
                    <td className="mono job-cmd" title={row.command}>
                      {row.job}
                    </td>
                    <td>
                      <span className={`chip ${row.statusTone}`}>{row.status}</span>
                    </td>
                    <td className="num">{row.elapsed}</td>
                    <td className="num" title={row.etaBasis}>
                      {row.eta}
                    </td>
                    <td>
                      <div
                        className={`job-progress-track ${row.fraction === null ? 'indeterminate' : ''} status-${row.status}`}
                        role="progressbar"
                        aria-label={row.progressName}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={row.fraction === null ? undefined : Math.round(row.fraction * 100)}
                        aria-valuetext={row.fraction === null ? `Elapsed ${row.elapsed}; ETA estimating` : `Elapsed ${row.elapsed}; ETA ${row.eta}`}
                      >
                        <span style={row.fraction === null ? undefined : { width: `${row.fraction * 100}%` }} />
                      </div>
                    </td>
                    <td className={`now${row.statusTone === 'fail' ? ' neg' : ''}`} title={row.now}>
                      {row.now}
                    </td>
                    <td className="actions">
                      {row.done ? <span className="job-done" title="finished">✓</span> : null}
                      {row.runId ? (
                        <button
                          className="btn primary"
                          onClick={(e) => {
                            e.stopPropagation()
                            openRunDetail(row.runId!)
                          }}
                        >
                          run {shortId(row.runId)}
                        </button>
                      ) : null}
                      <button
                        className="btn job-expand"
                        onClick={(event) => {
                          event.stopPropagation()
                          toggle(row.jobId)
                        }}
                        aria-expanded={isOpen}
                      >
                        {isOpen ? 'hide log' : 'live log'}
                      </button>
                      {row.cancellable ? (
                        <button
                          className="btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            void api.cancel(row.jobId)
                          }}
                        >
                          cancel
                        </button>
                      ) : null}
                    </td>
                  </tr>,
                ]
                if (isOpen) {
                  rows.push(
                    <tr key={`${row.jobId}:console`} className="console-row">
                      <td colSpan={8}>
                        <JobConsole jobId={row.jobId} onRun={(rid) => openRunDetail(rid)} embedded />
                      </td>
                    </tr>,
                  )
                }
                return rows
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
