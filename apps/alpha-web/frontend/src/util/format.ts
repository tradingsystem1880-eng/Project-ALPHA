// Formatting helpers — every number the workstation shows is tabular-aligned and consistent.

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
