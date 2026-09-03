// Formatting helpers — every number the workstation shows is tabular-aligned and consistent —
// plus the shared narrow/guard helpers (importable from both explain/ and panels/).

export function isFiniteNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

/** The value as a finite number, else null (manifests carry null for non-finite stats). */
export function asNum(v: unknown): number | null {
  return isFiniteNum(v) ? v : null
}

export function asStr(v: unknown): string | null {
  return typeof v === 'string' ? v : null
}

/** UTC calendar date of an epoch-seconds bar stamp (`YYYY-MM-DD`). */
export function fmtUtcDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toISOString().slice(0, 10)
}

export function fmtTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000)
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function fmtNum(v: unknown, digits = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

export function fmtPct(v: unknown, digits = 1): string {
  return typeof v === 'number' && Number.isFinite(v) ? `${(v * 100).toFixed(digits)}%` : '—'
}

export function shortId(id: string): string {
  return id.length > 10 ? id.slice(0, 10) : id
}

export function fmtBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unit = 0
  while (size >= 1000 && unit < units.length - 1) {
    size /= 1000
    unit += 1
  }
  return `${size.toFixed(unit < 2 ? 0 : 1)} ${units[unit]}`
}
