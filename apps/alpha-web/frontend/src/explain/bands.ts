// Mirror of the Python grading constants in
// packages/alpha-validation/src/alpha_validation/verdict.py — keep BOTH files in lockstep
// (verdict.py carries the matching cross-reference comment). The persisted manifest verdict is
// ALWAYS authoritative; this mirror exists so the UI can explain a grade against its bands
// ("edge=B because OOS Sharpe 1.24 ∈ [1.0, 1.5)"). The vitest fixture suite recomputes grades
// from real manifests and asserts they equal the persisted ones, guarding against drift.

import { isFiniteNum as finite } from '../util/format'

export type Bands = readonly (readonly [number, string])[]

// (inclusive lower bound, grade), scanned high-to-low; below the last bound is "F".
export const EDGE_BANDS: Bands = [
  [1.5, 'A'],
  [1.0, 'B'],
  [0.5, 'C'],
  [0.0, 'D'],
]
export const SAMPLE_BANDS: Bands = [
  [1000, 'A'],
  [500, 'B'],
  [250, 'C'],
  [100, 'D'],
]
// index = robustness checks passed (0..4)
export const ROBUSTNESS_BY_COUNT: readonly string[] = ['F', 'D', 'C', 'B', 'A']
// Risk bands use the *upper* bound (smaller is better); scanned low-to-high.
export const DRAWDOWN_BANDS: Bands = [
  [0.1, 'A'],
  [0.2, 'B'],
  [0.35, 'C'],
  [0.5, 'D'],
]
export const RUIN_BANDS: Bands = [
  [0.01, 'A'],
  [0.05, 'B'],
  [0.15, 'C'],
  [0.3, 'D'],
]
export const OVERALL_BANDS: Bands = [
  [3.5, 'A'],
  [2.5, 'B'],
  [1.5, 'C'],
  [0.5, 'D'],
]

export const GPA: Record<string, number> = { A: 4, B: 3, C: 2, D: 1, F: 0 }

/** Highest band whose lower bound `value` clears; `F` if it clears none (or is null/NaN). */
export function gradeAtLeast(value: number | null | undefined, bands: Bands): string {
  if (!finite(value)) return 'F'
  for (const [bound, grade] of bands) if (value >= bound) return grade
  return 'F'
}

/** Best band whose upper bound `value` stays within; `F` if it exceeds all (or is null/NaN). */
export function gradeAtMost(value: number | null | undefined, bands: Bands): string {
  if (!finite(value)) return 'F'
  for (const [bound, grade] of bands) if (value <= bound) return grade
  return 'F'
}

export function worse(a: string, b: string): string {
  return (GPA[a] ?? 0) <= (GPA[b] ?? 0) ? a : b
}

/** The band interval a grade occupies, rendered like "[1.0, 1.5)" — for narrative text. */
export function bandInterval(grade: string, bands: Bands, kind: 'atLeast' | 'atMost'): string {
  const idx = bands.findIndex(([, g]) => g === grade)
  if (idx < 0) {
    // F = beyond the last band
    const last = bands[bands.length - 1][0]
    return kind === 'atLeast' ? `below ${last}` : `above ${last}`
  }
  const [bound] = bands[idx]
  if (kind === 'atLeast') {
    const upper = idx > 0 ? bands[idx - 1][0] : null
    return upper === null ? `≥ ${bound}` : `[${bound}, ${upper})`
  }
  const lower = idx > 0 ? bands[idx - 1][0] : null
  return lower === null ? `≤ ${bound}` : `(${lower}, ${bound}]`
}

export interface RecomputedVerdict {
  edge: string
  robustness: string
  risk: string
  sample: string
  overall: string
  gpa: number
  checks: number
}

/** Recompute the verdict from raw gate quantities — mirrors grade_verdict() in verdict.py. */
export function recomputeVerdict(inputs: {
  oosSharpe: number | null
  nullTiersPassed: boolean
  dsrPassed: boolean
  cpcvPassed: boolean
  ciLowerPositive: boolean
  maxDrawdown: number | null
  riskOfRuin: number | null
  nOos: number
}): RecomputedVerdict {
  const edge = gradeAtLeast(inputs.oosSharpe, EDGE_BANDS)
  const checks =
    Number(inputs.nullTiersPassed) +
    Number(inputs.dsrPassed) +
    Number(inputs.cpcvPassed) +
    Number(inputs.ciLowerPositive)
  const robustness = ROBUSTNESS_BY_COUNT[checks]
  const ddDepth = finite(inputs.maxDrawdown) ? Math.abs(inputs.maxDrawdown) : null
  const risk = worse(gradeAtMost(ddDepth, DRAWDOWN_BANDS), gradeAtMost(inputs.riskOfRuin, RUIN_BANDS))
  const sample = gradeAtLeast(inputs.nOos, SAMPLE_BANDS)
  const gpa = ((GPA[edge] ?? 0) + (GPA[robustness] ?? 0) + (GPA[risk] ?? 0) + (GPA[sample] ?? 0)) / 4
  const overall = gradeAtLeast(gpa, OVERALL_BANDS)
  return { edge, robustness, risk, sample, overall, gpa, checks }
}
