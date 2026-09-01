import { describe, expect, it } from 'vitest'

import type { JobSummary } from '../api/types'
import { formatJobDuration, jobProgressView } from './jobProgress'

const job = (overrides: Partial<JobSummary> = {}): JobSummary => ({
  job_id: 'job-1',
  command: 'forecast eval AMZN --horizon 21',
  command_path: 'forecast eval',
  kind: 'forecast',
  status: 'running',
  created_at: 1_000,
  finished_at: null,
  elapsed_seconds: 120,
  current_step: 'Running alpha forecast eval',
  progress_mode: 'indeterminate',
  progress_fraction: null,
  eta_seconds: null,
  eta_sample_count: 0,
  run_id: null,
  session_id: null,
  returncode: null,
  n_lines: 0,
  ...overrides,
})

describe('job progress model', () => {
  it('formats exact elapsed durations compactly', () => {
    expect(formatJobDuration(9.9)).toBe('9s')
    expect(formatJobDuration(125)).toBe('2m 05s')
    expect(formatJobDuration(3_661)).toBe('1h 01m')
  })

  it('keeps first-time work explicitly indeterminate', () => {
    const view = jobProgressView(job(), 1_150)
    expect(view.elapsedLabel).toBe('2m 30s')
    expect(view.etaLabel).toBe('estimating…')
    expect(view.fraction).toBeNull()
    expect(view.estimateBasis).toContain('first comparable')
  })

  it('advances an estimate from completed comparable jobs without claiming certainty', () => {
    const view = jobProgressView(
      job({ progress_mode: 'estimated', eta_seconds: 180, eta_sample_count: 3 }),
      1_180,
    )
    expect(view.etaLabel).toBe('~2 min')
    expect(view.fraction).toBeCloseTo(0.6)
    expect(view.estimateBasis).toContain('median of 3')
  })

  it('uses the recorded duration and a full terminal bar after completion', () => {
    const view = jobProgressView(
      job({ status: 'done', elapsed_seconds: 83, progress_mode: 'terminal', finished_at: 1_083 }),
      2_000,
    )
    expect(view.elapsedLabel).toBe('1m 23s')
    expect(view.etaLabel).toBe('complete')
    expect(view.fraction).toBe(1)
  })
  it('shows the server failure message as the failed row detail', () => {
    const message = 'Invalid value: --start/--end must be YYYY-MM-DD: day is out of range for month'
    const view = jobProgressView(
      job({ status: 'failed', progress_mode: 'terminal', finished_at: 1_083, current_step: message }),
      1_100,
    )
    expect(view.currentStep).toBe(message)
  })
})
