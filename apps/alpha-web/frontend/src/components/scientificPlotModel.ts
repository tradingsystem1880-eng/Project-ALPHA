export interface ScientificPoint { time: number; value: number | null }
/** Display coordinates only: UTC milliseconds and NaN gaps, never statistical estimation. */
export function scientificValues(points: readonly ScientificPoint[]) {
  return { x: points.map(p => p.time * 1000), y: points.map(p => p.value ?? NaN) }
}
export function plotBounds(points: readonly ScientificPoint[]): { x: [number, number]; y: [number, number] } {
  if (!points.length) return { x: [0, 1], y: [0, 1] }
  let min = Infinity, max = -Infinity
  for (const p of points) if (p.value !== null && Number.isFinite(p.value)) { min = Math.min(min, p.value); max = Math.max(max, p.value) }
  if (!Number.isFinite(min)) { min = 0; max = 1 }
  const pad = (max - min || Math.abs(max) || 1) * .08
  return { x: [points[0].time * 1000, points.at(-1)!.time * 1000 + (points[0].time === points.at(-1)!.time ? 1000 : 0)], y: [min - pad, max + pad] }
}
export function nearestTimestamp(times: readonly number[], time: number): number | null {
  if (!times.length || time < times[0] || time > times[times.length - 1]) return null
  let lo = 0, hi = times.length - 1
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (times[mid] < time) lo = mid + 1; else hi = mid }
  return lo > 0 && time - times[lo - 1] < times[lo] - time ? times[lo - 1] : times[lo]
}

/** Descriptive display of returned observations, not an estimator or readiness claim. */
export function seriesSummary(points: readonly ScientificPoint[]) {
  let minimum: number | null = null, maximum: number | null = null, missing = 0
  for (const { value } of points) {
    if (value === null) { missing++; continue }
    minimum = minimum === null ? value : Math.min(minimum, value)
    maximum = maximum === null ? value : Math.max(maximum, value)
  }
  return { total: points.length, missing, first: points[0]?.time ?? null, last: points.at(-1)?.time ?? null, minimum, maximum, latest: points.at(-1)?.value ?? null }
}
export function trailingWindow(points: readonly ScientificPoint[], days: number): [number, number] | null {
  if (!points.length) return null
  const end = points.at(-1)!.time
  return [Math.max(points[0].time, end - days * 86400), end]
}
/** Inclusive UTC calendar days clipped to returned coverage; never resample or refetch. */
export function dateWindow(points: readonly ScientificPoint[], from: string, to: string): [number, number] | null {
  if (!points.length) return null
  const start = Date.parse(`${from}T00:00:00Z`), end = Date.parse(`${to}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end) || new Date(start).toISOString().slice(0, 10) !== from || new Date(end).toISOString().slice(0, 10) !== to || start > end) return null
  const clipped: [number, number] = [Math.max(points[0].time, start / 1000), Math.min(points.at(-1)!.time, end / 1000 + 86399)]
  return clipped[0] < clipped[1] ? clipped : null
}
export function recordedCsv(points: readonly ScientificPoint[], label: string): string {
  return `timestamp_utc,"${label.replaceAll('"', '""')}"\n` + points.map(p => `${new Date(p.time * 1000).toISOString()},${p.value ?? ''}`).join('\n') + '\n'
}
