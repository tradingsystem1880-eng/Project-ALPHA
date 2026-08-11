import { describe, expect, it, vi } from 'vitest'

import type { ControlJob, ControlJobDetail } from '../api/types'
import { refreshDurableJobs } from './durableJobs'

function job(jobId: string, status: ControlJob['status']): ControlJob {
  return {
    job_id: jobId,
    kind: 'suite:baseline',
    status,
    project_id: 'project-1',
    experiment_id: 'experiment-1',
    request: {},
    result_run_id: null,
    terminal_error: null,
    created_at: '2026-07-20T00:00:00Z',
    updated_at: '2026-07-20T00:00:00Z',
    heartbeat_at: '2026-07-20T00:00:00Z',
    last_sequence: 1,
  }
}

function detail(summary: ControlJob): ControlJobDetail {
  return {
    ...summary,
    events: [],
    event_total: 1,
    event_limit: 100,
    event_offset: 0,
    event_tail: true,
    events_has_more: false,
    events_truncated: false,
  }
}

describe('durable development job recovery', () => {
  it('rehydrates every queued and running job through the detail endpoint after reload', async () => {
    const firstPage = [job('queued-1', 'queued'), job('done-1', 'succeeded')]
    const secondPage = [job('running-1', 'running')]
    const listJobs = vi.fn(async (_limit: number, offset: number) =>
      offset === 0
        ? { items: firstPage, has_more: true }
        : { items: secondPage, has_more: false },
    )
    const getDetail = vi.fn(async (jobId: string) =>
      detail(job(jobId, jobId === 'queued-1' ? 'running' : 'succeeded')),
    )

    const refreshed = await refreshDurableJobs(listJobs, getDetail)

    expect(listJobs.mock.calls).toEqual([[100, 0], [100, 2]])
    expect(getDetail.mock.calls.map(([jobId]) => jobId)).toEqual(['queued-1', 'running-1'])
    expect(refreshed.jobs.map(({ job_id, status }) => [job_id, status])).toEqual([
      ['queued-1', 'running'],
      ['done-1', 'succeeded'],
      ['running-1', 'succeeded'],
    ])
    expect(refreshed.activeJobIds).toEqual(['queued-1'])
    expect(refreshed.completedJobIds).toEqual(['running-1'])
    expect(refreshed.detailErrors).toEqual([])
  })

  it('keeps an active summary retryable when one detail projection fails', async () => {
    const refreshed = await refreshDurableJobs(
      async () => ({ items: [job('queued-1', 'queued')] }),
      async () => Promise.reject(new Error('temporary 503')),
    )

    expect(refreshed.jobs[0].status).toBe('queued')
    expect(refreshed.activeJobIds).toEqual(['queued-1'])
    expect(refreshed.completedJobIds).toEqual([])
    expect(refreshed.detailErrors).toEqual(['queued-1: Error: temporary 503'])
  })
})
