// Rows for the one dense jobs table (artboard 1-Terminal: Time · Job · Status · Detail · ✓):
// ordering and every cell string, so the panel only lays them out. The current step is relayed
// exactly — a failed job's CLI message is its `now` cell, shown under Detail.

import type { JobSummary } from '../api/types'
import { fmtTime } from '../util/format'
import { jobProgressView } from './jobProgress'

export interface JobRow {
  jobId: string
  status: string
  statusTone: 'pass' | 'kind' | 'fail'
  command: string
  /** `HH:MM:SS` UTC the job was created — the Time column. */
  time: string
  /** The command without the `alpha` prefix — the Job column. */
  job: string
  done: boolean
  started: string
  elapsed: string
  eta: string
  etaBasis: string
  fraction: number | null
  progressName: string
  now: string
  lines: number
  runId: string | null
  cancellable: boolean
}

export function jobRows(jobs: JobSummary[], nowSeconds: number): JobRow[] {
  return [...jobs]
    .sort(
      (left, right) =>
        Number(right.status === 'running') - Number(left.status === 'running')
        || right.created_at - left.created_at,
    )
    .map((job) => {
      const progress = jobProgressView(job, nowSeconds)
      return {
        jobId: job.job_id,
        status: job.status,
        statusTone: job.status === 'done' ? 'pass' : job.status === 'running' ? 'kind' : 'fail',
        command: `alpha ${job.command}`,
        time: new Date(job.created_at * 1_000).toISOString().slice(11, 19),
        job: job.command,
        done: job.status === 'done',
        started: fmtTime(job.created_at),
        elapsed: progress.elapsedLabel,
        eta: progress.etaLabel,
        etaBasis: progress.estimateBasis,
        fraction: progress.fraction,
        progressName: `Job ${progress.commandPath} progress`,
        now: progress.currentStep,
        lines: job.n_lines,
        runId: job.run_id,
        cancellable: job.status === 'running',
      }
    })
}
