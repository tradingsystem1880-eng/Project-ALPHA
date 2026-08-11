import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type {
  ResearchCase,
  ResearchCaseReport,
  ResearchDecisionView,
  ResearchGatePacket,
  ResearchMaterialAnswers,
} from '../api/types'
import { Placeholder } from '../components/Placeholder'
import { onNewIdea } from '../context/newIdea'
import type { PanelHandleProps } from '../context/panelHandle'
import { usePanelLinked } from '../context/usePanelLinked'
import { findingChipClass } from './researchChipModel'
import {
  researchBudgetRows,
  researchContractView,
  researchEvidenceFirewall,
  researchPhaseLabel,
  researchPilotEligibility,
  researchProposalAvailable,
} from './researchCockpitModel'
import { HypothesisCardView, ScorecardDetail, ScorecardStrip } from './researchViews'

type ChartConstruction = ResearchMaterialAnswers['chart_construction']
type EventAvailability = ResearchMaterialAnswers['event_availability']
type PrimaryOutcome = ResearchMaterialAnswers['primary_outcome']
type BusyOperation = 'capture' | 'load' | 'proposal' | 'pilot' | 'status' | 'report' | 'decision'
type CockpitView = 'overview' | 'decision'

const CHART_OPTIONS: ReadonlyArray<{ value: ChartConstruction; label: string }> = [
  { value: 'spy_rth_60m_four_hour_window', label: 'Synthetic SPY-like 60m D0 · four-hour window' },
]

const EVENT_OPTIONS: ReadonlyArray<{ value: EventAvailability; label: string }> = [
  { value: 'second_trough_confirmable', label: 'Second trough confirmable' },
]

const OUTCOME_OPTIONS: ReadonlyArray<{ value: PrimaryOutcome; label: string }> = [
  { value: 'four_trading_hour_return_25bp', label: 'Four trading hours · +25 bp' },
]

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason)
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

function ApprovalBoundary({ researchCase }: { researchCase: ResearchCase }) {
  if (researchCase.exploration_review.state !== 'pending') return null
  const contract = researchContractView(researchCase)
  if (!contract.approval_ready) {
    return (
      <div className="workbench-notice" role="note">
        <strong>GATE 1 OPERATOR UNAVAILABLE</strong>
        <span>
          This immutable proposal cannot be approved in Gate 1. Reject it through the owner-only
          CLI, then close or revise the case without claiming empirical evidence.
        </span>
        <code className="mono">
          alpha research reject exploration {researchCase.project_id}{' '}
          {researchCase.active_contract_id} --actor owner --reason &quot;&lt;your reason&gt;&quot;
        </code>
      </div>
    )
  }
  return (
    <div className="workbench-notice" role="note">
      <strong>HUMAN APPROVAL BOUNDARY</strong>
      <span>
        The Workstation can prepare and explain this contract, but cannot approve it. Review the
        exact immutable contract with Codex, then use the owner-only CLI approval path if satisfied.
      </span>
      <code className="mono">
        alpha research approve exploration {researchCase.project_id}{' '}
        {researchCase.active_contract_id} --actor owner --reason &quot;&lt;your reason&gt;&quot;
      </code>
    </div>
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
        <span className="research-case-next">{researchCase.next_action}</span>
      </div>
      {researchCase.scorecard ? <ScorecardStrip scorecard={researchCase.scorecard} /> : null}
    </div>
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

      <ApprovalBoundary researchCase={researchCase} />

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
          {contract.blocking_questions.length ? (
            <div className="research-question-list">
              <span className="eyebrow">Material questions requiring owner definition</span>
              <ol>{contract.blocking_questions.map((item) => <li key={item}>{item}</li>)}</ol>
            </div>
          ) : null}
        </section>

        <section>
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
  const [lookupId, setLookupId] = useState(initialProjectId)
  const [idea, setIdea] = useState('')
  const [caseName, setCaseName] = useState('')
  const [sourcePackId, setSourcePackId] = useState('')
  const [chartConstruction, setChartConstruction] = useState<ChartConstruction | ''>('')
  const [eventAvailability, setEventAvailability] = useState<EventAvailability | ''>('')
  const [primaryOutcome, setPrimaryOutcome] = useState<PrimaryOutcome | ''>('')
  const [busy, setBusy] = useState<BusyOperation | null>(null)
  const [error, setError] = useState<string | null>(null)

  const proposalComplete = useMemo(
    () => sourcePackId.trim() !== '' && chartConstruction !== ''
      && eventAvailability !== '' && primaryOutcome !== '',
    [chartConstruction, eventAvailability, primaryOutcome, sourcePackId],
  )

  function acceptCase(next: ResearchCase): void {
    setResearchCase(next)
    setLookupId(next.project_id)
    setSourcePackId(next.source_pack_id ?? '')
    setReport(null)
    setDecisionView(null)
  }

  async function loadCase(projectId: string, operation: 'load' | 'status' = 'load'): Promise<void> {
    const clean = projectId.trim()
    if (!clean) return
    setBusy(operation)
    setError(null)
    try {
      acceptCase(operation === 'status'
        ? await api.researchStatus(clean)
        : await api.researchCase(clean))
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(null)
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
      void loadCase(linkedProjectId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedProjectId])

  // The shell's New Idea action focuses the capture form; it never creates anything.
  useEffect(
    () =>
      onNewIdea(() => {
        ideaRef.current?.focus()
        ideaRef.current?.scrollIntoView({ block: 'center' })
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
    if (!researchCase || !proposalComplete || !chartConstruction
      || !eventAvailability || !primaryOutcome) return
    setBusy('proposal')
    setError(null)
    try {
      const response = await api.researchProposal(researchCase.project_id, {
        source_pack_id: sourcePackId.trim(),
        answers: {
          chart_construction: chartConstruction,
          event_availability: eventAvailability,
          primary_outcome: primaryOutcome,
        },
      })
      acceptCase(response.case)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(null)
    }
  }

  async function launchPilot(): Promise<void> {
    if (!researchCase) return
    setBusy('pilot')
    setError(null)
    try {
      const response = await api.researchPilot(researchCase.project_id)
      acceptCase(response.case)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(null)
    }
  }

  async function loadDecisionView(): Promise<void> {
    if (!researchCase) return
    setBusy('decision')
    setError(null)
    try {
      setDecisionView(await api.researchDecisionView(researchCase.project_id))
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(null)
    }
  }

  // Selecting the Decision tab (or refreshing the case while on it) fetches the assembled view.
  useEffect(() => {
    if (view === 'decision' && researchCase && decisionView === null) {
      void loadDecisionView()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, researchCase, decisionView])

  async function loadReport(): Promise<void> {
    if (!researchCase) return
    setBusy('report')
    setError(null)
    try {
      const next = await api.researchProgressReport(researchCase.project_id)
      setReport(next)
      if (next.report_schema === 'ResearchProgressReportV1') setResearchCase(next.case)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="title">Research Cockpit</span>
        <span className="chip kind">GATE 1 SAFE REST</span>
        <span className="muted">capture · read · propose · D0 pilot · status · report</span>
        <span className="spacer" />
        <span className="chip fail">NO APPROVAL · D2 · DEEP · TRADING</span>
      </div>
      <div className="panel-body panel-pad workbench research-cockpit" tabIndex={0}>
        <div className="sandbox-banner">
          RESEARCH SANDBOX · SYNTHETIC D0 IS NOT REAL-MARKET EVIDENCE OR A TRADING SIGNAL
        </div>

        <div className="research-intake-grid">
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
        </div>

        {error ? <div className="workbench-notice" role="alert"><strong>REQUEST FAILED</strong><span>{error}</span></div> : null}

        {researchCase ? (
          <>
            <CaseHeader researchCase={researchCase} />
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
              <DecisionViewSection view={decisionView} busy={busy} />
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
                <div className="workbench-notice">
                  <strong>SOURCE PACK REQUIRED</strong>
                  <span>Create and freeze the screened source pack through the trusted-local CLI, then paste its immutable ID. This REST surface cannot fetch sources or approve the proposal.</span>
                </div>
                <div className="research-proposal-grid">
                  <label><span className="eyebrow">Frozen source pack ID</span><input className="field mono" value={sourcePackId} onChange={(event) => setSourcePackId(event.target.value)} /></label>
                  <label><span className="eyebrow">Equal-duration chart construction</span><select className="field" value={chartConstruction} onChange={(event) => setChartConstruction(event.target.value as ChartConstruction | '')}><option value="">Choose explicitly…</option>{CHART_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                  <label><span className="eyebrow">When the event becomes knowable</span><select className="field" value={eventAvailability} onChange={(event) => setEventAvailability(event.target.value as EventAvailability | '')}><option value="">Choose explicitly…</option>{EVENT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                  <label><span className="eyebrow">Primary economic endpoint</span><select className="field" value={primaryOutcome} onChange={(event) => setPrimaryOutcome(event.target.value as PrimaryOutcome | '')}><option value="">Choose explicitly…</option>{OUTCOME_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                </div>
                <button className="btn primary" type="submit" disabled={!proposalComplete || busy !== null}>
                  {busy === 'proposal' ? 'materializing…' : 'materialize for owner review'}
                </button>
              </form>
            ) : null}
          </>
        ) : (
          <Placeholder big="NO ACTIVE RESEARCH CASE">
            Capture an idea or open a known project ID. Nothing launches automatically.
          </Placeholder>
        )}
      </div>
    </div>
  )
}
