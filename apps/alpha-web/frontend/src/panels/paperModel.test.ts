import { describe, expect, it } from 'vitest'

import type { JobSummary, PaperEvent, PaperSession, SystemStatus } from '../api/types'
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

const event = (sequence: number, event_type: PaperEvent['event_type'], payload = {}): PaperEvent => ({
  schema_version: 1,
  session_id: 'a-session',
  sequence,
  event_type,
  recorded_at: `2026-07-19T00:00:0${sequence}Z`,
  ts_event_ns: null,
  payload,
})

const system = (paper_enabled: boolean): SystemStatus =>
  ({ paper_enabled }) as SystemStatus

const session = (overrides: Partial<PaperSession> = {}): PaperSession =>
  ({
    session_id: 'a-session',
    status: 'running',
    stale: false,
    ...overrides,
  }) as PaperSession

describe('paper monitor model', () => {
  it('merges cursor pages without duplicate events', () => {
    const merged = mergePaperEvents(
      [event(1, 'lifecycle'), event(2, 'order')],
      [event(2, 'order'), event(3, 'fill')],
    )
    expect(merged.map((item) => item.sequence)).toEqual([1, 2, 3])
    expect(nextEventCursor(merged)).toBe(3)
  })

  it('uses the newest position event as the position summary', () => {
    expect(
      latestPosition([
        event(1, 'position', { side: 'LONG', quantity: 0.25 }),
        event(2, 'fill'),
        event(3, 'position', { side: 'FLAT', quantity: 0 }),
      ]),
    ).toEqual({ side: 'FLAT', quantity: 0 })
  })

  it('finds only a running job attached to the selected session', () => {
    const jobs = [
      { job_id: 'old', status: 'done', session_id: 'target' },
      { job_id: 'other', status: 'running', session_id: 'another' },
      { job_id: 'live', status: 'running', session_id: 'target' },
    ] as Array<JobSummary & { session_id?: string | null }>
    expect(matchingRunningJob(jobs, 'target')?.job_id).toBe('live')
    expect(matchingRunningJob(jobs, 'missing')).toBeNull()
  })

  it('builds concise blotter text from event payloads', () => {
    expect(eventSummary(event(4, 'rejection', { side: 'BUY', quantity: 1.5, reason: 'limit' }))).toBe(
      'BUY · qty 1.5 · limit',
    )
    expect(eventSummary(event(5, 'lifecycle', { status: 'running' }))).toBe('running')
  })

  it('models loading, error, disabled, and empty overview states', () => {
    expect(paperOverviewState(null, null, null)).toBe('loading')
    expect(paperOverviewState(system(true), null, 'poll failed')).toBe('error')
    expect(paperOverviewState(system(false), [], null)).toBe('disabled-empty')
    expect(paperOverviewState(system(false), [session()], null)).toBe('disabled-history')
    expect(paperOverviewState(system(true), [], null)).toBe('enabled-empty')
  })

  it('models stale, terminal/cancelled, live, and polling-error detail states', () => {
    expect(paperDetailState('a-session', null, null)).toBe('loading')
    expect(paperDetailState('a-session', session(), 'offline')).toBe('error')
    expect(paperDetailState('a-session', session({ stale: true }), null)).toBe('stale')
    expect(paperDetailState('a-session', session({ status: 'cancelled' }), null)).toBe('terminal')
    expect(paperDetailState('a-session', session(), null)).toBe('live')
    expect(paperStatusTone('cancelled')).toBe('fail')
    expect(paperStatusTone('completed')).toBe('pass')
  })
})
