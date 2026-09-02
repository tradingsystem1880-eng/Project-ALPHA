import { describe, expect, it } from 'vitest'

import type { JobSummary } from '../api/types'
import { jobRows } from './jobTableModel'

const job = (overrides: Partial<JobSummary> = {}): JobSummary => ({
  job_id: 'job-1',
  command: 'forecast eval AMZN --horizon 21',
  command_path: 'forecast eval',
  kind: 'forecast',
  status: 'running',
  created_at: 1_000,
  finished_at: null,
  elapsed_seconds: 120,
  current_step: 'Evaluating rolling forecast origin 8 of 20',
  progress_mode: 'estimated',
  progress_fraction: 0.4,
  eta_seconds: 180,
  eta_sample_count: 3,
  run_id: null,
  session_id: null,
  returncode: null,
  n_lines: 14,
  ...overrides,
})

describe('jobRows', () => {
  it('puts running jobs first, then newest first', () => {
    const rows = jobRows(
      [
        job({ job_id: 'old-done', status: 'done', created_at: 10 }),
        job({ job_id: 'new-done', status: 'done', created_at: 30 }),
        job({ job_id: 'run', status: 'running', created_at: 20 }),
      ],
      1_120,
    )
    expect(rows.map((row) => row.jobId)).toEqual(['run', 'new-done', 'old-done'])
  })

  it('relays the current step exactly — a failure message is the now cell', () => {
    const message = 'No data for XRP/USDT on binance before 2018-05-04 (first listed).'
    const [row] = jobRows(
      [job({ status: 'failed', progress_mode: 'terminal', current_step: message, returncode: 2 })],
      1_120,
    )
    expect(row.now).toBe(message)
    expect(row.statusTone).toBe('fail')
    expect(row.eta).toBe('complete')
    expect(row.cancellable).toBe(false)
  })

  it('carries elapsed, ETA, progress fraction and the accessible name for a running job', () => {
    const [row] = jobRows([job()], 1_120)
    expect(row.statusTone).toBe('kind')
    expect(row.elapsed).toBe('2m 00s')
    expect(row.eta).toBe('~3 min')
    expect(row.fraction).toBeCloseTo(0.4, 5)
    expect(row.progressName).toBe('Job forecast eval progress')
    expect(row.cancellable).toBe(true)
    expect(row.command).toBe('alpha forecast eval AMZN --horizon 21')
  })
})
