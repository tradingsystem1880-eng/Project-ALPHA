// Verdict medallion: the letter always carries the identity; color is redundant reinforcement.

import { gradeColor, gradeSoft } from '../../util/verdict'

export function Medallion({
  grade,
  label,
  big = false,
}: {
  grade: string
  label?: string
  big?: boolean
}) {
  return (
    <div className={`medallion${big ? ' big' : ''}`}>
      {label ? <span className="eyebrow">{label}</span> : null}
      <span
        className="medallion-grade"
        style={{ color: gradeColor(grade), background: gradeSoft(grade) }}
      >
        {grade || '—'}
      </span>
    </div>
  )
}
