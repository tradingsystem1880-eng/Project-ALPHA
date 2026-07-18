// Verdict grade helpers: every A–F grade maps to its own CSS token (previously only A/D/F
// were colored, so B and C were indistinguishable from a generic caution).

export type Grade = 'A' | 'B' | 'C' | 'D' | 'F'

const GRADES: readonly Grade[] = ['A', 'B', 'C', 'D', 'F']

export function isGrade(value: unknown): value is Grade {
  return typeof value === 'string' && (GRADES as readonly string[]).includes(value)
}

/** CSS color var for a grade (e.g. 'var(--verdict-b)'); muted fallback for unknown input. */
export function gradeColor(grade: string): string {
  return isGrade(grade) ? `var(--verdict-${grade.toLowerCase()})` : 'var(--muted)'
}

/** Soft (translucent background) CSS var for a grade. */
export function gradeSoft(grade: string): string {
  return isGrade(grade) ? `var(--verdict-${grade.toLowerCase()}-soft)` : 'var(--panel-2)'
}
