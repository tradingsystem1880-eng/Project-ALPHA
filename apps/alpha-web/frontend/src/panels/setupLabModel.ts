import { asObj } from '../util/format'

/** Display projection only: no metric, missing-value fill or result is computed here. */
export function object(value: unknown): Record<string, unknown> {
  return asObj(value) ?? {}
}

export function stored(value: unknown): string {
  if (value === null || value === undefined) return 'not recorded'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

export function curveRows(value: unknown) {
  const curve = object(value)
  const mean = Array.isArray(curve.mean) ? curve.mean : []
  return mean.map((value, index) => ({ bar: index, mean: value,
    drift: Array.isArray(curve.drift) ? curve.drift[index] : null,
    lower: Array.isArray(curve.lower) ? curve.lower[index] : null,
    upper: Array.isArray(curve.upper) ? curve.upper[index] : null }))
}

export const FIELD_LABELS: Record<string, string> = {
  pooled: 'All instruments combined', per_asset: 'By instrument', mean: 'Average return after costs (fraction)',
  median: 'Middle return after costs (fraction)', hit_rate: 'Share of returns above zero',
  drift_mean: 'Average ordinary-date return', excess: 'Average return above the ordinary-date baseline',
  random_date_p: 'Random-date tail probability (chance of an equal or larger result)',
  random_date_5: 'Random dates, lower 5% bound', random_date_50: 'Random dates, middle value',
  random_date_95: 'Random dates, upper 95% bound', mean_r: 'Average return divided by initial stop risk',
  profit_factor: 'Total positive returns divided by the magnitude of negative returns',
  spec_sha256: 'Stored specification fingerprint', total_trials: 'Recorded trial count at publication',
  accepted_clusters: 'Separate accepted occurrences', clusters: 'Separate occurrence groups',
  accepted: 'Accepted matching days', events: 'Candidate events', pending: 'Still waiting at the end',
  primary_horizon: 'Primary outcome window (bars)', horizons: 'Outcome windows (bars)',
  mean_bars_held: 'Average holding length (bars)', median_bars_held: 'Middle holding length (bars)',
  fee_bps: 'fee bps (fee per side)', slippage_bps: 'slippage bps (assumed execution cost per side)',
  stability: 'Chronological halves', draws: 'Random-date samples', controls: 'Comparison rules',
  median_r: 'Middle return divided by initial stop risk', share_above_zero_r: 'Share of trades above 0 R',
  expectancy_r: 'Expectancy per trade in R', risk_explanation: 'How to read R',
  short_borrow_bps_per_year: 'assumed stock borrow, bps per year', short_carry_bps_per_day: 'assumed crypto funding, bps per day',
  opposite_direction: 'Opposite direction on the same entries (a control)',
}

/** Rounds long stored decimals for reading only; the stored value is unchanged. */
export function shown(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value) && !Number.isInteger(value)) {
    const digits = Math.abs(value) >= 1 ? 2 : 4
    return String(Number(value.toFixed(digits)))
  }
  return stored(value)
}

export interface Mark { symbol: string; at: number; rejected: boolean }

/** One mark per stored candidate that has a recorded date; no date is guessed. */
export function timelineMarks(candidates: readonly Record<string, unknown>[]): Mark[] {
  const marks: Mark[] = []
  for (const row of candidates) {
    const at = typeof row.event_ts === 'string' ? Date.parse(row.event_ts) : Number.NaN
    if (Number.isFinite(at)) marks.push({ symbol: String(row.symbol ?? 'not recorded'), at, rejected: row.status === 'rejected' })
  }
  return marks
}
