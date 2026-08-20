import { describe, expect, it } from 'vitest'

import type { ResearchCase } from '../api/types'
import {
  RESEARCH_DISPOSITIONS,
  RESEARCH_EXECUTION_STATES,
  RESEARCH_OUTCOMES,
  RESEARCH_PHASES,
  RESEARCH_RESPONSIBILITIES,
  headlineResearchCharts,
  researchBudgetRows,
  researchCaseBucket,
  researchCaseProgress,
  researchContractView,
  researchEvidenceFirewall,
  researchPilotEligibility,
  researchProposalAvailable,
  sortResearchCases,
  type ResearchCaseSummary,
  type ResearchChartSummary,
} from './researchCockpitModel'

describe('Research Cockpit contract mirrors', () => {
  it('locks the canonical phase, execution, outcome, disposition, and responsibility values', () => {
    expect(RESEARCH_PHASES).toEqual([
      'captured',
      'triage',
      'exploration_review',
      'pilot',
      'deep_research',
      'confirmation_review',
      'sealed_confirmation',
      'research_decision',
      'closed',
    ])
    expect(RESEARCH_EXECUTION_STATES).toEqual([
      'idle', 'queued', 'running', 'paused', 'blocked', 'failed',
    ])
    expect(RESEARCH_OUTCOMES).toEqual([
      'SUPPORTED', 'CONTRADICTED', 'INCONCLUSIVE', 'INVALID',
    ])
    expect(RESEARCH_DISPOSITIONS).toEqual([
      'advance_to_strategy', 'revise', 'park', 'reject',
    ])
    expect(RESEARCH_RESPONSIBILITIES).toEqual(['codex', 'owner'])
  })
})

function researchCase(overrides: Partial<ResearchCaseSummary>): ResearchCaseSummary {
  return {
    case_id: 'case-1',
    title: 'SPY double bottom',
    original_idea: 'SPY bounces after a double bottom on a four-hour chart',
    phase: 'triage',
    execution_state: 'idle',
    outcome: null,
    disposition: null,
    next_action: 'Inspect source and data feasibility',
    responsibility: 'codex',
    latest_finding: null,
    blocker: null,
    recovery_action: null,
    completed_milestones: 1,
    total_milestones: 7,
    owner_pinned: false,
    priority: {
      falsifiability: 2,
      data_readiness: 2,
      novelty: 1,
      information_gain_per_cost: 2,
    },
    budget: {
      approved_units: 20,
      consumed_units: 4,
      unit: 'minutes',
    },
    updated_at: '2026-08-06T01:00:00Z',
    ...overrides,
  }
}

describe('Research Cockpit case projection', () => {
  it('keeps phase and execution state separate while deriving owner-facing buckets', () => {
    expect(researchCaseBucket(researchCase({ responsibility: 'owner' }))).toBe('needs_owner')
    expect(researchCaseBucket(researchCase({ execution_state: 'running' }))).toBe('running')
    expect(researchCaseBucket(researchCase({ execution_state: 'blocked' }))).toBe('blocked')
    expect(researchCaseBucket(researchCase({ execution_state: 'failed' }))).toBe('blocked')
    expect(researchCaseBucket(researchCase({
      phase: 'closed',
      outcome: 'CONTRADICTED',
      disposition: 'reject',
    }))).toBe('closed')
    expect(researchCaseBucket(researchCase({}))).toBe('ready')
  })

  it('sorts needs-owner before running/ready/blocked/closed and respects owner pins within a bucket', () => {
    const rows = [
      researchCase({ case_id: 'closed', phase: 'closed', outcome: 'INCONCLUSIVE', disposition: 'park' }),
      researchCase({ case_id: 'blocked', execution_state: 'blocked' }),
      researchCase({ case_id: 'ready-low', priority: { falsifiability: 1, data_readiness: 1, novelty: 1, information_gain_per_cost: 1 } }),
      researchCase({ case_id: 'running', execution_state: 'running' }),
      researchCase({ case_id: 'owner', responsibility: 'owner' }),
      researchCase({ case_id: 'ready-pinned', owner_pinned: true, priority: { falsifiability: 0, data_readiness: 0, novelty: 0, information_gain_per_cost: 0 } }),
      researchCase({ case_id: 'ready-high', priority: { falsifiability: 2, data_readiness: 2, novelty: 2, information_gain_per_cost: 2 } }),
    ]

    expect(sortResearchCases(rows).map((row) => row.case_id)).toEqual([
      'owner',
      'running',
      'ready-pinned',
      'ready-high',
      'ready-low',
      'blocked',
      'closed',
    ])
  })

  it('clamps milestone and budget progress without inventing progress for zero totals', () => {
    expect(researchCaseProgress(researchCase({ completed_milestones: 9, total_milestones: 7 })))
      .toEqual({ milestone_fraction: 1, budget_fraction: 0.2 })
    expect(researchCaseProgress(researchCase({
      completed_milestones: 1,
      total_milestones: 0,
      budget: { approved_units: 0, consumed_units: 2, unit: 'minutes' },
    }))).toEqual({ milestone_fraction: 0, budget_fraction: null })
  })
})

describe('Research Cockpit chart projection', () => {
  it('shows at most one preregistered headline chart per decision category in canonical order', () => {
    const charts: ResearchChartSummary[] = [
      { chart_id: 'confounder-late', category: 'confounders', registered_order: 8, question: 'late', conclusion: 'late', caveat: 'late' },
      { chart_id: 'null', category: 'null_multiplicity', registered_order: 6, question: 'null?', conclusion: 'null', caveat: 'power' },
      { chart_id: 'primary', category: 'primary_effect', registered_order: 2, question: 'effect?', conclusion: 'small', caveat: 'wide CI' },
      { chart_id: 'event', category: 'event_validity', registered_order: 1, question: 'valid?', conclusion: 'yes', caveat: 'synthetic proxy' },
      { chart_id: 'parameters', category: 'parameter_stability', registered_order: 3, question: 'stable?', conclusion: 'mixed', caveat: 'small cells' },
      { chart_id: 'confounder-first', category: 'confounders', registered_order: 4, question: 'Tuesday?', conclusion: 'material', caveat: 'interaction' },
      { chart_id: 'transportability', category: 'transportability', registered_order: 5, question: 'transportable?', conclusion: 'QQQ only', caveat: 'correlated beta; not independent replication' },
      { chart_id: 'appendix', category: 'appendix', registered_order: 0, question: 'extra?', conclusion: 'extra', caveat: 'extra' },
    ]

    expect(headlineResearchCharts(charts).map((chart) => chart.chart_id)).toEqual([
      'event',
      'primary',
      'parameters',
      'confounder-first',
      'transportability',
      'null',
    ])
  })
})

function projectedCase(overrides: Partial<ResearchCase> = {}): ResearchCase {
  return {
    schema_version: 1,
    project_id: 'project-1',
    project_name: 'SPY double bottom',
    phase: 'exploration_review',
    execution_state: 'idle',
    active_contract_id: 'rc-1',
    active_contract: {
      contract_id: 'rc-1',
      project_id: 'project-1',
      scope: 'exploration',
      parent_contract_id: null,
      payload: {
        raw_idea: 'SPY may bounce after a point-in-time double bottom.',
        approval_ready: true,
        blocking_questions: [],
        thesis: {
          mechanism: 'Revisited support may concentrate demand.',
          prediction: 'Forward returns exceed matched controls.',
          interpretation: 'Predictive association, not causation.',
          alternatives: ['weekday', 'volatility regime'],
        },
      },
      created_by: 'codex',
      author_kind: 'agent',
      created_at: '2026-08-06T00:00:00Z',
      review_state: 'pending',
      latest_review: null,
    },
    exploration_contract_id: 'rc-1',
    confirmation_contract_id: null,
    exploration_review: { state: 'pending', event: null },
    confirmation_review: { state: 'pending', event: null },
    research_decision: null,
    next_action: 'Owner reviews the exact contract.',
    responsibility: 'owner',
    blocker: null,
    recovery: null,
    latest_finding: null,
    milestones: [],
    completed_milestones: [],
    remaining_milestones: [
      'pilot',
      'deep_research',
      'confirmation_review',
      'sealed_confirmation',
      'research_decision',
      'closed',
    ],
    elapsed_time_seconds: 60,
    elapsed_budget: { wall_seconds: 60, source_requests: 2 },
    remaining_budget: { wall_seconds: 120, variants: 8 },
    active_job_id: null,
    checkpoint: null,
    hashes: {},
    source_pack_id: 'sp-1',
    attempt_count: 0,
    terminal_attempt_count: 0,
    unfinalized_launch_count: 0,
    remaining_launches: 3,
    latest_launch_reservation_id: null,
    latest_launch_number: null,
    latest_attempt_id: null,
    latest_run_id: null,
    latest_run_fingerprint: null,
    d2_state: 'sealed',
    d2_boundary_hash: 'sha256:boundary',
    d2_history: [],
    d3_state: 'not_sealed',
    ...overrides,
  }
}

describe('Research Cockpit REST projection helpers', () => {
  it('keeps the proposal action reachable from freshly captured and triage cases only', () => {
    expect(researchProposalAvailable('captured')).toBe(true)
    expect(researchProposalAvailable('triage')).toBe(true)
    expect(researchProposalAvailable('exploration_review')).toBe(false)
    expect(researchProposalAvailable('pilot')).toBe(false)
  })

  it('reads thesis text without treating it as an empirical result', () => {
    expect(researchContractView(projectedCase())).toEqual({
      raw_idea: 'SPY may bounce after a point-in-time double bottom.',
      mechanism: 'Revisited support may concentrate demand.',
      prediction: 'Forward returns exceed matched controls.',
      interpretation: 'Predictive association, not causation.',
      alternatives: ['weekday', 'volatility regime'],
      blocking_questions: [],
      valid_answer_bundles: [],
      recommended_answer_bundle_id: null,
      approval_ready: true,
    })
  })

  it('preserves object-shaped material questions and choice consequences', () => {
    const researchCase = projectedCase()
    researchCase.active_contract.payload.blocking_questions = [
      {
        id: 'chart_construction',
        prompt: 'Which exact chart defines the claim?',
        blocking_reason: 'It changes the event population.',
        recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
        choices: [
          {
            id: 'spy_rth_60m_four_hour_window',
            label: 'SPY 60-minute RTH proxy',
            consequence: 'Uses equal 60-minute bars.',
            availability: 'available',
            blocked_reason: null,
          },
        ],
      },
    ]

    expect(researchContractView(researchCase).blocking_questions).toEqual([
      {
        id: 'chart_construction',
        prompt: 'Which exact chart defines the claim?',
        blocking_reason: 'It changes the event population.',
        recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
        choices: [
          {
            id: 'spy_rth_60m_four_hour_window',
            label: 'SPY 60-minute RTH proxy',
            consequence: 'Uses equal 60-minute bars.',
            availability: 'available',
            blocked_reason: null,
          },
        ],
      },
    ])
  })

  it('keeps heterogeneous budget resources separate', () => {
    expect(researchBudgetRows(projectedCase())).toEqual([
      { resource: 'source_requests', used: 2, remaining: null },
      { resource: 'variants', used: null, remaining: 8 },
      { resource: 'wall_seconds', used: 60, remaining: 120 },
    ])
  })

  it('allows only an approved, idle pilot and explains the evidence firewall', () => {
    expect(researchPilotEligibility(projectedCase())).toEqual({
      allowed: false,
      reason: 'The exact exploration contract still needs human approval outside REST.',
    })
    const pilot = projectedCase({
      phase: 'pilot',
      exploration_review: { state: 'approved', event: null },
    })
    expect(researchPilotEligibility(pilot)).toEqual({
      allowed: true,
      reason: 'Runs synthetic D0 only; it cannot create real-market evidence.',
    })
    expect(researchEvidenceFirewall(pilot)).toContain('D2 SEALED')
    expect(researchEvidenceFirewall(pilot)).toContain('D3 NOT SEALED')
  })
})
