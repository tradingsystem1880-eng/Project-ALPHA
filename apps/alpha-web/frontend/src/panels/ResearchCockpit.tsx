import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'

import { api, type OwnerActionType } from '../api/client'
import { CopyCommand } from '../components/CopyCommand'
import { OwnerActionButton } from '../components/OwnerActionButton'
import {
  contentAddressHash,
  performOwnerAction,
  researchCaseRevision,
} from '../auth/ownerAuth'
import type {
  ResearchCase,
  ResearchCaseReport,
  ResearchDecisionView,
  ResearchGatePacket,
  ResearchMaterialAnswers,
  ResearchProposalOptionsV1,
  ResearchStudyStatusV1,
  VerifiedBlindSemanticReadV1,
} from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { onNewIdea } from '../context/newIdea'
import type { PanelHandleProps } from '../context/panelHandle'
import { usePanelLinked } from '../context/usePanelLinked'
import { findingChipClass } from './researchChipModel'
import { openProviderCenter, openResearchData, openResearchSources } from './actions'
import {
  researchBudgetRows,
  researchBudgetValueRows,
  researchContractView,
  researchEvidenceFirewall,
  researchPhaseLabel,
  researchPilotEligibility,
  researchProposalAvailable,
  CLI_ONLY,
  RESEARCH_DISPOSITIONS,
  RESEARCH_OUTCOMES,
  ownerStep,
} from './researchCockpitModel'
import { HypothesisCardView, ScorecardDetail, ScorecardStrip } from './researchViews'

type ChartConstruction = ResearchMaterialAnswers['chart_construction']
type EventAvailability = ResearchMaterialAnswers['event_availability']
type PrimaryOutcome = ResearchMaterialAnswers['primary_outcome']
type BusyOperation = 'capture' | 'load' | 'proposal' | 'pilot' | 'status' | 'report' | 'decision'
type CockpitView = 'overview' | 'study' | 'decision'

const CHART_OPTIONS: ReadonlyArray<{ value: ChartConstruction; label: string }> = [
  { value: 'spy_rth_60m_four_hour_window', label: 'Synthetic SPY-like 60m D0 · four-hour window' },
  { value: 'tiingo_daily_fallback', label: 'Qualified Tiingo daily SPY · next-session lane' },
  { value: 'bybit_btcusdt_linear_hourly', label: 'Bybit linear BTCUSDT · hourly crowding lane' },
]

const EVENT_OPTIONS: ReadonlyArray<{ value: EventAvailability; label: string }> = [
  { value: 'second_trough_confirmable', label: 'Second trough confirmable' },
  { value: 'bybit_funding_event_point_in_time', label: 'Bybit funding event · point-in-time' },
]

const OUTCOME_OPTIONS: ReadonlyArray<{ value: PrimaryOutcome; label: string }> = [
  { value: 'four_trading_hour_return_25bp', label: 'Four trading hours · +25 bp' },
  { value: 'next_regular_session_return_50bp', label: 'Next regular session · +50 bp' },
  {
    value: 'next_funding_mark_minus_index_5bp',
    label: 'Next funding mark-minus-index · -5 bp',
  },
]

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason)
}

function blockerRecovery(code: string): { label: string; action: () => void } | null {
  const normalized = code.toUpperCase()
  if (normalized.includes('SOURCE') || normalized.includes('PACK')) {
    return { label: 'Open Literature', action: openResearchSources }
  }
  if (normalized.includes('DATA')) {
    return { label: 'Open Research Data', action: openResearchData }
  }
  if (normalized.includes('PROVIDER')) {
    return { label: 'Open Provider Readiness', action: openProviderCenter }
  }
  return null
}

function budgetValue(value: number | null): string {
  return value === null ? '—' : value.toLocaleString()
}

function elapsedLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3_600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
  return `${Math.floor(seconds / 3_600)}h ${Math.floor((seconds % 3_600) / 60)}m`
}

function GateFinding({
  label,
  finding,
}: {
  label: string
  finding: ResearchGatePacket['layers']['guided_evidence']['mechanism']
}) {
  return (
    <div>
      <span className="eyebrow">{label}</span>
      <span className="mono">{finding.status}</span>
      <p>{finding.summary ?? 'No typed finding was recorded.'}</p>
    </div>
  )
}

function TerminalGatePacket({ packet }: { packet: ResearchGatePacket }) {
  const conclusion = packet.layers.conclusion_90_seconds
  const guided = packet.layers.guided_evidence
  const appendix = packet.layers.technical_appendix
  const interval = conclusion.uncertainty
  const checks = guided.confirmation_checks

  return (
    <section className="research-terminal-report" aria-label="Terminal Research Gate Packet">
      <div className="rd-head">90-second Research Gate conclusion</div>
      <div className="development-spec">
        <div><span className="eyebrow">Scientific outcome</span><strong>{packet.scientific_outcome}</strong></div>
        <div><span className="eyebrow">Owner disposition</span><strong>{packet.recommended_disposition.replaceAll('_', ' ').toUpperCase()}</strong></div>
        <div><span className="eyebrow">Evidence basis</span><span className="mono">{conclusion.evidence_basis.replaceAll('_', ' ')}</span></div>
        <div><span className="eyebrow">Primary estimate</span><span className="mono">{conclusion.primary_estimate ?? 'NOT TESTED'}</span></div>
        <div><span className="eyebrow">Uncertainty</span><span className="mono">{interval ? `${interval.lower} to ${interval.upper} · ${Math.round(interval.level * 100)}% ${interval.method}` : 'NOT TESTED'}</span></div>
        <div><span className="eyebrow">Effective sample</span><span className="mono">{conclusion.effective_sample_size ?? 'NOT TESTED'}</span></div>
        <div><span className="eyebrow">Practical magnitude</span><span className="mono">{conclusion.practical_magnitude.status.replaceAll('_', ' ')}</span></div>
        <div><span className="eyebrow">Confirmation classification</span><span className="mono">{guided.confirmation_classification ?? 'NOT TESTED'}</span></div>
      </div>
      <div className="workbench-notice">
        <strong>{conclusion.thesis_answer}</strong>
        <span>{conclusion.strongest_caveat}</span>
        <span>{guided.teaching_note}</span>
      </div>
      <div className="development-grid research-report-grid">
        <div className="research-findings">
          <GateFinding label="Mechanism" finding={guided.mechanism} />
          <GateFinding label="Strongest support" finding={guided.strongest_support} />
          <GateFinding label="Strongest contradiction" finding={guided.strongest_contradiction} />
          <GateFinding label="Multiplicity" finding={guided.multiplicity} />
          <GateFinding label="Prospective power" finding={guided.power} />
          <GateFinding label="Negative controls" finding={guided.negative_controls} />
        </div>
        <div className="research-question-list">
          <span className="eyebrow">Confounders</span>
          <p>Resolved: {guided.confounders.resolved.join(' · ') || 'none recorded'}</p>
          <p>Unresolved: {guided.confounders.unresolved.join(' · ') || 'none recorded'}</p>
          <span className="eyebrow">Stability</span>
          <p className="mono">parameter {guided.stability.parameter.status} · temporal {guided.stability.temporal.status} · transportability {guided.stability.transportability.status}</p>
          {checks ? (
            <>
              <span className="eyebrow">Frozen confirmation checks</span>
              <p className="mono">
                corrected primary {String(checks.corrected_primary_test_passed)} · registered direction {String(checks.interval_registered_direction)} · economic hurdle {String(checks.economic_hurdle_cleared)} · wholly adverse {String(checks.interval_wholly_against_direction)}
              </p>
            </>
          ) : null}
          <span className="eyebrow">Untested work</span>
          <ul>{guided.untested_work.map((item) => <li key={item}>{item}</li>)}</ul>
          <span className="eyebrow">What would change the conclusion</span>
          <ul>{guided.what_would_change_conclusion.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </div>
      <div className="research-lineage">
        <div><span className="eyebrow">Packet ID</span><code>{packet.packet_id}</code></div>
        <div><span className="eyebrow">Packet hash</span><code>{packet.packet_hash}</code></div>
        <div><span className="eyebrow">Bounded ledgers</span><span className="mono">{Object.entries(appendix.ledger_bounds.counts).map(([name, count]) => `${name.replaceAll('_', ' ')} ${count}`).join(' · ')}</span></div>
        <div><span className="eyebrow">Authority</span><span>{packet.authority.evidence_claim}; strategy validated {String(packet.authority.strategy_validated)} · paper ready {String(packet.authority.paper_ready)} · places orders {String(packet.authority.places_orders)}</span></div>
      </div>
    </section>
  )
}

function DecisionViewSection({
  view,
  busy,
}: {
  view: ResearchDecisionView | null
  busy: BusyOperation | null
}) {
  if (!view) {
    return (
      <Placeholder big={busy === 'decision' ? 'LOADING DECISION VIEW' : 'DECISION VIEW UNAVAILABLE'}>
        The decision view assembles the edge-validation checklist, the full readiness scorecard,
        the gate packet, and the append-only owner decision history.
      </Placeholder>
    )
  }
  return (
    <section className="research-decision-view" aria-label="Owner decision view">
      <div className="rd-head">Edge-validation checklist · fourteen questions, typed statuses only</div>
      <div className="scorecard-table" aria-label="Edge-validation checklist">
        {view.checklist.questions.map((row) => (
          <div key={row.question_id} className="scorecard-row">
            <span className="eyebrow">{row.number}. {row.question}</span>
            <span className={findingChipClass(row.status)} title={`binding: ${row.binding}`}>
              {row.status.replaceAll('_', ' ')}
            </span>
            <p>{row.answer}</p>
          </div>
        ))}
      </div>
      <div className="rd-head">Full readiness scorecard</div>
      <ScorecardDetail scorecard={view.scorecard} />
      {view.gate_packet ? (
        <TerminalGatePacket packet={view.gate_packet} />
      ) : (
        <div className="workbench-notice" role="note">
          <strong>NO TERMINAL GATE PACKET</strong>
          <span>
            The case is open; the checklist and scorecard above stay live from admitted evidence.
            A terminal packet appears only after the owner closes the case.
          </span>
        </div>
      )}
      <div className="rd-head">Owner decision history · append-only</div>
      {view.decision_history.length ? (
        <div className="research-lineage" aria-label="Owner decision history">
          {view.decision_history.map((event) => (
            <div key={event.sequence}>
              <span className="eyebrow">#{event.sequence} · {event.occurred_at}</span>
              <span className="mono" title={`contract ${event.contract_id}`}>
                {event.outcome} · {event.disposition.replaceAll('_', ' ').toUpperCase()} ·{' '}
                {event.actor} ({event.actor_kind})
              </span>
              <p>{event.reason}</p>
            </div>
          ))}
        </div>
      ) : (
        <span className="muted">No owner decisions recorded. Decisions are owner-only CLI acts.</span>
      )}
    </section>
  )
}

export function StudyStatusSection({
  status,
  semanticRead,
  semanticError,
  researchCase,
  onRefresh,
}: {
  status: ResearchStudyStatusV1 | null
  semanticRead: VerifiedBlindSemanticReadV1 | null
  semanticError: string | null
  researchCase: ResearchCase
  onRefresh: () => void
}) {
  const step = ownerStep(researchCase)
  if (!status) {
    return (
      <Placeholder big="STUDY STATUS UNAVAILABLE">
        Refresh the case to read the CLI-owned semantic and D1 projection.
      </Placeholder>
    )
  }
  const events = [status.semantic.definition, status.semantic.review, status.semantic.freeze]
    .filter((event) => event !== null)
  const currentSemanticRead = semanticRead !== null && (
    status.semantic.source_state === 'not_recorded' || (
      status.semantic.source_state === 'current'
      && status.semantic.verified_read_sha256 === semanticRead.content_sha256
    )
  ) ? semanticRead : null
  const points = currentSemanticRead?.projection.points ?? []
  return (
    <section aria-label="Verified semantic study status">
      <div className="rd-head">Masked semantic projection · server verified</div>
      {currentSemanticRead ? (
        <>
          <div className="development-spec">
            <div><span className="eyebrow">D0 run</span><code>{currentSemanticRead.run_id}</code></div>
            <div><span className="eyebrow">Visible points</span><strong>{points.length}</strong></div>
            <div><span className="eyebrow">Masked future points</span><strong>{currentSemanticRead.projection.masked_count}</strong></div>
            <div><span className="eyebrow">Verified cutoff</span><code>{currentSemanticRead.projection.cutoff_confirmed_at}</code></div>
            <div><span className="eyebrow">Authority</span><strong>NONE · READ ONLY</strong></div>
          </div>
          <div className="research-lineage" aria-label="Visible pre-cutoff semantic points">
            {points.map((point) => (
              <div key={point.point_id}>
                <span className="eyebrow">{point.point_id}</span>
                <span className="mono">{point.available_at} · {point.value}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="workbench-notice" role="status">
          <strong>MASKED D0 PROJECTION UNAVAILABLE</strong>
          <span>{semanticError ?? (
            status.semantic.source_state === 'stale'
              ? 'The case changed after the prior semantic cycle. Refresh before using the masked read.'
              : 'Complete and mechanically verify the registered D0 pilot.'
          )}</span>
        </div>
      )}

      <div className="rd-head">Touch-ID-bound semantic state</div>
      <div className="workbench-notice">
        <strong>{status.semantic.state.replaceAll('_', ' ').toUpperCase()}</strong>
        <span>{status.semantic.next_owner_action}</span>
        <span>source {status.semantic.source_state.replaceAll('_', ' ')}</span>
        <code>head {status.semantic.head_sha256}</code>
      </div>
      <div className="research-lineage" aria-label="Verified semantic owner events">
        {events.map((event) => event && (
          <div key={event.event_id}>
            <span className="eyebrow">{String(event.payload.event_type)} · {event.recorded_at}</span>
            <code>{event.artifact_id}</code>
            {typeof event.payload.definition_label === 'string' ? (
              <strong>{event.payload.definition_label}</strong>
            ) : null}
            {typeof event.payload.definition_text === 'string' ? (
              <p>{event.payload.definition_text}</p>
            ) : null}
            {typeof event.payload.review_decision === 'string' ? (
              <strong>{event.payload.review_decision.toUpperCase()}</strong>
            ) : null}
            {typeof event.payload.review_text === 'string' ? (
              <p>{event.payload.review_text}</p>
            ) : null}
            <span>{event.actor} · {event.reason} · Touch ID receipt {event.receipt_id}</span>
          </div>
        ))}
        {!events.length ? <span className="muted">No semantic owner event has been recorded.</span> : null}
      </div>

      <div className="rd-head">Existing research authority linkage</div>
      <div className="development-spec">
        <div><span className="eyebrow">Active contract</span><code>{status.active_contract_id}</code></div>
        <div><span className="eyebrow">D1 state</span><strong>{status.d1.status.replaceAll('_', ' ').toUpperCase()}</strong></div>
        <div><span className="eyebrow">D1 launch</span><strong>{step.kind === 'action' && step.actionType === 'launch_d1' ? 'OWNER · TOUCH ID BELOW' : 'OWNER ONLY'}</strong></div>
        <div><span className="eyebrow">Promotion dossier</span><code>{status.promotion.packet_id ?? 'none'}</code></div>
        <div><span className="eyebrow">Promotion readiness</span><strong>{status.promotion.readiness.state.toUpperCase()}</strong></div>
      </div>
      <div className="research-budget" aria-label="D1 research budget">
        {researchBudgetValueRows(status.d1.elapsed_budget, status.d1.remaining_budget).map((row) => (
          <div key={row.resource}>
            <span>{row.resource.replaceAll('_', ' ')}</span>
            <span className="mono">used {budgetValue(row.used)} · left {budgetValue(row.remaining)}</span>
          </div>
        ))}
      </div>
      <div className="workbench-notice">
        <strong>NEXT · {status.responsibility.toUpperCase()}</strong><span>{status.next_action}</span>
      </div>
      {step.kind === 'action' && step.actionType === 'launch_d1' ? (
        <OwnerActionButton
          researchCase={researchCase}
          actionType={step.actionType}
          label={step.label}
          consequence={step.consequence}
          payload={step.payload}
          onComplete={onRefresh}
        />
      ) : null}
    </section>
  )
}

function ApprovalBoundary({
  researchCase,
  onComplete,
}: {
  researchCase: ResearchCase
  onComplete: () => void
}) {
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<OwnerActionType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const contract = researchContractView(researchCase)
  const scope = researchCase.exploration_review.state === 'pending'
    ? 'exploration'
    : researchCase.confirmation_review.state === 'pending'
      ? 'confirmation'
      : null
  if (scope === null) return null
  const canApprove = scope === 'confirmation' || contract.approval_ready

  async function decide(decision: 'approve' | 'reject'): Promise<void> {
    const actionType = `${decision}_${scope}` as OwnerActionType
    setPending(actionType)
    setError(null)
    try {
      const expectedRevision = await researchCaseRevision(researchCase)
      await performOwnerAction({
        action_type: actionType,
        project_id: researchCase.project_id,
        artifact_hash: contentAddressHash(researchCase.active_contract_id),
        expected_case_revision: expectedRevision,
        consequence_summary: decision === 'approve'
          ? `Approve the immutable ${scope} contract and permit only its next bounded research stage.`
          : `Reject the immutable ${scope} contract; no empirical stage is launched.`,
        reason: reason.trim(),
        payload: { contract_id: researchCase.active_contract_id },
      })
      setReason('')
      onComplete()
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="owner-action-boundary" aria-label={`${scope} owner decision`}>
      <span className="eyebrow">Fresh owner presence required</span>
      <strong>Review and decide this exact immutable {scope} contract</strong>
      <p>
        Touch ID binds one decision to this project, artifact, current case revision, consequence,
        and your reason. It grants no gate override, holdout, paper, broker, or order authority.
      </p>
      {!canApprove ? (
        <div className="workbench-notice" role="note">
          <strong>APPROVAL UNAVAILABLE</strong>
          <span>This proposal has no executable operator. Reject it or revise the research case.</span>
        </div>
      ) : null}
      <label>
        <span className="eyebrow">Decision reason</span>
        <textarea
          className="field"
          value={reason}
          maxLength={8192}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Explain why this exact contract should advance or stop."
        />
      </label>
      <div className="owner-action-buttons">
        <button
          className="btn primary"
          type="button"
          disabled={!reason.trim() || !canApprove || pending !== null}
          onClick={() => void decide('approve')}
        >
          {pending === `approve_${scope}` ? 'waiting for Touch ID…' : `Touch ID · approve ${scope}`}
        </button>
        <button
          className="btn"
          type="button"
          disabled={!reason.trim() || pending !== null}
          onClick={() => void decide('reject')}
        >
          {pending === `reject_${scope}` ? 'waiting for Touch ID…' : `Touch ID · reject ${scope}`}
        </button>
      </div>
      {error ? <div className="workbench-notice" role="alert"><strong>ACTION BLOCKED</strong><span>{error}</span></div> : null}
      <div className="advanced-only">
        <CopyCommand command={CLI_ONLY.recovery.command} why={CLI_ONLY.recovery.why} />
      </div>
    </section>
  )
}

function CaseHeader({ researchCase }: { researchCase: ResearchCase }) {
  return (
    <div className="research-case-header" aria-label="Case status header">
      <div className="research-case-header-row">
        <strong>{researchCase.project_name}</strong>
        <span className="mono">{researchPhaseLabel(researchCase.phase).toUpperCase()}</span>
        <span className="mono">{researchCase.execution_state.toUpperCase()}</span>
        <span className={researchCase.responsibility === 'owner' ? 'chip fail' : 'chip kind'}>
          {researchCase.responsibility === 'owner' ? 'NEEDS YOU' : 'CODEX'}
        </span>
      </div>
      {researchCase.scorecard ? <ScorecardStrip scorecard={researchCase.scorecard} /> : null}
    </div>
  )
}

function CanonicalNextAction({ researchCase, onRefresh }: { researchCase: ResearchCase; onRefresh: () => void }) {
  const step = ownerStep(researchCase)
  return (
    <section className="research-next-action" aria-label="Canonical next action">
      <span className="eyebrow">Do this next</span>
      <strong>{researchCase.next_action}</strong>
      {researchCase.recovery ? <span>{researchCase.recovery}</span> : null}
      {step.kind === 'action' ? (
        <OwnerActionButton
          researchCase={researchCase}
          actionType={step.actionType}
          label={step.label}
          consequence={step.consequence}
          payload={step.payload}
          onComplete={onRefresh}
        />
      ) : step.kind === 'decide' ? (
        <span className="muted">Record the final disposition on the Decision tab.</span>
      ) : step.kind === 'waiting' ? (
        <span className="muted">{step.text}</span>
      ) : null}
    </section>
  )
}

/** The owner's closing decision (alpha research decide): outcome + disposition, then Touch ID. */
function OwnerDecisionForm({ researchCase, onRefresh }: { researchCase: ResearchCase; onRefresh: () => void }) {
  const [outcome, setOutcome] = useState<string>('')
  const [disposition, setDisposition] = useState<string>('')
  const step = ownerStep(researchCase)
  if (step.kind !== 'decide') {
    return (
      <span className="muted">
        {researchCase.phase === 'closed'
          ? 'This case is closed; its decision is in the history above.'
          : 'The final disposition opens in the research_decision phase, after D2.'}
      </span>
    )
  }
  const ready = outcome !== '' && disposition !== ''
  return (
    <div className="owner-decision-form" aria-label="Final disposition">
      <label>
        <span className="eyebrow">Outcome</span>
        <select className="field" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
          <option value="">choose…</option>
          {RESEARCH_OUTCOMES.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </label>
      <label>
        <span className="eyebrow">Disposition</span>
        <select className="field" value={disposition} onChange={(event) => setDisposition(event.target.value)}>
          <option value="">choose…</option>
          {RESEARCH_DISPOSITIONS.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
        </select>
      </label>
      <OwnerActionButton
        researchCase={researchCase}
        actionType="record_final_disposition"
        label="record decision"
        consequence={`Record the final disposition ${outcome || '…'} · ${disposition || '…'} for this case; advance_to_strategy writes the promotion dossier.`}
        payload={{ outcome, disposition }}
        disabledReason={ready ? null : 'choose an outcome and a disposition first'}
        onComplete={onRefresh}
      />
    </div>
  )
}

function MaterialQuestions({ researchCase, onRefresh }: { researchCase: ResearchCase; onRefresh: () => void }) {
  const contract = researchContractView(researchCase)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  if (!contract.blocking_questions.length) return null
  const step = ownerStep(researchCase)
  const answered = contract.blocking_questions.every((question) => answers[question.id])
  const blocked =
    step.kind !== 'revise'
      ? 'the case is not waiting for revised answers'
      : step.sourcePackId === null
        ? 'freeze a source pack first (Evidence tab) — revision binds to it'
        : answered
          ? null
          : 'answer every question first'
  return (
    <section className="research-material-questions" aria-label="Material research questions">
      <div className="rd-head">Three decisions needed before this idea can be tested</div>
      <ol>
        {contract.blocking_questions.map((question) => (
          <li key={question.id} className="research-material-question">
            <strong>{question.prompt}</strong>
            <p>{question.blocking_reason}</p>
            <div className="research-choice-cards" role="radiogroup" aria-label={question.prompt}>
              {question.choices.map((choice) => (
                <div className="research-choice-card" key={choice.id}>
                  <label>
                    <input
                      type="radio"
                      name={`answer-${question.id}`}
                      value={choice.id}
                      checked={answers[question.id] === choice.id}
                      disabled={choice.availability === 'unavailable'}
                      onChange={() => setAnswers((current) => ({ ...current, [question.id]: choice.id }))}
                    />
                    <strong>{choice.label}</strong>
                  </label>
                  <span>{choice.consequence}</span>
                  {choice.availability === 'unavailable' ? (
                    <span className="chip fail" title="Choose another answer; this operator does not exist in the CLI yet">
                      UNAVAILABLE · {choice.blocked_reason}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </li>
        ))}
      </ol>
      <OwnerActionButton
        researchCase={researchCase}
        actionType="revise_exploration"
        label="revise with these answers"
        consequence="Revise the exploration contract with these material answers (alpha research revise); Codex re-proposes, nothing launches."
        payload={{ source_pack_id: step.kind === 'revise' ? step.sourcePackId : null, answers }}
        artifactId={researchCase.active_contract_id}
        disabledReason={blocked}
        primary={false}
        onComplete={onRefresh}
      />
    </section>
  )
}

function CaseSummary({
  researchCase,
  report,
  busy,
  onRefresh,
  onReport,
  onPilot,
}: {
  researchCase: ResearchCase
  report: ResearchCaseReport | null
  busy: BusyOperation | null
  onRefresh: () => void
  onReport: () => void
  onPilot: () => void
}) {
  const contract = researchContractView(researchCase)
  const budget = researchBudgetRows(researchCase)
  const pilot = researchPilotEligibility(researchCase)
  const decision = researchCase.research_decision

  return (
    <>
      <section className="development-spec" aria-label="Active Research Case">
        <div><span className="eyebrow">Case</span><strong>{researchCase.project_name}</strong></div>
        <div><span className="eyebrow">Phase</span><span className="mono">{researchPhaseLabel(researchCase.phase).toUpperCase()}</span></div>
        <div><span className="eyebrow">Execution</span><span className="mono">{researchCase.execution_state.toUpperCase()}</span></div>
        <div><span className="eyebrow">Responsibility</span><span className="mono">{researchCase.responsibility.toUpperCase()}</span></div>
        <div><span className="eyebrow">Contract review</span><span className="mono">{researchCase.exploration_review.state.toUpperCase()}</span></div>
        <div><span className="eyebrow">D2 confirmation</span><span className="mono">{researchCase.d2_state.toUpperCase()}</span></div>
        <div><span className="eyebrow">D3 strategy holdout</span><span className="mono">{researchCase.d3_state.replaceAll('_', ' ').toUpperCase()}</span></div>
        <div><span className="eyebrow">Attempts · milestones</span><span className="mono">{researchCase.attempt_count} · {researchCase.completed_milestones.length} done · {researchCase.remaining_milestones.length} left</span></div>
        <div><span className="eyebrow">Elapsed research time</span><span className="mono">{elapsedLabel(researchCase.elapsed_time_seconds)}</span></div>
      </section>

      <div className="agent-brief-bar">
        <div>
          <span className="eyebrow">Canonical next action</span>
          <span>{researchCase.next_action}</span>
          <span className="muted">{researchEvidenceFirewall(researchCase)}</span>
        </div>
        <button className="btn" type="button" disabled={busy !== null} onClick={onRefresh}>
          {busy === 'status' ? 'refreshing…' : 'refresh status'}
        </button>
        <button className="btn" type="button" disabled={busy !== null} onClick={onReport}>
          {busy === 'report' ? 'loading…' : 'progress report'}
        </button>
      </div>

      {researchCase.blocker ? (
        <div className="workbench-notice" role="alert">
          <strong>BLOCKED</strong>
          <span>{researchCase.blocker}</span>
          {researchCase.recovery ? <span>Recovery: {researchCase.recovery}</span> : null}
        </div>
      ) : null}

      {report?.report_schema === 'ResearchProgressReportV1' ? (
        <div className="workbench-notice" role="status">
          <strong>PROGRESS REPORT</strong>
          <span>{report.warning}</span>
        </div>
      ) : null}

      {report?.report_schema === 'ResearchGatePacketV1' ? (
        <TerminalGatePacket packet={report} />
      ) : null}

      <ApprovalBoundary researchCase={researchCase} onComplete={onRefresh} />

      {researchCase.latest_finding ? (
        <div className="workbench-notice" role="status">
          <strong>LATEST TYPED FINDING</strong>
          <span>{researchCase.latest_finding}</span>
        </div>
      ) : null}

      <div className="development-grid research-detail-grid">
        <section>
          <div className="rd-head">Thesis · what we think and why</div>
          <div className="development-spec research-thesis-grid">
            <div><span className="eyebrow">Original idea · exact wording</span><p>{contract.raw_idea ?? 'Not present in the active contract.'}</p></div>
            <div><span className="eyebrow">Provisional mechanism</span><p>{contract.mechanism ?? 'Not yet materialized.'}</p></div>
            <div><span className="eyebrow">Registered prediction</span><p>{contract.prediction ?? 'Not yet materialized.'}</p></div>
            <div><span className="eyebrow">Correct interpretation</span><p>{contract.interpretation ?? 'Not yet materialized.'}</p></div>
          </div>
          {contract.alternatives.length ? (
            <div className="research-question-list">
              <span className="eyebrow">Competing explanations to challenge</span>
              <ul>{contract.alternatives.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          ) : null}
        </section>

        <section className="advanced-only">
          <div className="rd-head">Governance · budget · lineage</div>
          <div className="research-lineage">
            <div><span className="eyebrow">Project ID</span><code>{researchCase.project_id}</code></div>
            <div><span className="eyebrow">Active contract</span><code>{researchCase.active_contract_id}</code></div>
            <div><span className="eyebrow">Source pack</span><code>{researchCase.source_pack_id ?? 'not frozen'}</code></div>
            <div><span className="eyebrow">D2 boundary hash</span><code>{researchCase.d2_boundary_hash}</code></div>
            <div><span className="eyebrow">Latest attempt</span><code>{researchCase.latest_attempt_id ?? 'none'}</code></div>
            <div><span className="eyebrow">Latest run</span><code>{researchCase.latest_run_id ?? 'none'}</code></div>
          </div>
          <div className="research-budget" aria-label="Research resource budget">
            <span className="eyebrow">Resources stay in their native units</span>
            {budget.length ? budget.map((row) => (
              <div key={row.resource}>
                <span>{row.resource.replaceAll('_', ' ')}</span>
                <span className="mono">used {budgetValue(row.used)} · left {budgetValue(row.remaining)}</span>
              </div>
            )) : <span className="muted">No budget consumption recorded.</span>}
          </div>
          {decision ? (
            <div className="workbench-notice">
              <strong>{decision.outcome} · {decision.disposition.replaceAll('_', ' ').toUpperCase()}</strong>
              <span>{decision.reason}</span>
            </div>
          ) : null}
          <div className="research-pilot-action">
            <button
              className="btn primary"
              type="button"
              disabled={!pilot.allowed || busy !== null}
              title={pilot.reason}
              onClick={onPilot}
            >
              {busy === 'pilot' ? 'running bounded pilot…' : 'run deterministic D0 pilot'}
            </button>
            <span>{pilot.reason}</span>
          </div>
        </section>
      </div>
    </>
  )
}

export function ResearchCockpit(props: PanelHandleProps) {
  const params = (props.params ?? {}) as { projectId?: unknown }
  const initialProjectId = typeof params.projectId === 'string' ? params.projectId : ''
  const panelLink = usePanelLinked(props)
  const ideaRef = useRef<HTMLTextAreaElement | null>(null)
  const [researchCase, setResearchCase] = useState<ResearchCase | null>(null)
  const [report, setReport] = useState<ResearchCaseReport | null>(null)
  const [view, setView] = useState<CockpitView>('overview')
  const [decisionView, setDecisionView] = useState<ResearchDecisionView | null>(null)
  const [semanticRead, setSemanticRead] = useState<VerifiedBlindSemanticReadV1 | null>(null)
  const [semanticError, setSemanticError] = useState<string | null>(null)
  const [lookupId, setLookupId] = useState(initialProjectId)
  const [idea, setIdea] = useState('')
  const [caseName, setCaseName] = useState('')
  const [showCapture, setShowCapture] = useState(
    initialProjectId === '' && panelLink.linked.projectId === null,
  )
  const [sourcePackId, setSourcePackId] = useState('')
  const [datasetRefId, setDatasetRefId] = useState('')
  const [proposalOptions, setProposalOptions] = useState<ResearchProposalOptionsV1 | null>(null)
  const [proposalOptionsError, setProposalOptionsError] = useState<string | null>(null)
  const [answerBundleId, setAnswerBundleId] = useState('')
  const [chartConstruction, setChartConstruction] = useState<ChartConstruction | ''>('')
  const [eventAvailability, setEventAvailability] = useState<EventAvailability | ''>('')
  const [primaryOutcome, setPrimaryOutcome] = useState<PrimaryOutcome | ''>('')
  const [busy, setBusy] = useState<BusyOperation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const caseRequestSequence = useRef(0)
  const activeProjectRef = useRef(panelLink.linked.projectId)
  activeProjectRef.current = panelLink.linked.projectId

  const proposalComplete = useMemo(
    () => {
      const selected = proposalOptions?.valid_answer_bundles.find(
        (bundle) => bundle.bundle_id === answerBundleId,
      )
      return sourcePackId !== '' && selected?.available === true
        && (!selected.requires_dataset || datasetRefId !== '')
    },
    [answerBundleId, datasetRefId, proposalOptions, sourcePackId],
  )

  function acceptCase(next: ResearchCase): void {
    setResearchCase(next)
    setLookupId(next.project_id)
    setSourcePackId(next.source_pack_id ?? '')
    setDatasetRefId('')
    setProposalOptions(null)
    setProposalOptionsError(null)
    setReport(null)
    setDecisionView(null)
    setSemanticRead(null)
    setSemanticError(null)
    setAnswerBundleId('')
    setChartConstruction('')
    setEventAvailability('')
    setPrimaryOutcome('')
    setShowCapture(false)
    panelLink.setLinked({ projectId: next.project_id })
  }

  function selectAnswerBundle(bundleId: string): void {
    setAnswerBundleId(bundleId)
    const bundle = proposalOptions?.valid_answer_bundles.find(
      (candidate) => candidate.bundle_id === bundleId,
    )
    setChartConstruction((bundle?.answers.chart_construction ?? '') as ChartConstruction | '')
    setEventAvailability((bundle?.answers.event_availability ?? '') as EventAvailability | '')
    setPrimaryOutcome((bundle?.answers.primary_outcome ?? '') as PrimaryOutcome | '')
    if (!bundle?.requires_dataset) setDatasetRefId('')
  }

  useEffect(() => {
    if (!researchCase || !researchProposalAvailable(researchCase.phase)) return
    const projectId = researchCase.project_id
    let current = true
    setProposalOptionsError(null)
    void api.researchProposalOptions(projectId).then((options) => {
      if (!current) return
      setProposalOptions(options)
      const recommended = options.valid_answer_bundles.find(
        (bundle) => bundle.bundle_id === options.recommended_answer_bundle_id
          && bundle.available,
      )
      if (recommended) {
        setAnswerBundleId(recommended.bundle_id)
        setChartConstruction(recommended.answers.chart_construction)
        setEventAvailability(recommended.answers.event_availability)
        setPrimaryOutcome(recommended.answers.primary_outcome)
      }
      setSourcePackId((selected) => (
        options.compatible_source_packs.some((pack) => pack.pack_id === selected)
          ? selected
          : (options.compatible_source_packs[0]?.pack_id ?? '')
      ))
    }).catch((reason: unknown) => {
      if (current) setProposalOptionsError(errorMessage(reason))
    })
    return () => { current = false }
  }, [researchCase])

  async function loadCase(projectId: string, operation: 'load' | 'status' = 'load'): Promise<void> {
    const clean = projectId.trim()
    if (!clean) return
    const sequence = ++caseRequestSequence.current
    setBusy(operation)
    setError(null)
    try {
      const next = operation === 'status'
        ? await api.researchStatus(clean)
        : await api.researchCase(clean)
      if (sequence !== caseRequestSequence.current) return
      acceptCase(next)
    } catch (reason) {
      if (sequence === caseRequestSequence.current) setError(errorMessage(reason))
    } finally {
      if (sequence === caseRequestSequence.current) setBusy(null)
    }
  }

  useEffect(() => {
    if (initialProjectId) void loadCase(initialProjectId)
    // The Dockview parameter is immutable for this panel instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialProjectId])

  // The Research Backlog drives this panel through linked context (spec §2.2).
  const linkedProjectId = panelLink.linked.projectId
  useEffect(() => {
    if (linkedProjectId && linkedProjectId !== researchCase?.project_id) {
      setResearchCase(null)
      setReport(null)
      setDecisionView(null)
      setProposalOptions(null)
      setError(null)
      void loadCase(linkedProjectId)
    } else if (!linkedProjectId && researchCase) {
      caseRequestSequence.current += 1
      setResearchCase(null)
      setReport(null)
      setDecisionView(null)
      setProposalOptions(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedProjectId])

  // The shell's New Idea action focuses the capture form; it never creates anything.
  useEffect(
    () =>
      onNewIdea(() => {
        setShowCapture(true)
        window.setTimeout(() => {
          ideaRef.current?.focus()
          ideaRef.current?.scrollIntoView({ block: 'center' })
        }, 0)
      }),
    [],
  )

  async function capture(event: FormEvent): Promise<void> {
    event.preventDefault()
    if (!idea.trim()) return
    setBusy('capture')
    setError(null)
    try {
      const response = await api.researchCapture({
        idea,
        ...(caseName.trim() ? { name: caseName.trim() } : {}),
      })
      acceptCase(response.case)
      setIdea('')
      setCaseName('')
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(null)
    }
  }

  async function propose(event: FormEvent): Promise<void> {
    event.preventDefault()
    if (!researchCase || !proposalOptions || !proposalComplete || !answerBundleId) return
    setBusy('proposal')
    setError(null)
    const projectId = researchCase.project_id
    try {
      const response = await api.researchProposal(projectId, {
        source_pack_id: sourcePackId.trim(),
        answer_bundle_id: answerBundleId,
        dataset_ref_id: datasetRefId || null,
        expected_case_revision: proposalOptions.case_revision,
      })
      if (activeProjectRef.current === projectId) acceptCase(response.case)
    } catch (reason) {
      if (activeProjectRef.current === projectId) setError(errorMessage(reason))
    } finally {
      if (activeProjectRef.current === projectId) setBusy(null)
    }
  }

  async function launchPilot(): Promise<void> {
    if (!researchCase) return
    const projectId = researchCase.project_id
    setBusy('pilot')
    setError(null)
    try {
      const response = await api.researchPilot(projectId)
      if (activeProjectRef.current === projectId) acceptCase(response.case)
    } catch (reason) {
      if (activeProjectRef.current === projectId) setError(errorMessage(reason))
    } finally {
      if (activeProjectRef.current === projectId) setBusy(null)
    }
  }

  async function loadDecisionView(): Promise<void> {
    if (!researchCase) return
    const projectId = researchCase.project_id
    setBusy('decision')
    setError(null)
    try {
      const next = await api.researchDecisionView(projectId)
      if (activeProjectRef.current === projectId) setDecisionView(next)
    } catch (reason) {
      if (activeProjectRef.current === projectId) setError(errorMessage(reason))
    } finally {
      if (activeProjectRef.current === projectId) setBusy(null)
    }
  }

  // Selecting the Decision tab (or refreshing the case while on it) fetches the assembled view.
  useEffect(() => {
    if (view === 'decision' && researchCase && decisionView === null) {
      void loadDecisionView()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, researchCase, decisionView])

  useEffect(() => {
    if (view !== 'study' || !researchCase) return
    const projectId = researchCase.project_id
    let current = true
    setSemanticRead(null)
    setSemanticError(null)
    void api.researchSemanticProjection(projectId).then((projection) => {
      if (current && activeProjectRef.current === projectId) setSemanticRead(projection)
    }).catch((reason: unknown) => {
      if (current && activeProjectRef.current === projectId) setSemanticError(errorMessage(reason))
    })
    return () => { current = false }
  }, [view, researchCase])

  async function loadReport(): Promise<void> {
    if (!researchCase) return
    const projectId = researchCase.project_id
    setBusy('report')
    setError(null)
    try {
      const next = await api.researchProgressReport(projectId)
      if (activeProjectRef.current !== projectId) return
      setReport(next)
      if (next.report_schema === 'ResearchProgressReportV1') setResearchCase(next.case)
    } catch (reason) {
      if (activeProjectRef.current === projectId) setError(errorMessage(reason))
    } finally {
      if (activeProjectRef.current === projectId) setBusy(null)
    }
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Research Case</span>
        <span className="chip kind">GUIDED RESEARCH</span>
        <span className="muted">question → sources → data → bounded test → decision</span>
        <span className="spacer" />
        <span className="chip fail">TOUCH ID REQUIRED · NO OVERRIDE · NO TRADING</span>
      </div>
      <div className="panel-body panel-pad workbench research-cockpit" tabIndex={0}>
        {showCapture || !researchCase ? <div className="research-intake-grid">
          <form onSubmit={(event) => void capture(event)}>
            <span className="eyebrow">Capture a raw observation in your exact words</span>
            <textarea
              className="field"
              ref={ideaRef}
              value={idea}
              maxLength={8192}
              onChange={(event) => setIdea(event.target.value)}
              placeholder="Example: I notice the S&P 500 bounces after double bottoms on a 4h chart."
              aria-label="Raw research idea"
            />
            <div className="research-form-row">
              <input
                className="field"
                value={caseName}
                maxLength={200}
                onChange={(event) => setCaseName(event.target.value)}
                placeholder="Optional case name"
                aria-label="Research Case name"
              />
              <button className="btn primary" type="submit" disabled={!idea.trim() || busy !== null}>
                {busy === 'capture' ? 'capturing…' : 'capture · no compute'}
              </button>
            </div>
          </form>
          <form onSubmit={(event) => { event.preventDefault(); void loadCase(lookupId) }}>
            <span className="eyebrow">Open a known Research Case</span>
            <div className="research-form-row">
              <input
                className="field mono"
                value={lookupId}
                onChange={(event) => setLookupId(event.target.value)}
                placeholder="Project ID"
                aria-label="Research Case project ID"
              />
              <button className="btn" type="submit" disabled={!lookupId.trim() || busy !== null}>
                {busy === 'load' ? 'loading…' : 'open case'}
              </button>
            </div>
            <span className="muted">Or select a case in the Research Backlog — it drives this cockpit.</span>
          </form>
        </div> : null}

        {error ? <div className="workbench-notice" role="alert"><strong>REQUEST FAILED</strong><span>{error}</span></div> : null}

        {researchCase ? (
          <>
            <MaterialQuestions researchCase={researchCase} onRefresh={() => void loadCase(researchCase.project_id, 'status')} />
            <CaseHeader researchCase={researchCase} />
            <CanonicalNextAction researchCase={researchCase} onRefresh={() => void loadCase(researchCase.project_id, 'status')} />
            <div className="research-view-tabs" role="tablist" aria-label="Cockpit views">
              <button
                className={view === 'overview' ? 'btn primary' : 'btn'}
                type="button"
                role="tab"
                aria-selected={view === 'overview'}
                onClick={() => setView('overview')}
              >
                Overview
              </button>
              <button
                className={view === 'study' ? 'btn primary' : 'btn'}
                type="button"
                role="tab"
                aria-selected={view === 'study'}
                onClick={() => setView('study')}
              >
                Study
              </button>
              <button
                className={view === 'decision' ? 'btn primary' : 'btn'}
                type="button"
                role="tab"
                aria-selected={view === 'decision'}
                onClick={() => setView('decision')}
              >
                Decision
              </button>
            </div>
            {view === 'decision' ? (
              <>
                <DecisionViewSection view={decisionView} busy={busy} />
                <section className="research-decision-form" aria-label="Owner final disposition">
                  <div className="rd-head">Final disposition · owner Touch ID</div>
                  <OwnerDecisionForm researchCase={researchCase} onRefresh={() => void loadCase(researchCase.project_id, 'status')} />
                </section>
              </>
            ) : view === 'study' ? (
              <StudyStatusSection
                status={researchCase.study_status ?? null}
                researchCase={researchCase}
                onRefresh={() => void loadCase(researchCase.project_id, 'status')}
                semanticRead={semanticRead}
                semanticError={semanticError}
              />
            ) : (
              <CaseSummary
                researchCase={researchCase}
                report={report}
                busy={busy}
                onRefresh={() => void loadCase(researchCase.project_id, 'status')}
                onReport={() => void loadReport()}
                onPilot={() => void launchPilot()}
              />
            )}
            {view === 'overview' && researchCase.hypothesis_card ? (
              <HypothesisCardView card={researchCase.hypothesis_card} />
            ) : null}

            {view === 'overview' && researchProposalAvailable(researchCase.phase) ? (
              <form className="research-proposal" onSubmit={(event) => void propose(event)}>
                <div className="rd-head">Materialize the exact exploration proposal</div>
                {proposalOptionsError ? (
                  <div className="workbench-notice" role="alert">
                    <strong>PROPOSAL OPTIONS FAILED</strong><span>{proposalOptionsError}</span>
                  </div>
                ) : null}
                {!proposalOptions ? (
                  <div className="workbench-notice" role="status">
                    <strong>LOADING CURRENT OPTIONS</strong>
                    <span>Checking executable bundles, frozen packs, datasets, and case revision.</span>
                  </div>
                ) : null}
                {proposalOptions?.blockers.map((blocker) => {
                  const recovery = blockerRecovery(blocker.code)
                  return (
                    <div className="workbench-notice" role="alert" key={blocker.code}>
                      <strong>{blocker.message}</strong><span>{blocker.recovery_action}</span>
                      {recovery ? <button className="btn" type="button" onClick={recovery.action}>{recovery.label}</button> : null}
                    </div>
                  )
                })}
                <fieldset className="research-question-list">
                  <legend className="eyebrow">Valid answer bundle</legend>
                  {proposalOptions?.valid_answer_bundles.map((bundle) => (
                    <label className="workbench-notice" key={bundle.bundle_id}>
                      <input
                        type="radio"
                        name="research-answer-bundle"
                        value={bundle.bundle_id}
                        checked={answerBundleId === bundle.bundle_id}
                        disabled={!bundle.available}
                        onChange={() => selectAnswerBundle(bundle.bundle_id)}
                      />
                      <strong>
                        {bundle.label}
                        {bundle.bundle_id === proposalOptions.recommended_answer_bundle_id
                          ? ' · RECOMMENDED'
                          : ''}
                      </strong>
                      <span>
                        {bundle.blocked_reason ?? (bundle.requires_dataset
                          ? 'Requires an exact qualified dataset.'
                          : 'Synthetic D0 only; never real-market evidence.')}
                      </span>
                    </label>
                  ))}
                </fieldset>
                <div className="research-proposal-grid">
                  <label>
                    <span className="eyebrow">Frozen source pack</span>
                    <select className="field mono" value={sourcePackId} onChange={(event) => setSourcePackId(event.target.value)}>
                      <option value="">Select a project source pack</option>
                      {proposalOptions?.compatible_source_packs.map((pack) => (
                        <option key={pack.pack_id} value={pack.pack_id}>
                          {pack.source_ids.length} source{pack.source_ids.length === 1 ? '' : 's'} · {pack.pack_id.slice(0, 15)}…
                        </option>
                      ))}
                    </select>
                  </label>
                  {proposalOptions?.valid_answer_bundles.find(
                    (bundle) => bundle.bundle_id === answerBundleId,
                  )?.requires_dataset ? (
                    <label>
                      <span className="eyebrow">Qualified dataset</span>
                      <select className="field mono" value={datasetRefId} onChange={(event) => setDatasetRefId(event.target.value)}>
                        <option value="">Select the exact dataset</option>
                        {proposalOptions.compatible_datasets.map((dataset) => (
                          <option key={dataset.ref_id} value={dataset.ref_id}>
                            {dataset.instrument} · {dataset.provider} · {dataset.start_ts} to {dataset.end_ts}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                  <label><span className="eyebrow">Equal-duration chart construction</span><input className="field" value={CHART_OPTIONS.find((option) => option.value === chartConstruction)?.label ?? ''} readOnly /></label>
                  <label><span className="eyebrow">When the event becomes knowable</span><input className="field" value={EVENT_OPTIONS.find((option) => option.value === eventAvailability)?.label ?? ''} readOnly /></label>
                  <label><span className="eyebrow">Primary economic endpoint</span><input className="field" value={OUTCOME_OPTIONS.find((option) => option.value === primaryOutcome)?.label ?? ''} readOnly /></label>
                </div>
                <button className="btn primary" type="submit" disabled={!proposalComplete || busy !== null}>
                  {busy === 'proposal' ? 'materializing…' : 'materialize for owner review'}
                </button>
              </form>
            ) : null}
          </>
        ) : (
          <Placeholder big={linkedProjectId || busy === 'load' ? 'LOADING RESEARCH CASE' : 'NO ACTIVE RESEARCH CASE'}>
            {linkedProjectId || busy === 'load'
              ? 'Loading the selected project and discarding any response from an older selection.'
              : 'Capture an idea or select one from the Backlog. Nothing launches automatically.'}
          </Placeholder>
        )}
      </div>
    </div>
  )
}
