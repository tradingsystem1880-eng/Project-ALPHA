import type {
  JsonScalar,
  PaperEvent,
  PaperJobSummary,
  PaperSession,
  SystemStatus,
} from '../api/types'

export type PaperOverviewState =
  | 'loading'
  | 'error'
  | 'disabled-empty'
  | 'disabled-history'
  | 'enabled-empty'
  | 'enabled-history'

export function paperOverviewState(
  system: SystemStatus | null,
  sessions: PaperSession[] | null,
  error: string | null,
): PaperOverviewState {
  if (error) return 'error'
  if (!system || sessions === null) return 'loading'
  if (!system.paper_enabled) return sessions.length ? 'disabled-history' : 'disabled-empty'
  return sessions.length ? 'enabled-history' : 'enabled-empty'
}

export function paperDetailState(
  selectedId: string | null,
  session: PaperSession | null,
  error: string | null,
): 'idle' | 'loading' | 'error' | 'stale' | 'terminal' | 'live' {
  if (error) return 'error'
  if (!selectedId) return 'idle'
  if (!session) return 'loading'
  if (session.stale) return 'stale'
  if (['completed', 'cancelled', 'failed'].includes(session.status)) return 'terminal'
  return 'live'
}

export function paperStatusTone(status: PaperSession['status']): string {
  if (status === 'running' || status === 'completed') return 'pass'
  if (status === 'starting' || status === 'stopping') return 'kind'
  return 'fail'
}

export function mergePaperEvents(current: PaperEvent[], incoming: PaperEvent[]): PaperEvent[] {
  const bySequence = new Map(current.map((event) => [event.sequence, event]))
  for (const event of incoming) bySequence.set(event.sequence, event)
  return [...bySequence.values()].sort((left, right) => left.sequence - right.sequence)
}

export function nextEventCursor(events: PaperEvent[]): number {
  return events.reduce((cursor, event) => Math.max(cursor, event.sequence), 0)
}

export function latestPosition(events: PaperEvent[]): Record<string, JsonScalar> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].event_type === 'position') return events[index].payload
  }
  return null
}

export function matchingRunningJob(
  jobs: PaperJobSummary[],
  sessionId: string,
): PaperJobSummary | null {
  return jobs.find((job) => job.status === 'running' && job.session_id === sessionId) ?? null
}

function firstPayloadValue(payload: Record<string, JsonScalar>, keys: string[]): JsonScalar {
  for (const key of keys) {
    const value = payload[key]
    if (value !== undefined && value !== null && value !== '') return value
  }
  return null
}

export function eventSummary(event: PaperEvent): string {
  const { payload } = event
  const parts: string[] = []
  const side = firstPayloadValue(payload, ['side', 'order_side'])
  const quantity = firstPayloadValue(payload, ['quantity', 'qty', 'size'])
  const price = firstPayloadValue(payload, ['price', 'avg_price', 'fill_price'])
  const status = firstPayloadValue(payload, ['status', 'state'])
  const reason = firstPayloadValue(payload, ['reason', 'message', 'warning'])
  if (side !== null) parts.push(String(side))
  if (quantity !== null) parts.push(`qty ${String(quantity)}`)
  if (price !== null) parts.push(`@ ${String(price)}`)
  if (status !== null) parts.push(String(status))
  if (reason !== null) parts.push(String(reason))
  return parts.length ? parts.join(' · ') : JSON.stringify(payload)
}
