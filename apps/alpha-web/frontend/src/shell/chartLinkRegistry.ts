import { scheduleChartRange, cancelChartRange } from '../components/chartResize'
/** Workspace-local imperative UTC linking. Cursor traffic never enters React state. */
export interface ChartLinkEndpoint { range(from: number, to: number): void; cursor(time: number | null): void }
export function createChartLinkRegistry() {
  const endpoints = new Map<string, ChartLinkEndpoint>()
  let range = false, cursor = false, applying = false, frame = 0
  let pendingCursor: { id: string; time: number | null } | undefined
  const pendingRanges = new Map<string, { from: number; to: number }>()
  const flush = () => {
    frame = 0; applying = true
    try {
      const event = pendingCursor; pendingCursor = undefined
      if (cursor && event) for (const [target, endpoint] of endpoints) if (target !== event.id) endpoint.cursor(event.time)

    } finally { applying = false }
    if (pendingCursor) schedule()
  }
  const flushRange = () => {
    const next = pendingRanges.entries().next().value
    if (next && range) {
      const [target, value] = next; pendingRanges.delete(target)
      applying = true
      try { endpoints.get(target)?.range(value.from, value.to) } finally { applying = false }
    }
    if (pendingRanges.size) scheduleChartRange(flushRange)
  }
  const schedule = () => { if (!frame) frame = requestAnimationFrame(flush) }
  return {
    configure(linkRange: boolean, linkCursor: boolean) {
      range = linkRange; cursor = linkCursor
      if (!range) { pendingRanges.clear(); cancelChartRange(flushRange) }
      if (!cursor) pendingCursor = undefined
    },
    register(id: string, endpoint: ChartLinkEndpoint) {
      endpoints.set(id, endpoint)
      return () => {
        if (endpoints.get(id) === endpoint) { endpoints.delete(id); pendingRanges.delete(id) }
        if (!endpoints.size) { if (frame) cancelAnimationFrame(frame); frame = 0; pendingCursor = undefined; pendingRanges.clear(); cancelChartRange(flushRange) }
      }
    },
    publish(id: string, type: 'range' | 'cursor', ...values: number[]) {
      if (applying || !(type === 'range' ? range : cursor)) return
      if (type === 'cursor') { pendingCursor = { id, time: values[0] ?? null }; schedule() }
      else {
        pendingRanges.delete(id)
        for (const target of endpoints.keys()) if (target !== id) pendingRanges.set(target, { from: values[0], to: values[1] })
        if (pendingRanges.size) scheduleChartRange(flushRange)
      }
    },
  }
}
export type ChartLinkRegistry = ReturnType<typeof createChartLinkRegistry>

/** Inclusive backend UTC endpoints mapped to display coordinates, without data resampling. */
export function logicalRangeForUTC(times: readonly number[], from: number, to: number): { from: number; to: number } | null {
  if (!times.length || from > to || to < times[0] || from > times[times.length - 1]) return null
  const lower = (time: number, inclusive: boolean) => {
    let lo = 0, hi = times.length
    while (lo < hi) { const mid = (lo + hi) >>> 1; if (times[mid] < time || (!inclusive && times[mid] === time)) lo = mid + 1; else hi = mid }
    return lo
  }
  const first = lower(from, true), last = lower(to, false) - 1
  if (first > last) return null
  return first === last ? { from: first - .5, to: last + .5 } : { from: first + 1e-6, to: last - 1e-6 }
}
