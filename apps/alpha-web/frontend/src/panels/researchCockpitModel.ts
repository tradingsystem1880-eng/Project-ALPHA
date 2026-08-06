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
  blocking_questions: string[]
  approval_ready: boolean
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
    blocking_questions: textList(payload.blocking_questions),
    approval_ready: payload.approval_ready === true,
  }
}

function finiteBudgetValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

/** Preserve heterogeneous budget units as separate rows; summing seconds, requests, and variants is invalid. */
export function researchBudgetRows(researchCase: ResearchCase): ResearchBudgetRow[] {
  const resources = new Set([
    ...Object.keys(researchCase.elapsed_budget),
    ...Object.keys(researchCase.remaining_budget),
  ])
  return [...resources].sort().map((resource) => ({
    resource,
    used: finiteBudgetValue(researchCase.elapsed_budget[resource]),
    remaining: finiteBudgetValue(researchCase.remaining_budget[resource]),
  }))
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
