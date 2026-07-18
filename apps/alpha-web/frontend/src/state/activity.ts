// The live-desk client store: one EventSource on /api/activity/stream shared by every panel.
//
// Module-level external store (the linked.ts pattern) so Dockview's separate React roots all see
// one connection. Reconnect uses exponential backoff; on every (re)connect the run list is
// considered stale and `runsVersion` bumps — panels refetch /api/runs instead of replaying missed
// events (the store is durable; the stream is only a change notification).

import { useSyncExternalStore } from 'react'

import type { JobSummary, RunListItem } from '../api/types'

export type ConnectionState = 'connecting' | 'live' | 'down'

export interface ActivityEvent {
  seq: number
  at: number // client wall-clock, display only
  type: 'run_added' | 'run_updated' | 'job_started' | 'job_done' | 'job_failed' | 'job_cancelled'
  run?: RunListItem
  job?: JobSummary
}

export interface ActivityState {
  connection: ConnectionState
  /** Bumps on any run-store change AND on (re)connect — subscribers refetch /api/runs on change. */
  runsVersion: number
  /** Bumps on any job change — JobMonitor refetches /api/jobs on change. */
  jobsVersion: number
  runningJobs: number
  /** Newest-first ring buffer of recent events for the Activity Feed. */
  feed: ActivityEvent[]
}

const FEED_CAP = 200

let state: ActivityState = {
  connection: 'connecting',
  runsVersion: 0,
  jobsVersion: 0,
  runningJobs: 0,
  feed: [],
}
let seq = 0
let es: EventSource | null = null
let retryMs = 1000
let retryTimer: number | null = null
const listeners = new Set<() => void>()

function emit(patch: Partial<ActivityState>): void {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

function pushEvent(type: ActivityEvent['type'], data: string): void {
  let run: RunListItem | undefined
  let job: JobSummary | undefined
  try {
    const parsed = JSON.parse(data) as Record<string, unknown>
    if (type.startsWith('run_')) run = parsed as unknown as RunListItem
    else job = parsed as unknown as JobSummary
  } catch {
    return
  }
  seq += 1
  const ev: ActivityEvent = { seq, at: Date.now() / 1000, type, run, job }
  const feed = [ev, ...state.feed].slice(0, FEED_CAP)
  const patch: Partial<ActivityState> = { feed }
  if (type.startsWith('run_')) patch.runsVersion = state.runsVersion + 1
  else {
    patch.jobsVersion = state.jobsVersion + 1
    if (type === 'job_started') patch.runningJobs = state.runningJobs + 1
    else patch.runningJobs = Math.max(0, state.runningJobs - 1)
  }
  emit(patch)
}

function connect(): void {
  if (es) return
  emit({ connection: 'connecting' })
  const source = new EventSource('/api/activity/stream?poll=1')
  es = source

  source.addEventListener('snapshot', (e) => {
    retryMs = 1000
    let running = 0
    try {
      running = (JSON.parse((e as MessageEvent<string>).data) as { jobs_running?: number })
        .jobs_running ?? 0
    } catch {
      running = 0
    }
    // (re)connected: anything may have happened while we were away — force refetches
    emit({
      connection: 'live',
      runningJobs: running,
      runsVersion: state.runsVersion + 1,
      jobsVersion: state.jobsVersion + 1,
    })
  })
  const on = (type: ActivityEvent['type']) => (e: Event) =>
    pushEvent(type, (e as MessageEvent<string>).data)
  source.addEventListener('run_added', on('run_added'))
  source.addEventListener('run_updated', on('run_updated'))
  source.addEventListener('job_started', on('job_started'))
  source.addEventListener('job_done', on('job_done'))
  source.addEventListener('job_failed', on('job_failed'))
  source.addEventListener('job_cancelled', on('job_cancelled'))

  source.onerror = () => {
    source.close()
    if (es === source) es = null
    emit({ connection: 'down' })
    if (retryTimer !== null) window.clearTimeout(retryTimer)
    retryTimer = window.setTimeout(() => {
      retryTimer = null
      connect()
    }, retryMs)
    retryMs = Math.min(retryMs * 2, 15000)
  }
}

/** Start the shared activity connection (idempotent). Call once from the shell. */
export function initActivity(): void {
  connect()
}

export function getActivity(): ActivityState {
  return state
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}

export function useActivity(): ActivityState {
  return useSyncExternalStore(subscribe, getActivity, getActivity)
}
