// Shared read-only research views: the HypothesisCard rendering (spec §5.1) and the
// compact Readiness Scorecard strip (spec §10.2). Both render enumerated states only —
// no numeric aggregate, no synthetic confidence — and are used by the Research Cockpit
// and the Evidence Hub so the two surfaces can never diverge.

import type { HypothesisCard, ResearchScorecard } from '../api/types'
import { stateChipClass } from './researchChipModel'

export function HypothesisCardView({ card }: { card: HypothesisCard }) {
  return (
    <section className="hypothesis-card" aria-label="Formal hypothesis card">
      <div className="rd-head">
        Hypothesis card · {card.complete_fields} of {card.total_fields} fields complete
      </div>
      <div className="hypothesis-card-grid">
        {card.fields.map((field) => (
          <div key={field.field_id} className="hypothesis-card-field">
            <span className="eyebrow">{field.label}</span>
            <span className={stateChipClass(field.status)}>{field.status.toUpperCase()}</span>
            <p>{field.value ?? 'Not yet defined.'}</p>
          </div>
        ))}
      </div>
      {card.analysis_plan ? (
        <div className="hypothesis-card-plan" aria-label="Frozen analysis plan">
          <span className="eyebrow">
            Analysis plan · {card.analysis_plan.family_count} registered families
          </span>
          {card.analysis_plan.families.map((entry) => (
            <span
              key={entry.family}
              className="chip kind"
              title={`multiplicity: ${entry.multiplicity.replaceAll('_', ' ')}`}
            >
              {entry.family.replaceAll('_', ' ')} · {entry.multiplicity.replaceAll('_', ' ')}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

export function ScorecardStrip({ scorecard }: { scorecard: ResearchScorecard }) {
  return (
    <div className="scorecard-strip" aria-label="Readiness scorecard">
      {scorecard.dimensions.map((dimension) => (
        <span
          key={dimension.dimension_id}
          className={stateChipClass(dimension.state)}
          title={`${dimension.label}: ${dimension.state.replaceAll('_', ' ')} — ${dimension.basis}`}
        >
          {dimension.label} · {dimension.state.replaceAll('_', ' ').toUpperCase()}
        </span>
      ))}
      <span
        className="chip kind"
        title={scorecard.recommendation.reasons.join(' ')}
      >
        {scorecard.recommendation.value}
      </span>
    </div>
  )
}

export function ScorecardDetail({ scorecard }: { scorecard: ResearchScorecard }) {
  return (
    <section className="scorecard-detail" aria-label="Readiness scorecard detail">
      <div className="scorecard-table">
        {scorecard.dimensions.map((dimension) => (
          <div key={dimension.dimension_id} className="scorecard-row">
            <span className="eyebrow">{dimension.label}</span>
            <span className={stateChipClass(dimension.state)}>
              {dimension.state.replaceAll('_', ' ').toUpperCase()}
            </span>
            <p>{dimension.basis}</p>
          </div>
        ))}
      </div>
      <div className="workbench-notice" role="note">
        <strong>{scorecard.recommendation.value}</strong>
        {scorecard.recommendation.reasons.map((reason) => (
          <span key={reason}>{reason}</span>
        ))}
      </div>
      {scorecard.unresolved_questions.count > 0 ? (
        <div className="research-question-list">
          <span className="eyebrow">
            Unresolved questions ({scorecard.unresolved_questions.count})
          </span>
          <ul>
            {scorecard.unresolved_questions.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
