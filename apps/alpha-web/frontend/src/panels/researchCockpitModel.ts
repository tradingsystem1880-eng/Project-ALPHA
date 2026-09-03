import type { ResearchCase } from '../api/types'

export const RESEARCH_PHASES = [
  'captured',
  'triage',
  'exploration_review',
  'pilot',
  'deep_research',
  'confirmation_review',
  'sealed_confirmation',
  'research_decision',
  'closed',
] as const

export const RESEARCH_EXECUTION_STATES = [
  'idle',
  'queued',
  'running',
  'paused',
  'blocked',
  'failed',
] as const

export const RESEARCH_OUTCOMES = [
  'SUPPORTED',
  'CONTRADICTED',
  'INCONCLUSIVE',
  'INVALID',
] as const

export const RESEARCH_DISPOSITIONS = [
  'advance_to_strategy',
  'revise',
  'park',
  'reject',
] as const

export const RESEARCH_RESPONSIBILITIES = ['codex', 'owner'] as const

export type ResearchPhase = typeof RESEARCH_PHASES[number]
export type ResearchExecutionState = typeof RESEARCH_EXECUTION_STATES[number]
export type ResearchOutcome = typeof RESEARCH_OUTCOMES[number]
export type ResearchDisposition = typeof RESEARCH_DISPOSITIONS[number]
export type ResearchResponsibility = typeof RESEARCH_RESPONSIBILITIES[number]
export type ResearchCaseBucket = 'needs_owner' | 'running' | 'ready' | 'blocked' | 'closed'

export interface ResearchPriority {
  falsifiability: number
  data_readiness: number
  novelty: number
  information_gain_per_cost: number
}

export interface ResearchBudgetProjection {
  approved_units: number
  consumed_units: number
  unit: 'minutes' | 'compute_units'
}

export interface ResearchCaseSummary {
  case_id: string
  title: string
  original_idea: string
  phase: ResearchPhase
  execution_state: ResearchExecutionState
  outcome: ResearchOutcome | null
  disposition: ResearchDisposition | null
  next_action: string
  responsibility: ResearchResponsibility
  latest_finding: string | null
  blocker: string | null
  recovery_action: string | null
  completed_milestones: number
  total_milestones: number
  owner_pinned: boolean
  priority: ResearchPriority
  budget: ResearchBudgetProjection
  updated_at: string
}

export type ResearchChartCategory =
  | 'event_validity'
  | 'primary_effect'
  | 'parameter_stability'
  | 'confounders'
  | 'transportability'
  | 'null_multiplicity'
  | 'appendix'

export interface ResearchChartSummary {
  chart_id: string
  category: ResearchChartCategory
  registered_order: number
  question: string
  conclusion: string
  caveat: string
}

export interface ResearchContractView {
  raw_idea: string | null
  mechanism: string | null
  prediction: string | null
  interpretation: string | null
  alternatives: string[]
  blocking_questions: ResearchMaterialQuestionV1[]
  valid_answer_bundles: ResearchAnswerBundleV1[]
  recommended_answer_bundle_id: string | null
  approval_ready: boolean
}

export interface ResearchMaterialChoiceV1 {
  id: string
  label: string
  consequence: string
  availability: 'available' | 'unavailable'
  blocked_reason: string | null
}

export interface ResearchMaterialQuestionV1 {
  id: string
  prompt: string
  blocking_reason: string
  choices: ResearchMaterialChoiceV1[]
  recommended_answer_bundle_id: string | null
}

export interface ResearchAnswerBundleV1 {
  bundle_id: string
  label: string
  answers: {
    chart_construction: string
    event_availability: string
    primary_outcome: string
  }
  requires_dataset: boolean
}

export interface ResearchBudgetRow {
  resource: string
  used: number | null
  remaining: number | null
}

const BUCKET_ORDER: Readonly<Record<ResearchCaseBucket, number>> = {
  needs_owner: 0,
  running: 1,
  ready: 2,
  blocked: 3,
  closed: 4,
}

const HEADLINE_CATEGORIES: ReadonlyArray<Exclude<ResearchChartCategory, 'appendix'>> = [
  'event_validity',
  'primary_effect',
  'parameter_stability',
  'confounders',
  'transportability',
  'null_multiplicity',
]

export function researchCaseBucket(researchCase: ResearchCaseSummary): ResearchCaseBucket {
  if (researchCase.phase === 'closed') return 'closed'
  if (researchCase.execution_state === 'blocked' || researchCase.execution_state === 'failed') return 'blocked'
  if (researchCase.responsibility === 'owner') return 'needs_owner'
  if (researchCase.execution_state === 'queued' || researchCase.execution_state === 'running') return 'running'
  return 'ready'
}

function priorityScore(priority: ResearchPriority): number {
  return priority.falsifiability
    + priority.data_readiness
    + priority.novelty
    + priority.information_gain_per_cost
}

export function sortResearchCases(cases: ResearchCaseSummary[]): ResearchCaseSummary[] {
  return [...cases].sort((left, right) => {
    const bucketDelta = BUCKET_ORDER[researchCaseBucket(left)]
      - BUCKET_ORDER[researchCaseBucket(right)]
    if (bucketDelta !== 0) return bucketDelta
    if (left.owner_pinned !== right.owner_pinned) return left.owner_pinned ? -1 : 1
    const priorityDelta = priorityScore(right.priority) - priorityScore(left.priority)
    if (priorityDelta !== 0) return priorityDelta
    const updatedDelta = right.updated_at.localeCompare(left.updated_at)
    return updatedDelta !== 0 ? updatedDelta : left.case_id.localeCompare(right.case_id)
  })
}

function boundedFraction(numerator: number, denominator: number): number | null {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0) return null
  return Math.max(0, Math.min(1, numerator / denominator))
}

export function researchCaseProgress(researchCase: ResearchCaseSummary): {
  milestone_fraction: number
  budget_fraction: number | null
} {
  return {
    milestone_fraction: boundedFraction(
      researchCase.completed_milestones,
      researchCase.total_milestones,
    ) ?? 0,
    budget_fraction: boundedFraction(
      researchCase.budget.consumed_units,
      researchCase.budget.approved_units,
    ),
  }
}

export function headlineResearchCharts(charts: ResearchChartSummary[]): ResearchChartSummary[] {
  return HEADLINE_CATEGORIES.flatMap((category) => {
    const candidates = charts
      .filter((chart) => chart.category === category)
      .sort((left, right) => left.registered_order - right.registered_order
        || left.chart_id.localeCompare(right.chart_id))
    return candidates[0] === undefined ? [] : [candidates[0]]
  })
}

export function researchPhaseLabel(phase: ResearchPhase): string {
  return phase.replaceAll('_', ' ')
}

export function researchBucketLabel(bucket: ResearchCaseBucket): string {
  if (bucket === 'needs_owner') return 'Needs you'
  return bucket.replaceAll('_', ' ')
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function textValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function materialQuestions(value: unknown): ResearchMaterialQuestionV1[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const question = objectValue(item)
    if (!question) return []
    const id = textValue(question.id)
    const prompt = textValue(question.prompt)
    const blockingReason = textValue(question.blocking_reason)
    if (!id || !prompt || !blockingReason || !Array.isArray(question.choices)) return []
    const choices = question.choices.flatMap((rawChoice) => {
      const choice = objectValue(rawChoice)
      if (!choice) return []
      const choiceId = textValue(choice.id)
      const label = textValue(choice.label)
      const consequence = textValue(choice.consequence)
      const availability: ResearchMaterialChoiceV1['availability'] | null =
        choice.availability === 'available' || choice.availability === 'unavailable'
          ? choice.availability
          : null
      if (!choiceId || !label || !consequence
        || (availability !== 'available' && availability !== 'unavailable')) return []
      return [{
        id: choiceId,
        label,
        consequence,
        availability,
        blocked_reason: textValue(choice.blocked_reason),
      }]
    })
    return [{
      id,
      prompt,
      blocking_reason: blockingReason,
      choices,
      recommended_answer_bundle_id: textValue(question.recommended_answer_bundle_id),
    }]
  })
}

function answerBundles(value: unknown): ResearchAnswerBundleV1[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const bundle = objectValue(item)
    const answers = objectValue(bundle?.answers)
    const bundleId = textValue(bundle?.bundle_id)
    const label = textValue(bundle?.label)
    const chart = textValue(answers?.chart_construction)
    const event = textValue(answers?.event_availability)
    const outcome = textValue(answers?.primary_outcome)
    if (!bundleId || !label || !chart || !event || !outcome
      || typeof bundle?.requires_dataset !== 'boolean') return []
    return [{
      bundle_id: bundleId,
      label,
      answers: {
        chart_construction: chart,
        event_availability: event,
        primary_outcome: outcome,
      },
      requires_dataset: bundle.requires_dataset,
    }]
  })
}

/** Read only explanatory fields from the immutable active contract; never infer empirical results. */
export function researchContractView(researchCase: ResearchCase): ResearchContractView {
  const payload = objectValue(researchCase.active_contract.payload) ?? {}
  const thesis = objectValue(payload.thesis) ?? {}
  return {
    raw_idea: textValue(payload.raw_idea),
    mechanism: textValue(thesis.mechanism),
    prediction: textValue(thesis.prediction),
    interpretation: textValue(thesis.interpretation),
    alternatives: textList(thesis.alternatives),
    blocking_questions: materialQuestions(payload.blocking_questions),
    valid_answer_bundles: answerBundles(payload.valid_answer_bundles),
    recommended_answer_bundle_id: textValue(payload.recommended_answer_bundle_id),
    approval_ready: payload.approval_ready === true,
  }
}

function finiteBudgetValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

/** Preserve heterogeneous budget units as separate rows; summing seconds, requests, and variants is invalid. */
export function researchBudgetValueRows(
  elapsed: Record<string, unknown>,
  remaining: Record<string, unknown>,
): ResearchBudgetRow[] {
  const resources = new Set([
    ...Object.keys(elapsed),
    ...Object.keys(remaining),
  ])
  return [...resources].sort().map((resource) => ({
    resource,
    used: finiteBudgetValue(elapsed[resource]),
    remaining: finiteBudgetValue(remaining[resource]),
  }))
}

export function researchBudgetRows(researchCase: ResearchCase): ResearchBudgetRow[] {
  return researchBudgetValueRows(researchCase.elapsed_budget, researchCase.remaining_budget)
}

export function researchPilotEligibility(researchCase: ResearchCase): {
  allowed: boolean
  reason: string
} {
  if (researchCase.phase !== 'pilot') {
    return {
      allowed: false,
      reason: researchCase.exploration_review.state === 'pending'
        ? 'The exact exploration contract still needs human approval outside REST.'
        : 'The deterministic D0 pilot is available only in the pilot phase.',
    }
  }
  if (researchCase.exploration_review.state !== 'approved') {
    return { allowed: false, reason: 'The exploration contract is not approved.' }
  }
  if (researchCase.execution_state === 'running' || researchCase.execution_state === 'queued') {
    return { allowed: false, reason: 'A bounded research attempt is already active.' }
  }
  return { allowed: true, reason: 'Runs synthetic D0 only; it cannot create real-market evidence.' }
}

/** A captured case resolves its one material question batch through the same proposal action as triage. */
export function researchProposalAvailable(phase: ResearchPhase): boolean {
  return phase === 'captured' || phase === 'triage'
}

export function researchEvidenceFirewall(researchCase: ResearchCase): string {
  const d2 = researchCase.d2_state.toUpperCase()
  const d3 = researchCase.d3_state.replaceAll('_', ' ').toUpperCase()
  return `D2 ${d2}: research confirmation remains governed by its immutable boundary. `
    + `D3 ${d3}: final strategy holdout remains outside this Research Case surface.`
}

// ---------------------------------------------------------------------------------------------
// Owner steps (Phase 4 P4): what the owner can complete from the terminal right now. Derived from
// the case's own fields only — phase, review states, execution state, responsibility — and never
// from browser-side authority: every offered step goes through the owner-auth challenge/perform
// routes, where the CLI re-validates it. A step the vocabulary keeps on the trusted CLI is
// returned as the exact command to copy, with the ADR that keeps it there.
// ---------------------------------------------------------------------------------------------

export type OwnerActionStep =
  | { kind: 'action'; actionType: 'launch_d1'; label: string; consequence: string; payload: Record<string, never> }
  | { kind: 'action'; actionType: 'launch_d2'; label: string; consequence: string; payload: Record<string, never> }
  | { kind: 'revise'; sourcePackId: string | null }
  | { kind: 'decide' }
  | { kind: 'review'; scope: 'exploration' | 'confirmation' }
  | { kind: 'waiting'; text: string }
  | { kind: 'none'; text: string }

const ACTIVE_EXECUTION = new Set<string>(['queued', 'running', 'paused'])

/** The owner step the case is at, or why there is none. */
export function ownerStep(researchCase: ResearchCase): OwnerActionStep {
  if (researchCase.phase === 'closed') return { kind: 'none', text: 'This case is closed.' }
  if (ACTIVE_EXECUTION.has(researchCase.execution_state)) {
    return { kind: 'waiting', text: `A bounded research attempt is ${researchCase.execution_state}; nothing to decide until it finishes.` }
  }
  if (researchCase.responsibility !== 'owner') {
    return { kind: 'waiting', text: 'Codex holds the next step; the case will come back to you.' }
  }
  const view = researchContractView(researchCase)
  if (researchCase.exploration_review.state === 'pending') {
    if (view.blocking_questions.length) return { kind: 'revise', sourcePackId: researchCase.source_pack_id }
    return { kind: 'review', scope: 'exploration' }
  }
  if (researchCase.exploration_review.state === 'rejected') {
    return { kind: 'revise', sourcePackId: researchCase.source_pack_id }
  }
  if (researchCase.phase === 'pilot' || researchCase.phase === 'deep_research') {
    return {
      kind: 'action',
      actionType: 'launch_d1',
      label: 'launch D1',
      consequence: 'Launch the frozen D1 analysis plan on the discovery share only (alpha research run deep); it reads no sealed data.',
      payload: {},
    }
  }
  if (researchCase.phase === 'confirmation_review' || researchCase.confirmation_review.state === 'pending') {
    return { kind: 'review', scope: 'confirmation' }
  }
  if (researchCase.phase === 'sealed_confirmation') {
    if (researchCase.confirmation_review.state !== 'approved') {
      return { kind: 'waiting', text: 'The confirmation contract is not approved; D2 cannot be launched.' }
    }
    return {
      kind: 'action',
      actionType: 'launch_d2',
      label: 'launch D2',
      consequence: 'Run the one-shot D2 confirmation (alpha research run confirm): the frozen primary reads the sealed share exactly once.',
      payload: {},
    }
  }
  if (researchCase.phase === 'research_decision') return { kind: 'decide' }
  return { kind: 'waiting', text: researchCase.next_action }
}

/** The trusted-CLI steps the browser deliberately cannot perform, with the ADR that keeps them there. */
export const CLI_ONLY = {
  recovery: {
    command: 'uv run alpha owner-auth recover --reason "<credential recovery reason>"',
    why: 'ADR-0030: credential recovery is a trusted local CLI act; the browser never asserts owner presence.',
  },
  assetMaster: {
    why: 'ADR-0032: the reviewed asset master is regenerated by the receipted CLI, never from the browser.',
  },
  holdoutReveal: {
    why: 'ADR-0014: the holdout reveal is a trusted local CLI ceremony; the browser cannot assert an owner name.',
  },
} as const
