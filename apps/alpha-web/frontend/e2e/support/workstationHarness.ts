import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import type { components } from '../../src/api/generated'

// The desk presets are gone: each of these is now a screen laid out for one job, reached
// from the top-bar tabs rather than assembled by the user.
const SCREENS = [
  { label: 'Research', id: 'explore' },
  { label: 'Build', id: 'build' },
  { label: 'Results', id: 'results' },
  { label: 'Compare', id: 'compare' },
  { label: 'Studios', id: 'studios' },
  { label: 'Operate', id: 'operate' },
] as const

const EMPTY_PAGE = { items: [], limit: 50, offset: 0, has_more: false }
const SYSTEM_STATUS = {
  paper_enabled: false,
  ibkr_paper_enabled: false,
  counts: { symbols: 0, snapshots: 0 },
  data_dir: {
    path: '/deterministic-test-data',
    exists: true,
    readable: true,
    writable: true,
    free_bytes: 1_000_000_000,
  },
  nautilus: { installed_version: '1.228.0', pinned_version: '1.228.0', matches_pin: true },
  kronos_cache: { configured: false, exists: false, local_only: true, path: null },
}

const RESEARCH_RAW_IDEA = 'SPY may bounce after a point-in-time double bottom.'
const RESEARCH_QUESTIONS: components['schemas']['ResearchMaterialQuestionV1'][] = [
  {
    id: 'chart_construction',
    prompt: 'Which exact instrument and equal-duration chart defines the claim?',
    blocking_reason: 'It changes the primary instrument and event population.',
    choices: [
      {
        id: 'spy_rth_60m_four_hour_window',
        label: 'SPY 60-minute RTH proxy',
        consequence: 'Uses equal 60-minute bars and a four-trading-hour pattern window.',
        availability: 'available',
        blocked_reason: null,
      },
      {
        id: 'spy_extended_fixed_4h',
        label: 'SPY fixed four-hour extended-hours bars',
        consequence: 'Would require a separately registered extended-session operator.',
        availability: 'unavailable',
        blocked_reason: 'No registered end-to-end research operator uses this choice.',
      },
    ],
    recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
  },
  {
    id: 'event_availability',
    prompt: 'When is the event knowable without future information?',
    blocking_reason: 'It changes event timing and prevents a look-ahead detector.',
    choices: [{
      id: 'second_trough_confirmable',
      label: 'Second trough confirmable',
      consequence: 'Fires only after required right-pivot observations are available.',
      availability: 'available',
      blocked_reason: null,
    }],
    recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
  },
  {
    id: 'primary_outcome',
    prompt: 'What single horizon and minimum useful move defines a bounce?',
    blocking_reason: 'It fixes the primary endpoint and economic hurdle.',
    choices: [{
      id: 'four_trading_hour_return_25bp',
      label: 'Four trading hours, 25 bp',
      consequence: 'Tests a positive 240-trading-minute return that clears 0.25%.',
      availability: 'available',
      blocked_reason: null,
    }],
    recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
  },
]

// Typed against the generated contract so ANY future ResearchCase drift fails the
// frontend type gate instead of silently passing a stale mocked shape to e2e.
const RESEARCH_CONTRACT_ID = `rc_${'a'.repeat(64)}`
const RESEARCH_SEMANTIC_HASH = 'c'.repeat(64)

const RESEARCH_CASE: components['schemas']['ResearchCase'] = {
  schema_version: 1,
  project_id: 'research-project-1',
  project_name: 'SPY double bottom',
  phase: 'triage',
  execution_state: 'idle',
  active_contract_id: RESEARCH_CONTRACT_ID,
  active_contract: {
    contract_id: RESEARCH_CONTRACT_ID,
    project_id: 'research-project-1',
    scope: 'exploration',
    parent_contract_id: null,
    payload: {
      raw_idea: RESEARCH_RAW_IDEA,
      approval_ready: false,
      blocking_questions: RESEARCH_QUESTIONS,
      valid_answer_bundles: [],
      recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
      thesis: {
        mechanism: 'Revisited support may concentrate demand or reduce selling pressure.',
        prediction: 'Point-in-time events have higher returns than matched controls.',
        interpretation: 'Predictive association, not a causal effect.',
        alternatives: ['day of week', 'volatility regime'],
      },
    },
    created_by: 'codex',
    author_kind: 'agent',
    created_at: '2026-08-06T00:00:00Z',
    review_state: 'pending',
    latest_review: null,
  },
  exploration_contract_id: RESEARCH_CONTRACT_ID,
  confirmation_contract_id: null,
  exploration_review: { state: 'pending', event: null },
  confirmation_review: { state: 'pending', event: null },
  research_decision: null,
  next_action: 'Owner answers the three material protocol questions.',
  responsibility: 'owner',
  blocker: null,
  recovery: null,
  latest_finding: null,
  milestones: [],
  completed_milestones: [],
  remaining_milestones: ['pilot', 'deep_research', 'confirmation_review', 'sealed_confirmation', 'research_decision', 'closed'],
  elapsed_time_seconds: 0,
  elapsed_budget: { wall_seconds: 0, source_requests: 0 },
  remaining_budget: { wall_seconds: 1_200, source_requests: 20 },
  active_job_id: null,
  checkpoint: null,
  hashes: {},
  source_pack_id: null,
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
  d2_boundary_hash: 'a'.repeat(64),
  d2_history: [],
  d3_state: 'not_sealed',
}

const RESEARCH_CLOSED_CASE: components['schemas']['ResearchCase'] = {
  ...RESEARCH_CASE,
  phase: 'closed',
  active_contract: { ...RESEARCH_CASE.active_contract, review_state: 'approved' },
  exploration_review: { state: 'approved', event: null },
  confirmation_review: { state: 'approved', event: null },
  research_decision: {
    project_id: RESEARCH_CASE.project_id,
    sequence: 1,
    contract_id: RESEARCH_CASE.active_contract_id,
    outcome: 'INCONCLUSIVE',
    disposition: 'park',
    actor: 'owner',
    actor_kind: 'human',
    occurred_at: '2026-08-06T01:00:00Z',
    reason: 'No typed non-synthetic evidence exists.',
  },
  next_action: 'Research Case is closed.',
  remaining_milestones: [],
  study_status: {
    schema: 'ResearchStudyStatusV1',
    schema_version: 1,
    authority: 'none',
    project_id: RESEARCH_CASE.project_id,
    active_contract_id: RESEARCH_CONTRACT_ID,
    semantic: {
      state: 'freeze_required',
      source_state: 'current',
      case_contract_id: RESEARCH_CONTRACT_ID,
      case_revision: '9'.repeat(64),
      verified_read_sha256: '8'.repeat(64),
      projection_sha256: '7'.repeat(64),
      run_id: '0123456789abcdef',
      cutoff_confirmed_at: '2026-08-29T23:00:00Z',
      event_count: 2,
      head_sha256: RESEARCH_SEMANTIC_HASH,
      definition: {
        event_id: `se_${'1'.repeat(64)}`,
        artifact_id: `sd_${'2'.repeat(64)}`,
        receipt_id: 'semantic-receipt-1',
        actor: 'owner',
        reason: 'Define the visible shape.',
        recorded_at: '2026-08-30T00:00:01Z',
        payload: {
          event_type: 'definition',
          definition_label: 'bounded reversal',
          definition_text: 'Visible troughs only; no post-cutoff values.',
        },
      },
      review: {
        event_id: `se_${RESEARCH_SEMANTIC_HASH}`,
        artifact_id: `sr_${'3'.repeat(64)}`,
        receipt_id: 'semantic-receipt-2',
        actor: 'owner',
        reason: 'Approve the bounded definition.',
        recorded_at: '2026-08-30T00:00:02Z',
        payload: {
          event_type: 'review',
          review_decision: 'approve',
          review_text: 'The definition uses only the masked read.',
        },
      },
      freeze: null,
      next_owner_action: 'Freeze the approved semantic definition with fresh Touch ID.',
    },
    d1: {
      launch_authority: 'owner_cli_only',
      status: 'completed',
      attempts: [{
        attempt_id: 'd1-attempt-1',
        contract_id: RESEARCH_CONTRACT_ID,
        status: 'completed',
        run_id: '0123456789abcdef',
        recorded_at: '2026-08-30T00:01:00Z',
      }],
      elapsed_budget: { variants: 3 },
      remaining_budget: { variants: 61 },
    },
    promotion: {
      packet_id: null,
      readiness: {
        state: 'blocked',
        blockers: [{
          code: 'confirmation_not_supported',
          evidence_refs: ['research_gate_evidence.confirmation_classification'],
        }],
      },
    },
    next_action: 'Review evidence before any owner decision.',
    responsibility: 'owner',
  },
}

const RESEARCH_SEMANTIC_READ: components['schemas']['VerifiedBlindSemanticReadV1'] = {
  schema: 'VerifiedBlindSemanticReadV1',
  schema_version: 1,
  source_verification: 'verified_completed_d0_recomputation',
  authority: 'none',
  run_id: '0123456789abcdef',
  projection: {
    schema: 'BlindSemanticProjectionV1',
    schema_version: 1,
    run_id: '0123456789abcdef',
    acceptance_artifact_sha256: '4'.repeat(64),
    events_artifact_sha256: '5'.repeat(64),
    chart_data_artifact_sha256: '6'.repeat(64),
    cutoff_confirmed_at: '2026-08-29T23:00:00Z',
    points: [{ point_id: 'visible-1', available_at: '2026-08-29T22:00:00Z', value: 101.5 }],
    masked_count: 8,
    authority: 'none',
    cutoff_source: 'd0_acceptance_measurement_reference',
    lineage_verification: 'not_checked',
    semantic_status: 'unfrozen',
    content_sha256: '7'.repeat(64),
  },
  content_sha256: '8'.repeat(64),
}

const RESEARCH_CASE_ROW: components['schemas']['ResearchCaseSummaryRow'] = {
  case_id: RESEARCH_CASE.project_id,
  title: RESEARCH_CASE.project_name,
  original_idea: RESEARCH_RAW_IDEA,
  phase: 'triage',
  execution_state: 'idle',
  outcome: null,
  disposition: null,
  next_action: RESEARCH_CASE.next_action,
  responsibility: 'owner',
  latest_finding: null,
  blocker: null,
  recovery_action: null,
  completed_milestones: 2,
  total_milestones: 9,
  owner_pinned: false,
  priority: { falsifiability: 0, data_readiness: 0, novelty: 0, information_gain_per_cost: 0 },
  budget: { approved_units: 20, consumed_units: 0, unit: 'minutes' },
  updated_at: '2026-08-06T00:00:00Z',
}

const RESEARCH_CASE_PAGE: components['schemas']['ResearchCasePage'] = {
  items: [RESEARCH_CASE_ROW],
  limit: 50,
  offset: 0,
  has_more: false,
}

const HYPOTHESIS_CARD_FIELDS: ReadonlyArray<
  [components['schemas']['HypothesisCardField']['field_id'], string]
> = [
  ['research_question', 'Research question'],
  ['phenomenon', 'Phenomenon'],
  ['population', 'Population / universe'],
  ['condition_event', 'Condition / event'],
  ['dependent_variable', 'Dependent variable'],
  ['horizon', 'Horizon'],
  ['expected_direction', 'Expected direction'],
  ['economic_mechanism', 'Economic mechanism'],
  ['null_hypothesis', 'Null hypothesis'],
  ['alternative_hypothesis', 'Alternative hypothesis'],
  ['baseline', 'Baseline'],
  ['confounders', 'Confounders'],
  ['falsification_criteria', 'Falsification criteria'],
  ['success_criteria', 'Success criteria'],
]

const RESEARCH_HYPOTHESIS_CARD: components['schemas']['HypothesisCard'] = {
  card_schema: 'HypothesisCardV1',
  fields: HYPOTHESIS_CARD_FIELDS.map(([fieldId, label]) => ({
    field_id: fieldId,
    label,
    value: fieldId === 'research_question' ? RESEARCH_RAW_IDEA : null,
    status: fieldId === 'research_question' ? 'complete' : 'missing',
  })),
  complete_fields: 1,
  total_fields: 14,
}

const BLOCKED_CONFIRMATION_READINESS: components['schemas']['ResearchReadinessProjection'] = {
  state: 'blocked',
  blockers: [
    {
      code: 'primary_result_not_passed',
      evidence_refs: ['research_gate_evidence.primary_result'],
    },
  ],
}

const BLOCKED_PROMOTION_READINESS: components['schemas']['ResearchReadinessProjection'] = {
  state: 'blocked',
  blockers: [
    {
      code: 'confirmation_not_supported',
      evidence_refs: ['research_gate_evidence.confirmation_classification'],
    },
  ],
}

const RESEARCH_SCORECARD: components['schemas']['ResearchScorecard'] = {
  scorecard_schema: 'ResearchReadinessScorecardV1',
  dimensions: [
    { dimension_id: 'hypothesis_definition', label: 'Hypothesis definition', state: 'partial', basis: '1 of 14 hypothesis-card fields are complete.' },
    { dimension_id: 'data_quality', label: 'Data quality', state: 'not_tested', basis: 'No registered research datasets.' },
    { dimension_id: 'sample_adequacy', label: 'Sample adequacy', state: 'not_tested', basis: 'No power evidence has been recorded.' },
    { dimension_id: 'effect_existence', label: 'Effect existence', state: 'not_tested', basis: 'No primary-result evidence has been recorded.' },
    { dimension_id: 'effect_size', label: 'Effect size', state: 'not_tested', basis: 'No practical-magnitude evidence exists.' },
    { dimension_id: 'temporal_stability', label: 'Temporal stability', state: 'not_tested', basis: 'The recorded temporal-stability finding is NOT_TESTED.' },
    { dimension_id: 'cross_asset_stability', label: 'Cross-asset stability', state: 'not_tested', basis: 'The recorded transportability finding is NOT_TESTED.' },
    { dimension_id: 'regime_robustness', label: 'Regime robustness', state: 'not_tested', basis: 'No regime-decomposition evidence exists yet.' },
    { dimension_id: 'falsification', label: 'Falsification', state: 'not_tested', basis: 'The registered falsifiers have not run.' },
    { dimension_id: 'mechanism', label: 'Mechanism', state: 'not_tested', basis: 'No mechanism evidence has been recorded.' },
    { dimension_id: 'literature', label: 'Literature', state: 'insufficient', basis: 'No screened claim-level literature evidence.' },
    { dimension_id: 'data_mining_risk', label: 'Data-mining risk', state: 'low', basis: 'All analysis families are contract-registered; unregistered attempts are impossible.' },
  ],
  unresolved_questions: { count: 3, items: RESEARCH_QUESTIONS.map((question) => question.prompt) },
  recommendation: {
    value: 'MORE RESEARCH REQUIRED',
    reasons: ['10 of 12 readiness dimensions are untested.', '3 unresolved questions remain.'],
  },
  confirmation_readiness: BLOCKED_CONFIRMATION_READINESS,
  promotion_readiness: BLOCKED_PROMOTION_READINESS,
}

const RESEARCH_EVIDENCE_HUB: components['schemas']['ResearchEvidenceHub'] = {
  hub_schema: 'ResearchEvidenceHubV1',
  project_id: RESEARCH_CASE.project_id,
  sections: {
    overview: {
      original_idea: RESEARCH_RAW_IDEA,
      phase: 'triage',
      execution_state: 'idle',
      next_action: RESEARCH_CASE.next_action,
      responsibility: 'owner',
      latest_finding: null,
      outstanding_questions: RESEARCH_QUESTIONS.map((question) => question.prompt),
      hypothesis_card: RESEARCH_HYPOTHESIS_CARD,
      scorecard: RESEARCH_SCORECARD,
    },
    data: {
      registered_datasets: [],
      status: 'NOT_TESTED',
      note: 'No registered research datasets; the data plane arrives in a later phase.',
    },
    literature: {
      claims: [
        {
          claim_id: `sc_${'b'.repeat(64)}`,
          direction: 'supports',
          strength: 'moderate',
          status: 'screened',
          claim_text: 'Month-end index drift is positive pre-2010.',
          source_id: `rs_${'c'.repeat(64)}`,
          author_kind: 'agent',
          limitations: 'Post-publication decay is not addressed.',
          anchor_state: 'LEGACY — NO TEXT ANCHOR',
        },
        {
          claim_id: `sc_${'d'.repeat(64)}`,
          direction: 'contradicts',
          strength: 'weak',
          status: 'draft',
          claim_text: 'The effect vanished after decimalization.',
          source_id: `rs_${'c'.repeat(64)}`,
          author_kind: 'agent',
          limitations: 'Single-market sample.',
          anchor_state: 'LEGACY — NO TEXT ANCHOR',
        },
      ],
      sources: [],
      source_packs: [],
      recommendation: {
        schema: 'ResearchRecommendationV1',
        status: 'DRAFT — UNSCREENED',
        allowed_next_actions: [
          { rank: 1, action: 'screen_reject_or_revise_claims', reason: 'One draft needs review.' },
        ],
        uncertainty: 'Contradictory coverage remains incomplete.',
        authority: 'Decision support only; it cannot screen, freeze, approve, or launch.',
      },
      status: 'SUPPORTING',
    },
    mechanism: {
      mechanism: 'Revisited support may concentrate demand or reduce selling pressure.',
      interpretation: 'Predictive association, not a causal effect.',
      alternatives: ['day of week', 'volatility regime'],
      confounders: [
        { text: 'Day-of-week seasonality', status: 'unresolved' },
        { text: 'Volatility regime', status: 'unresolved' },
      ],
    },
    exploration: { charts: [], watermark: 'EXPLORATORY', status: 'NOT_TESTED' },
    experiments: { attempts: [] },
    evidence_for: { findings: [] },
    evidence_against: { findings: [] },
    falsification: {
      falsifiers: [
        { text: 'Shuffled-label control shows no effect', result: 'NOT_TESTED' },
        { text: 'Randomised-price null shows no effect', result: 'NOT_TESTED' },
      ],
      stop_rules: ['Stop when the budget is exhausted.'],
    },
    robustness: { findings: [], status: 'NOT_TESTED' },
    decision: {
      outcome: null,
      disposition: null,
      d2_state: 'sealed',
      d3_state: 'not_sealed',
      packet_id: null,
      packet_hash: null,
    },
  },
}

const RESEARCH_PROTOCOLS: components['schemas']['ResearchProtocolLibrary'] = {
  protocols: [
    {
      id: 'new-idea-intake',
      title: 'New-Idea Intake',
      purpose: 'idea → research questions, no trading rules',
      packet_kind: 'research_case',
      output_contract: 'tentative claim, mechanism, alternatives, material questions',
      file: 'new-idea-intake.md',
      sha256: 'd'.repeat(64),
    },
    {
      id: 'research-critic',
      title: 'Research Critic',
      purpose: 'independently attack current evidence',
      packet_kind: 'validation',
      output_contract: 'critique note (adversarial-reviewer format)',
      file: 'research-critic.md',
      sha256: 'e'.repeat(64),
    },
  ],
}

const RESEARCH_PROPOSAL_OPTIONS: components['schemas']['ResearchProposalOptionsV1'] = {
  proposal_schema: 'ResearchProposalOptionsV1',
  project_id: RESEARCH_CASE.project_id,
  case_revision: 'a'.repeat(64),
  material_questions: RESEARCH_QUESTIONS,
  recommended_answer_bundle_id: 'synthetic_spy_60m_four_hour_v1',
  valid_answer_bundles: [{
    bundle_id: 'synthetic_spy_60m_four_hour_v1',
    label: 'SPY 60-minute synthetic detector validation',
    answers: {
      chart_construction: 'spy_rth_60m_four_hour_window',
      event_availability: 'second_trough_confirmable',
      primary_outcome: 'four_trading_hour_return_25bp',
    },
    requires_dataset: false,
    compatible_dataset_ids: [],
    available: true,
    blocked_reason: null,
  }],
  compatible_source_packs: [],
  compatible_datasets: [],
  blockers: [{
    code: 'SOURCE_PACK_REQUIRED',
    message: 'Freeze at least one project source pack before proposing.',
    recovery_action: 'Open Literature, review sources, and freeze a pack.',
  }],
  approval_ready: false,
}

const RESEARCH_PACKET: components['schemas']['ResearchContextPacket'] = {
  packet_id: `cp_${'f'.repeat(64)}`,
  project_id: RESEARCH_CASE.project_id,
  packet_kind: 'research_case',
  protocol_id: 'new-idea-intake',
  protocol_content_hash: 'd'.repeat(64),
  payload: {
    packet_schema: 'ResearchContextPacketV1',
    packet_kind: 'research_case',
    project_id: RESEARCH_CASE.project_id,
    next_action: RESEARCH_CASE.next_action,
  },
  created_by: 'codex',
  created_at: '2026-08-09T00:00:00Z',
}

const RESEARCH_NOTE: components['schemas']['ResearchNote'] = {
  note_id: `rn_${'a'.repeat(64)}`,
  project_id: RESEARCH_CASE.project_id,
  sequence: 1,
  note_kind: 'critique',
  body: 'The volatility-regime confounder is not yet matched.',
  author: 'codex',
  author_kind: 'agent',
  context_packet_id: RESEARCH_PACKET.packet_id,
  created_at: '2026-08-09T00:05:00Z',
}

const RESEARCH_GATE_PACKET: components['schemas']['ResearchGatePacket'] = {
  report_schema: 'ResearchGatePacketV1',
  schema_version: 1,
  terminal: true,
  packet_id: `rgp_${'b'.repeat(64)}`,
  packet_hash: 'b'.repeat(64),
  project_id: RESEARCH_CASE.project_id,
  active_contract_id: RESEARCH_CASE.active_contract_id,
  scientific_outcome: 'INCONCLUSIVE',
  recommended_disposition: 'park',
  authority: {
    evidence_claim: 'point-in-time-valid predictive association',
    strategy_validated: false,
    paper_ready: false,
    places_orders: false,
    uses_final_strategy_holdout: false,
  },
  layers: {
    conclusion_90_seconds: {
      project_name: RESEARCH_CASE.project_name,
      thesis: 'Point-in-time double bottoms predict a positive forward return.',
      thesis_answer: 'The recorded outcome does not resolve the frozen claim.',
      scientific_outcome: 'INCONCLUSIVE',
      recommended_disposition: 'park',
      owner_decision_reason: 'No typed non-synthetic evidence exists.',
      evidence_basis: 'NO_TYPED_NON_SYNTHETIC_EVIDENCE',
      primary_estimate: null,
      uncertainty: null,
      effective_sample_size: null,
      practical_magnitude: {
        status: 'NOT_TESTED',
        value: null,
        unit: null,
        interpretation: 'No typed D1 or D2 empirical result is present.',
      },
      strongest_caveat: 'D0 is synthetic and cannot support a market claim.',
    },
    guided_evidence: {
      primary_result: {
        status: 'NOT_TESTED',
        estimate: null,
        unit: null,
        sample_size: null,
        effective_sample_size: null,
        uncertainty: null,
        practical_magnitude: {
          status: 'NOT_TESTED',
          value: null,
          unit: null,
          interpretation: 'No typed D1 or D2 empirical result is present.',
        },
      },
      confirmation_classification: null,
      confirmation_checks: null,
      mechanism: { status: 'NOT_TESTED', summary: 'Proposed mechanism only.' },
      strongest_support: { status: 'NOT_TESTED', summary: null },
      strongest_contradiction: { status: 'NOT_TESTED', summary: null },
      confounders: { resolved: [], unresolved: ['day of week', 'volatility regime'] },
      stability: {
        parameter: { status: 'NOT_TESTED', summary: null },
        temporal: { status: 'NOT_TESTED', summary: null },
        transportability: { status: 'NOT_TESTED', summary: null },
      },
      multiplicity: { status: 'NOT_TESTED', summary: null },
      power: { status: 'NOT_TESTED', summary: null },
      negative_controls: { status: 'NOT_TESTED', summary: null },
      untested_work: ['No typed D1 or D2 empirical result is present.'],
      what_would_change_conclusion: ['A preregistered future replication.'],
      teaching_note: 'This packet summarizes recorded evidence; it is not strategy validation.',
    },
    technical_appendix: {
      project: {},
      contract_lineage: [],
      source_pack_ledger: [],
      source_ledger: [],
      variant_ledger: [],
      attempt_ledger: [],
      launch_reservation_ledger: [],
      launch_attempt_link_ledger: [],
      budget_ledger: [],
      phase_review_d2_ledgers: {
        phase_events: [],
        review_events: [],
        execution_events: [],
        d2_events: [],
        decision_events: [],
      },
      immutable_artifact_links: [],
      selected_evidence: null,
      ledger_bounds: {
        maximum_rows_per_input_ledger: 10_000,
        truncated: false,
        counts: {
          contracts: 1,
          source_packs: 0,
          sources: 0,
          attempts: 0,
          launch_reservations: 0,
          launch_attempt_links: 0,
          phase_events: 1,
          review_events: 1,
          execution_events: 0,
          d2_events: 0,
          decision_events: 1,
          artifact_links: 0,
        },
      },
    },
  },
}

const RESEARCH_CHECKLIST: components['schemas']['ResearchEdgeChecklist'] = {
  checklist_schema: 'ResearchEdgeChecklistV1',
  questions: [
    {
      question_id: 'effect_exists', number: 1, question: 'Does the effect exist?',
      binding: 'primary result', status: 'INCONCLUSIVE',
      answer: 'Sealed confirmation classified the registered claim INCONCLUSIVE.',
    },
    {
      question_id: 'practical_magnitude', number: 2, question: 'Is it large enough to matter?',
      binding: 'practical magnitude vs registered minimum effect', status: 'INCONCLUSIVE',
      answer: 'The recorded magnitude finding is INCONCLUSIVE.',
    },
    {
      question_id: 'temporal_stability', number: 3, question: 'Is it stable through time?',
      binding: 'temporal stability', status: 'NOT_TESTED',
      answer: 'The recorded temporal-stability finding is NOT_TESTED.',
    },
    {
      question_id: 'sample_breadth', number: 4,
      question: 'Does it exist beyond one small sample?',
      binding: 'effective sample and registered subsamples', status: 'NOT_TESTED',
      answer: 'No effective-sample evidence has been recorded.',
    },
    {
      question_id: 'transportability', number: 5,
      question: 'Does it exist across relevant assets, or only one?',
      binding: 'cross-asset transportability', status: 'NOT_TESTED',
      answer: 'The recorded transportability finding is NOT_TESTED.',
    },
    {
      question_id: 'regime_dependence', number: 6, question: 'Is it regime-dependent?',
      binding: 'regime decomposition', status: 'NOT_TESTED',
      answer: 'No regime-decomposition evidence exists yet.',
    },
    {
      question_id: 'parameter_neighborhood', number: 7,
      question: 'Does it survive alternative definitions?',
      binding: 'parameter neighborhood', status: 'NOT_TESTED',
      answer: 'The recorded parameter-neighborhood finding is NOT_TESTED.',
    },
    {
      question_id: 'falsification', number: 8,
      question: 'Does it survive falsification tests?',
      binding: 'placebo, negative controls, and registered nulls', status: 'NOT_TESTED',
      answer: 'The registered falsifiers have not run.',
    },
    {
      question_id: 'data_artifact', number: 9, question: 'Is it likely a data artifact?',
      binding: 'data-quality audit findings', status: 'NOT_TESTED',
      answer: 'No registered dataset has been audited.',
    },
    {
      question_id: 'leakage', number: 10, question: 'Is it likely look-ahead or leakage?',
      binding: 'future-poison and lead-lag diagnostics', status: 'NOT_TESTED',
      answer: 'The lead-lag leakage screen has not run.',
    },
    {
      question_id: 'mechanism', number: 11, question: 'Is there a plausible mechanism?',
      binding: 'mechanism finding and screened claims', status: 'NOT_TESTED',
      answer: 'The recorded mechanism finding is NOT_TESTED.',
    },
    {
      question_id: 'economic_hurdle', number: 12,
      question: 'Could the magnitude survive realistic costs?',
      binding: 'economic-hurdle check (last rung)', status: 'NOT_TESTED',
      answer: 'No economic-hurdle evidence exists.',
    },
    {
      question_id: 'observation_count', number: 13, question: 'Do we have enough observations?',
      binding: 'power and the low-cluster floor', status: 'NOT_TESTED',
      answer: 'No power evidence has been recorded.',
    },
    {
      question_id: 'residual_uncertainty', number: 14,
      question: 'How much uncertainty remains?',
      binding: 'intervals and untested work', status: 'TESTED',
      answer: 'Unresolved questions and untested work remain.',
    },
  ],
}

const RESEARCH_DECISION_VIEW: components['schemas']['ResearchDecisionView'] = {
  view_schema: 'ResearchDecisionViewV1',
  project_id: RESEARCH_CASE.project_id,
  phase: 'closed',
  d2_state: 'sealed',
  next_action: 'Research Case is closed.',
  checklist: RESEARCH_CHECKLIST,
  scorecard: RESEARCH_SCORECARD,
  confirmation_readiness: BLOCKED_CONFIRMATION_READINESS,
  promotion_readiness: BLOCKED_PROMOTION_READINESS,
  gate_packet: RESEARCH_GATE_PACKET,
  decision_history: [
    {
      sequence: 1,
      contract_id: RESEARCH_CASE.active_contract_id,
      outcome: 'INCONCLUSIVE',
      disposition: 'park',
      actor: 'owner',
      actor_kind: 'human',
      occurred_at: '2026-08-06T01:00:00Z',
      reason: 'No typed non-synthetic evidence exists.',
    },
  ],
}

const PROJECT_VIEWPORTS: Record<string, { width: number; height: number }> = {
  'chromium-minimum': { width: 1280, height: 720 },
  'chromium-reference': { width: 1440, height: 900 },
  'chromium-wide': { width: 1920, height: 1080 },
}

const HEAVY_RUN_ID = '0123456789abcdef'
const HEAVY_BAR_COUNT = 25_000
const HEAVY_ANNOTATION_COUNT = 200
const HEAVY_START_TS = Date.UTC(1957, 0, 1) / 1_000

function heavyChartBundle(): unknown {
  const bars = Array.from({ length: HEAVY_BAR_COUNT }, (_, index) => {
    const baseline = 100 + index * 0.002 + Math.sin(index / 17)
    const open = baseline + Math.sin(index / 5) * 0.12
    const close = baseline + Math.cos(index / 7) * 0.12
    return {
      t: HEAVY_START_TS + index * 86_400,
      o: open,
      h: Math.max(open, close) + 0.3,
      l: Math.min(open, close) - 0.3,
      c: close,
      v: 1_000_000 + (index % 97) * 10_000,
    }
  })
  const annotations = Array.from({ length: HEAVY_ANNOTATION_COUNT }, (_, index) => {
    const barIndex = Math.floor((index * (HEAVY_BAR_COUNT - 2)) / (HEAVY_ANNOTATION_COUNT - 1))
    return {
      annotation_id: index + 1,
      decision_sequence_id: null,
      kind: index % 5 === 0 ? 'zone' : 'line',
      label: `LEVEL ${String(index + 1).padStart(3, '0')}`,
      unit: 'price',
      reason: 'deterministic performance fixture',
      anchors: [
        { anchor_index: 0, ts: bars[barIndex]!.t, value: bars[barIndex]!.c },
        { anchor_index: 1, ts: bars[barIndex + 1]!.t, value: bars[barIndex + 1]!.c },
      ],
    }
  })
  return {
    run_id: HEAVY_RUN_ID,
    trace_status: 'available',
    bars_status: 'available',
    provenance: {
      command: 'backtest_run',
      symbol: 'SPY',
      symbols: null,
      snapshot_id: 'performance-fixture',
      snapshot_hash: 'a'.repeat(64),
      timezone: 'UTC',
      price_unit: 'native_quote',
      artifact_contract_version: 3,
      as_of: bars.at(-1)!.t,
      artifact_sha256: {},
    },
    bars,
    equity: { ts: [], equity: [], drawdown: [] },
    trades: [],
    trace: [],
    decisions: [],
    orders: [],
    fills: [],
    indicators: [],
    annotations,
    folds: [],
    forecast: null,
    truncated: {
      bars: false,
      equity: false,
      trades: false,
      trace: false,
      indicators: false,
      annotations: false,
    },
  }
}

const CAUSAL_START_TS = Date.UTC(2025, 0, 1) / 1_000
const CAUSAL_TRADES = [
  {
    instrument_id: 'AAPL.SIM',
    side: 'BUY',
    quantity: 10,
    entry_price: 192.25,
    exit_price: 201.5,
    entry_ts: new Date((CAUSAL_START_TS + 92 * 86_400) * 1_000).toISOString(),
    exit_ts: new Date((CAUSAL_START_TS + 100 * 86_400) * 1_000).toISOString(),
    realized_pnl: 92.5,
    realized_return: 0.048114,
  },
]

function traceEvent(sequenceId: number, ts: number): Record<string, unknown> {
  return {
    sequence_id: sequenceId,
    event_type: 'decision',
    ts,
    parent_sequence_id: null,
    instrument_id: 'AAPL.SIM',
    side: 'BUY',
    quantity: 10,
    filled_quantity: null,
    price: null,
    status: null,
    signal: 1,
    decision_reason: `causal decision ${sequenceId}`,
    entry_ts: null,
    exit_ts: null,
    entry_price: null,
    exit_price: null,
    realized_pnl: null,
    realized_return: null,
  }
}

function causalChartBundle(traceAvailable = true): unknown {
  const bars = Array.from({ length: 205 }, (_, index) => ({
    t: CAUSAL_START_TS + index * 86_400,
    o: 100 + index,
    h: 102 + index,
    l: 99 + index,
    c: 101 + index,
    v: 1_000 + index,
  }))
  const decisions = Array.from({ length: 90 }, (_, index) =>
    traceEvent(index + 1, bars[index]!.t + 23 * 60 * 60),
  )
  const trade = {
    ...traceEvent(91, bars[100]!.t),
    event_type: 'trade',
    status: 'CLOSED',
    signal: null,
    decision_reason: null,
    price: 201.5,
    entry_ts: bars[92]!.t,
    exit_ts: bars[100]!.t,
    entry_price: 192.25,
    exit_price: 201.5,
    realized_pnl: 92.5,
    realized_return: 0.048114,
  }
  const trace = traceAvailable ? [...decisions, trade] : []
  return {
    run_id: HEAVY_RUN_ID,
    trace_status: traceAvailable ? 'available' : 'trace_unavailable',
    bars_status: 'available',
    provenance: {
      command: 'backtest_run',
      symbol: 'AAPL',
      symbols: null,
      snapshot_id: 'causal-fixture',
      snapshot_hash: 'f'.repeat(64),
      timezone: 'UTC',
      price_unit: 'native_quote',
      artifact_contract_version: traceAvailable ? 3 : null,
      as_of: bars.at(-1)!.t,
      artifact_sha256: {},
    },
    bars,
    equity: { ts: [], equity: [], drawdown: [] },
    trades: traceAvailable ? [{ ...CAUSAL_TRADES[0], entry_ts: bars[92]!.t, exit_ts: bars[100]!.t }] : [],
    trace,
    decisions: traceAvailable ? decisions : [],
    orders: [],
    fills: [],
    indicators: [],
    annotations: [],
    folds: [],
    forecast: null,
    truncated: {
      bars: true,
      equity: false,
      trades: false,
      trace: traceAvailable,
      indicators: false,
      annotations: false,
    },
  }
}

function denseCausalChartBundle(): unknown {
  const bundle = causalChartBundle() as Record<string, unknown>
  const bars = bundle.bars as Array<{ t: number }>
  const decisions = Array.from({ length: 90 }, (_, index) =>
    traceEvent(index * 2 + 1, bars[index]!.t + 23 * 60 * 60),
  )
  const fills = decisions.map((decision, index) => ({
    ...decision,
    sequence_id: index * 2 + 2,
    event_type: 'fill',
    ts: bars[index + 1]!.t,
    filled_quantity: 10,
    price: 101 + index,
    status: 'FILLED',
    signal: null,
    decision_reason: null,
  }))
  return {
    ...bundle,
    trace: decisions.flatMap((decision, index) => [decision, fills[index]]),
    decisions,
    fills,
    trades: [],
  }
}

const EMPTY_NATIVE_TEARSHEET = {
  available: false,
  calendar_returns: [],
  yearly_returns: [],
  histogram: [],
  qq: [],
  rolling: [],
  exposure_turnover: [],
  benchmark: [],
  trade_statistics: [],
  exposure_available: false,
  turnover_available: false,
  benchmark_available: false,
  trade_statistics_available: false,
  provenance: {
    run_id: HEAVY_RUN_ID,
    metric_namespace: 'alpha_validation',
    artifact_contract_version: 3,
    artifact_sha256: {},
  },
  bounds: {
    point_limit: 2_000,
    qq: { original: 0, returned: 0, truncated: false, sampling: 'all' },
    rolling: { original: 0, returned: 0, truncated: false, sampling: 'all' },
    exposure_turnover: { original: 0, returned: 0, truncated: false, sampling: 'all' },
    benchmark: { original: 0, returned: 0, truncated: false, sampling: 'all' },
  },
}

const ML_EXCHANGE_ID = 'a'.repeat(32)
const ML_EXPERIMENT = {
  experiment_id: ML_EXCHANGE_ID,
  project_id: null,
  status: 'trained',
  universe_size: 20,
  aligned_sessions: 756,
  feature_recipe: 'alpha158',
  model: 'lightgbm',
  folds: 1,
  snapshot_hash: 'b'.repeat(64),
  config_hash: 'c'.repeat(64),
  replay_run_id: null,
  diagnostic_only: true,
  counterfactual_refit: false,
  metrics: { ic: 0.042, rank_ic: 0.051, turnover: 0.08, costed_return: 0.11 },
}
const ML_DIAGNOSTIC_TEARSHEET = {
  available: true,
  exchange_id: ML_EXCHANGE_ID,
  authority: 'qlib_diagnostic_only',
  label: 'OOS replay validated — model not recomputed under counterfactual',
  counterfactual_refit: false,
  versions: { worker: 'worker-1', pyqlib: '0.9.7', lightgbm: '4.6.0' },
  feature_recipe: {
    name: 'Alpha158-style',
    feature_count: 2,
    names: ['KMID', 'KLEN'],
    vwap_source: 'causal daily OHLCV',
  },
  label_recipe: {
    name: 'next_session_open_to_open',
    definition: 'next-session open-to-open return',
    decision: 'close_t',
    entry: 'open_t_plus_1',
  },
  score_distribution: {
    min: -0.8,
    max: 0.9,
    mean: 0.04,
    std: 0.22,
    q05: -0.34,
    q25: -0.12,
    q50: 0.03,
    q75: 0.17,
    q95: 0.41,
  },
  ic: {
    mean: 0.042,
    rank_mean: 0.051,
    by_target: [
      { target_ts: '2025-01-02T00:00:00Z', ic: 0.03, rank_ic: 0.04, sample_count: 20 },
      { target_ts: '2025-01-03T00:00:00Z', ic: 0.054, rank_ic: 0.062, sample_count: 20 },
    ],
  },
  quantile_returns: [
    { quantile: 1, mean_return: -0.002, observations: 8 },
    { quantile: 2, mean_return: -0.0005, observations: 8 },
    { quantile: 3, mean_return: 0.0002, observations: 8 },
    { quantile: 4, mean_return: 0.0011, observations: 8 },
    { quantile: 5, mean_return: 0.0024, observations: 8 },
  ],
  portfolio: {
    selection: 'long_only_top_quintile_equal_weight',
    declared_costs: { fee_bps: 1, slippage_bps: 2 },
    periods: 2,
    gross_total_return: 0.013,
    costed_total_return: 0.011,
    benchmark_total_return: 0.004,
    costed_excess_total_return: 0.007,
    mean_turnover: 0.08,
    timeline: [
      { target_ts: '2025-01-02T00:00:00Z', gross_return: 0.006, costed_return: 0.005, benchmark_return: 0.002, excess_return: 0.003, turnover: 0.07, gross_equity: 1.006, costed_equity: 1.005, benchmark_equity: 1.002 },
      { target_ts: '2025-01-03T00:00:00Z', gross_return: 0.007, costed_return: 0.006, benchmark_return: 0.002, excess_return: 0.004, turnover: 0.09, gross_equity: 1.013, costed_equity: 1.011, benchmark_equity: 1.004 },
    ],
  },
  feature_importance: [
    { feature: 'KMID', mean_gain: 0.61, mean_split_count: 31 },
    { feature: 'KLEN', mean_gain: 0.39, mean_split_count: 19 },
  ],
  feature_importance_truncated: false,
  folds: [{
    fold: 0,
    fit_count: 1,
    train_rows: 10_000,
    validation_rows: 2_000,
    test_rows: 2_000,
    best_iteration: 2,
    model_hash: 'd'.repeat(64),
    normalization: {
      method: 'train_only_median_then_zscore',
      statistics_hash: 'e'.repeat(64),
      all_missing_train_features: 0,
    },
    training_history: {
      train: { l2: [0.4, 0.3] },
      valid: { l2: [0.45, 0.34] },
    },
    boundaries: {
      train_start: '2022-01-03T00:00:00Z',
      train_end: '2023-12-29T00:00:00Z',
      validation_start: '2024-01-02T00:00:00Z',
      validation_end: '2024-06-28T00:00:00Z',
      test_start: '2024-07-01T00:00:00Z',
      test_end: '2024-12-31T00:00:00Z',
    },
  }],
  timeline_total: 2,
  timeline_offset: 0,
  timeline_limit: 500,
  timeline_has_more: false,
}

// spec §15 / ADR-0026 (R6g): a run launched under an owner research-gate override permanently
// carries this marker; the SPA relays it on the run browser, run story, and tear sheet, and the
// Operations desk lists every active override.
const RESEARCH_GATE_WATERMARK = 'EXPLORATORY / RESEARCH GATE NOT COMPLETED'
const WATERMARKED_RUN_ID = 'fade0000000000ab'

const WATERMARKED_RUN_ITEM: components['schemas']['RunListItem'] = {
  run_id: WATERMARKED_RUN_ID,
  kind: 'portfolio',
  command: 'backtest_portfolio',
  label: 'SPY, TLT',
  symbol: null,
  symbols: ['SPY', 'TLT'],
  snapshot_id: null,
  snapshot_hash: null,
  passed: null,
  verdict: null,
  research_gate_watermark: RESEARCH_GATE_WATERMARK,
  run_context_kind: 'governed_project',
  run_context_project_id: 'project-overridden',
  run_context_watermark: RESEARCH_GATE_WATERMARK,
  mtime: 1,
}

const WATERMARKED_RUN_DETAIL: components['schemas']['RunDetail'] = {
  run_id: WATERMARKED_RUN_ID,
  kind: 'portfolio',
  mtime: 1,
  manifest: {
    command: 'backtest_portfolio',
    symbols: ['SPY', 'TLT'],
    research_gate: { state: 'overridden', watermark: RESEARCH_GATE_WATERMARK },
    run_context: {
      schema_version: 1,
      kind: 'governed_project',
      project_id: 'project-overridden',
      research_gate_state: 'overridden',
      watermark: 'EXPLORATORY',
    },
  },
  research_gate_watermark: RESEARCH_GATE_WATERMARK,
  run_context_kind: 'governed_project',
  run_context_project_id: 'project-overridden',
  run_context_watermark: RESEARCH_GATE_WATERMARK,
  has_equity: false,
  has_trades: false,
  has_tearsheet: false,
  has_forecast: false,
  has_nulls: false,
  has_trials: false,
  has_forecast_paths: false,
  has_propfirm_paths: false,
  has_origins: false,
  has_portfolio_analytics: false,
}

const ACTIVE_GATE_OVERRIDE: components['schemas']['ActiveResearchGateOverride'] = {
  project_id: 'project-override-1',
  project_name: 'SPY exploratory probe',
  sequence: 1,
  actor: 'owner',
  reason: 'Owner accepted exploratory-only engine work before research completes.',
  recorded_at: '2026-08-10T00:00:00Z',
}

const CRYPTO_MANIFEST_ID = '6'.repeat(64)
const CRYPTO_OPTION_MANIFEST_ID = '7'.repeat(64)
const CRYPTO_QUARANTINED_ID = '8'.repeat(64)
const CRYPTO_SNAPSHOT_ID = '9'.repeat(64)
const CRYPTO_ASSET_MASTER_ID = 'd'.repeat(64)
const CRYPTO_COINGECKO_MANIFEST_ID = 'e'.repeat(64)
const CRYPTO_COINGECKO_DETAIL_MANIFEST_ID = '4'.repeat(64)
const CRYPTO_POOL_MANIFEST_ID = 'f'.repeat(64)
const CRYPTO_SOLANA_POOL_MANIFEST_ID = '0'.repeat(64)
const CRYPTO_PROFILE_ID = '1'.repeat(64)
const CRYPTO_SELECTED_PROFILE_ID = '2'.repeat(64)
const CRYPTO_PROFILE_TASK_ID = '3'.repeat(64)
const CRYPTO_COVERAGE: components['schemas']['CryptoCoverageResponse'] = {
  items: [
    {
      manifest_id: CRYPTO_MANIFEST_ID,
      provider: 'bybit',
      venue: 'bybit',
      market_type: 'linear',
      family: 'funding',
      instrument: 'BTCUSDT',
      base_asset: 'BTC',
      quote_asset: 'USDT',
      frequency: 'funding_interval',
      units: 'dimensionless_rate',
      timestamp_convention: 'provider_event_utc',
      state: 'qualified',
      failures: [],
      warnings: [],
      observed_start: '2026-06-01T00:00:00Z',
      observed_end: '2026-08-14T16:00:00Z',
      row_count: 200,
      artifact_sha256: 'a'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: '2026-08-15T00:00:00Z',
    },
    {
      manifest_id: CRYPTO_OPTION_MANIFEST_ID,
      provider: 'bybit',
      venue: 'bybit',
      market_type: 'option',
      family: 'option_quotes',
      instrument: 'BTC',
      base_asset: 'BTC',
      quote_asset: 'USDT',
      frequency: 'point_in_time_chain',
      units: 'provider_native',
      timestamp_convention: 'provider_event_utc',
      state: 'qualified',
      failures: [],
      warnings: [],
      observed_start: '2026-08-15T00:00:00Z',
      observed_end: '2026-08-15T00:00:00Z',
      row_count: 582,
      artifact_sha256: 'b'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: '2026-08-15T00:00:00Z',
    },
    {
      manifest_id: CRYPTO_QUARANTINED_ID,
      provider: 'bybit',
      venue: 'bybit',
      market_type: 'option',
      family: 'option_quotes',
      instrument: 'BTC',
      base_asset: 'BTC',
      quote_asset: 'USD',
      frequency: 'point_in_time_chain',
      units: 'provider_native',
      timestamp_convention: 'provider_event_utc',
      state: 'quarantined',
      failures: ['quote_identity_mismatch'],
      warnings: [],
      observed_start: '2026-08-14T00:00:00Z',
      observed_end: '2026-08-14T00:00:00Z',
      row_count: 582,
      artifact_sha256: 'c'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: null,
    },
    {
      manifest_id: CRYPTO_COINGECKO_DETAIL_MANIFEST_ID,
      provider: 'coingecko',
      venue: 'coingecko',
      market_type: 'reference',
      family: 'asset_metadata',
      instrument: 'bitcoin',
      base_asset: 'BTC',
      quote_asset: null,
      frequency: 'point_in_time_detail',
      units: 'reference_only',
      timestamp_convention: 'provider_observation_utc',
      state: 'qualified',
      failures: [],
      warnings: [],
      observed_start: '2026-08-15T00:01:00Z',
      observed_end: '2026-08-15T00:01:00Z',
      row_count: 1,
      artifact_sha256: '4'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: '2026-08-15T00:01:00Z',
    },
    {
      manifest_id: CRYPTO_COINGECKO_MANIFEST_ID,
      provider: 'coingecko',
      venue: 'coingecko',
      market_type: 'reference',
      family: 'asset_metadata',
      instrument: 'all',
      base_asset: null,
      quote_asset: null,
      frequency: 'catalog_snapshot',
      units: 'metadata',
      timestamp_convention: 'fetch_knowledge_utc',
      state: 'qualified',
      failures: [],
      warnings: [],
      observed_start: '2026-08-15T00:00:00Z',
      observed_end: '2026-08-15T00:00:00Z',
      row_count: 20_000,
      artifact_sha256: 'd'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: '2026-08-15T00:00:00Z',
    },
    {
      manifest_id: CRYPTO_POOL_MANIFEST_ID,
      provider: 'geckoterminal',
      venue: 'geckoterminal',
      market_type: 'dex',
      family: 'dex_pools',
      instrument: 'eth',
      base_asset: 'ETH',
      quote_asset: 'USD',
      frequency: 'catalog_snapshot',
      units: 'provider_native',
      timestamp_convention: 'fetch_knowledge_utc',
      state: 'qualified',
      failures: [],
      warnings: [],
      observed_start: '2026-08-15T00:00:00Z',
      observed_end: '2026-08-15T00:00:00Z',
      row_count: 100,
      artifact_sha256: 'e'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: '2026-08-15T00:00:00Z',
    },
    {
      manifest_id: CRYPTO_SOLANA_POOL_MANIFEST_ID,
      provider: 'geckoterminal',
      venue: 'geckoterminal',
      market_type: 'dex',
      family: 'dex_pools',
      instrument: 'solana',
      base_asset: 'SOL',
      quote_asset: 'USD',
      frequency: 'catalog_snapshot',
      units: 'provider_native',
      timestamp_convention: 'fetch_knowledge_utc',
      state: 'qualified',
      failures: [],
      warnings: [],
      observed_start: '2026-08-15T00:00:00Z',
      observed_end: '2026-08-15T00:00:00Z',
      row_count: 100,
      artifact_sha256: 'f'.repeat(64),
      method_version: 'crypto-quality-v1',
      fetched_at: '2026-08-15T00:00:00Z',
    },
  ],
  count: 6,
  canonical_next_action: 'Select qualified families for a snapshot.',
  automatic_fallback: false,
  execution_authority: false,
}

const CRYPTO_PROFILE_SUMMARY: components['schemas']['CryptoCoverageProfileSummaryResponse'] = {
  profile_id: CRYPTO_PROFILE_ID,
  as_of: '2026-08-15T00:00:00Z',
  source_manifest_ids: ['a'.repeat(64)],
  task_count: 1,
  counts_by_provider: { binance: 1 },
  counts_by_cadence: { daily: 1 },
  counts_by_family: { market_bars: 1 },
  execution_authority: false,
}

const CRYPTO_PROFILE_TASK: components['schemas']['CryptoCoverageTaskResponse'] = {
  schema_version: 1,
  task_id: CRYPTO_PROFILE_TASK_ID,
  provider: 'binance',
  family: 'market_bars',
  instrument: 'BTCUSDT',
  base_asset: 'BTC',
  quote_asset: 'USDT',
  category: 'spot',
  frequency: '1d',
  cadence: 'daily',
  network: null,
  metrics: [],
  lookback_days: null,
  execution_authority: false,
}

// R6h (spec §15): an `open` research-required gate disables strategy-creation and
// optimisation affordances on the Develop desk with the reason and a link to the case;
// grandfathered (`not_required`) projects and non-research contexts stay fully enabled.
const GATED_PROJECT = {
  project_id: RESEARCH_CASE.project_id,
  name: 'Post-earnings drift case',
  hypothesis: 'Large surprises drift for ten sessions.',
  falsification_criterion: 'No drift after matched controls.',
  status: 'active',
  current_version_id: null,
  current_experiment_id: null,
  created_at: '2026-08-09T00:00:00Z',
  updated_at: '2026-08-09T00:00:00Z',
  research_gate_state: 'open',
} satisfies components['schemas']['ProjectSummary']

const UNGATED_PROJECT = {
  ...GATED_PROJECT,
  project_id: 'project-grandfathered-2',
  name: 'Grandfathered momentum book',
  research_gate_state: 'not_required',
} satisfies components['schemas']['ProjectSummary']

const CANDIDATE_VERSION_ID = 'strategy-version-hedged-basis'
const CANDIDATE_EXPERIMENT_ID = 'experiment-hedged-basis'
const CANDIDATE_PROJECT = {
  ...UNGATED_PROJECT,
  project_id: 'project-hedged-basis',
  name: 'BTCUSDT hedged basis candidate',
  current_version_id: CANDIDATE_VERSION_ID,
  current_experiment_id: CANDIDATE_EXPERIMENT_ID,
} satisfies components['schemas']['ProjectSummary']

function projectDetail(
  summary: components['schemas']['ProjectSummary'],
): components['schemas']['ProjectDetail'] {
  return {
    ...summary,
    versions: [],
    experiments: [],
    stage_states: [],
    stage_run_links: [],
    attempts: [],
    holdouts: [],
    holdout_audit: [],
    decision_packets: [],
    monte_carlo_reviews: [],
    research_gate_overrides: [],
    truncated: {
      versions: false,
      experiments: false,
      stage_states: false,
      stage_run_links: false,
      attempts: false,
      holdouts: false,
      holdout_audit: false,
      decision_packets: false,
      monte_carlo_reviews: false,
      research_gate_overrides: false,
    },
  }
}

const PROJECT_WORKSPACE_CATEGORIES = [
  'research',
  'sources',
  'datasets',
  'study-state',
  'promotion',
  'strategy-versions',
  'experiments',
  'runs',
  'validation',
  'figures',
  'reports',
  'sandbox-eligibility',
] as const

function projectWorkspace(
  projectId: string,
): components['schemas']['StrategyProjectWorkspaceProjection'] {
  const revisionId = `spw_${'a'.repeat(64)}`
  return {
    schema_name: 'StrategyProjectWorkspaceProjectionV1',
    schema_version: 1,
    project_id: projectId,
    workspace_root: `strategy-workspaces/project--${projectId}`,
    changed: false,
    recovered: false,
    stale: false,
    workspace: {
      schema_name: 'StrategyProjectWorkspaceV1',
      schema_version: 1,
      revision_id: revisionId,
      project_id: projectId,
      project_name_sha256: 'b'.repeat(64),
      authority: 'none',
      execution_authority: false,
      categories: [...PROJECT_WORKSPACE_CATEGORIES],
      indexes: PROJECT_WORKSPACE_CATEGORIES.map((category) => ({
        category,
        path: `indexes/${category}.json`,
        sha256: 'c'.repeat(64),
        reference_count: 0,
      })),
      sandbox_classification: 'non-transmitting-sandbox-only',
      content_sha256: 'd'.repeat(64),
    },
  }
}

const CANDIDATE_DETAIL = {
  ...projectDetail(CANDIDATE_PROJECT),
  versions: [
    {
      version_id: CANDIDATE_VERSION_ID,
      strategy_name: 'hedged_basis_crowding_v1',
      source_fingerprint: 'git:fixture',
      definition: {
        strategy_name: 'hedged_basis_crowding_v1',
        required_instrument: 'BTCUSDT',
        required_quote_asset: 'USDT',
        required_venues: ['bybit', 'binance'],
        total_round_trip_cost_bps: 40,
        periods_per_year: 1095,
        execution_model: 'two_leg_return_replay',
        deployment_scope: 'sandbox_only',
        paper_blocker: 'UNSUPPORTED_MULTI_VENUE_PAPER',
        places_orders: false,
      },
      parameter_space: {},
      created_at: '2026-08-15T00:00:00Z',
    },
  ],
  experiments: [
    {
      experiment_id: CANDIDATE_EXPERIMENT_ID,
      strategy_version_id: CANDIDATE_VERSION_ID,
      snapshot_id: 'crypto-snapshot-fixture',
      universe: ['BTCUSDT'],
      split_policy: { topology: 'group_atomic_60_20_20' },
      costs: { total_round_trip_bps: 40 },
      seeds: { master: 7 },
      stage_config: {},
      created_at: '2026-08-15T00:00:00Z',
    },
  ],
} satisfies components['schemas']['ProjectDetail']

interface MockOptions {
  chartBundle?: unknown
  trades?: unknown[]
  mlDiagnostics?: boolean
  jobs?: unknown[]
  researchGateOverride?: boolean
  researchGateLock?: boolean
  candidateProject?: boolean
  /** Opt-in so the screenshot baselines keep an empty, deterministic Library rail. */
  runs?: unknown[]
  capturedOwnerAction?: (body: Record<string, unknown>) => void
  researchDataRefreshDelayMs?: number
}

const LIBRARY_RUN = {
  run_id: 'abcdef0123456789',
  kind: 'runs',
  command: 'backtest run',
  label: 'SPY · ts_momentum',
  symbol: 'SPY',
  strategy: 'ts_momentum',
  mtime: 1_700_000_000,
  passed: null,
  verdict: null,
}

const HEAVY_LIBRARY_RUN: components['schemas']['RunListItem'] = {
  run_id: HEAVY_RUN_ID,
  kind: 'runs',
  command: 'backtest_run',
  label: 'AAPL · causal trace fixture',
  symbol: 'AAPL',
  symbols: null,
  snapshot_id: 'causal-fixture',
  snapshot_hash: 'f'.repeat(64),
  passed: null,
  verdict: null,
  research_gate_watermark: null,
  run_context_kind: 'standalone_sandbox',
  run_context_project_id: null,
  run_context_watermark: 'STANDALONE_UNQUALIFIED',
  mtime: 1_700_000_100,
}

async function openHeavyPrice(page: Page): Promise<void> {
  await page.getByRole('navigation', { name: 'Library' }).locator('.library-row').first().click()
  await page.getByRole('tab', { name: 'Research', exact: true }).click()
  await page.getByRole('tab', { name: 'Price', exact: true }).click()
}

function responseFor(route: Route, options: MockOptions): unknown {
  const url = new URL(route.request().url())
  if (url.pathname === '/api/owner-auth/actions/challenge') {
    options.capturedOwnerAction?.(route.request().postDataJSON() as Record<string, unknown>)
    return {
      challenge_id: '00000000-0000-4000-8000-000000000001',
      expires_at: '2026-08-13T02:01:00Z',
      public_key: {
        challenge: 'AQID',
        rpId: 'localhost',
        timeout: 60_000,
        allowCredentials: [],
        userVerification: 'required',
      },
    }
  }
  if (url.pathname === '/api/owner-auth/actions/perform') {
    return { authorization: { receipt_id: 'receipt-1' }, result: { status: 'recorded' } }
  }
  if (url.pathname === '/api/research/cases' && route.request().method() === 'POST') {
    return {
      project: { project_id: RESEARCH_CASE.project_id },
      contract: RESEARCH_CASE.active_contract,
      case: RESEARCH_CASE,
    }
  }
  if (
    url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/proposal-options`
    && route.request().method() === 'GET'
  ) return RESEARCH_PROPOSAL_OPTIONS
  if (
    url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}`
    && route.request().method() === 'GET'
  ) return RESEARCH_CLOSED_CASE
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/status`) {
    return RESEARCH_CASE
  }
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/semantic-projection`) {
    return RESEARCH_SEMANTIC_READ
  }
  if (
    url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/report`
    && route.request().method() === 'GET'
  ) return RESEARCH_GATE_PACKET
  if (url.pathname === '/api/research/cases' && route.request().method() === 'GET') {
    return RESEARCH_CASE_PAGE
  }
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/evidence-hub`) {
    return RESEARCH_EVIDENCE_HUB
  }
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/scorecard`) {
    return RESEARCH_SCORECARD
  }
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/decision-view`) {
    return RESEARCH_DECISION_VIEW
  }
  if (url.pathname === '/api/research/protocols') return RESEARCH_PROTOCOLS
  if (url.pathname === '/api/research/datasets') {
    return {
      items: [
        {
          ref_id: `rd_${'9'.repeat(64)}`,
          dataset_kind: 'snapshot',
          instrument: 'AAPL',
          provider: 'tiingo',
          start_ts: '2020-01-01',
          end_ts: '2020-06-01',
          bar_duration_minutes: null,
          origin: { snapshot_id: 'snap1', manifest_sha256: '8'.repeat(64) },
          research_only: true,
          registered_by: 'owner',
          registered_at: '2026-08-09T00:00:00Z',
          latest_audit: { summary: { blocking_count: 0, limiting_count: 1 } },
        },
      ] satisfies components['schemas']['ResearchDatasetRefRow'][],
      limit: 100,
      offset: 0,
    }
  }
  if (url.pathname === '/api/crypto-data/catalog') {
    return {
      families: [
        { family: 'asset_metadata', provider: 'coingecko', role: 'primary_acquisition' },
        { family: 'funding', provider: 'bybit', role: 'primary_acquisition' },
        { family: 'instrument_catalog', provider: 'bybit', role: 'primary_acquisition' },
        { family: 'derivative_bars', provider: 'bybit', role: 'primary_acquisition' },
        { family: 'derivative_trades', provider: 'bybit', role: 'primary_acquisition' },
        { family: 'derivative_book_snapshots', provider: 'bybit', role: 'primary_acquisition' },
        { family: 'option_quotes', provider: 'bybit', role: 'primary_acquisition' },
        { family: 'comparison_bars', provider: 'ccxt:coinbase', role: 'diagnostic_comparison' },
      ],
      automatic_fallback: false,
      execution_authority: false,
      next_action: 'Check storage before estimating or acquiring data.',
    } satisfies components['schemas']['CryptoCatalogResponse']
  }
  if (url.pathname === '/api/crypto-data/capabilities') {
    return {
      items: [
        {
          schema_version: 1,
          provider: 'bybit',
          family: 'funding',
          authentication: 'none',
          earliest: '2026-06-01T00:00:00+00:00',
          latest: '2026-08-14T00:00:00+00:00',
          frequencies: ['funding_interval'],
          limits: ['bybit_page_200'],
          verification_state: 'receipt_verified',
          qualification_state: 'qualified',
        },
        {
          schema_version: 1,
          provider: 'bybit',
          family: 'option_quotes',
          authentication: 'none',
          earliest: '2026-08-14T00:00:00+00:00',
          latest: '2026-08-14T00:00:00+00:00',
          frequencies: ['point_in_time_chain'],
          limits: ['hourly_all_supported_underlyings'],
          verification_state: 'receipt_verified',
          qualification_state: 'qualified',
        },
      ],
      count: 2,
      receipt_verified_count: 2,
      qualified_count: 2,
      provider_probe_performed: false,
      automatic_fallback: false,
      execution_authority: false,
      canonical_next_action: 'Inspect qualified coverage and freeze an exact snapshot.',
    } satisfies components['schemas']['CryptoCapabilitiesResponse']
  }
  if (url.pathname === '/api/crypto-data/asset-masters' && route.request().method() === 'GET') {
    return {
      items: [
        {
          asset_master_version: 'reviewed-native-v1',
          identity_count: 2,
          contract_identity_count: 0,
          builtin: true,
          state: 'verified',
        },
        {
          asset_master_version: CRYPTO_ASSET_MASTER_ID,
          identity_count: 3,
          contract_identity_count: 1,
          builtin: false,
          state: 'verified',
        },
      ],
      count: 2,
      ticker_join_allowed: false,
      next_action: 'Build an exact contract identity map.',
    } satisfies components['schemas']['CryptoAssetMasterListResponse']
  }
  if (url.pathname === '/api/crypto-data/asset-masters' && route.request().method() === 'POST') {
    expect(route.request().postDataJSON()).toEqual({
      coingecko_manifest_id: CRYPTO_COINGECKO_MANIFEST_ID,
      geckoterminal_manifest_ids: [
        CRYPTO_POOL_MANIFEST_ID,
        CRYPTO_SOLANA_POOL_MANIFEST_ID,
      ],
    })
    return {
      asset_master_version: CRYPTO_ASSET_MASTER_ID,
      identity_count: 3,
      contract_identity_count: 1,
      source_manifest_ids: [
        CRYPTO_COINGECKO_MANIFEST_ID,
        CRYPTO_POOL_MANIFEST_ID,
        CRYPTO_SOLANA_POOL_MANIFEST_ID,
      ],
      ticker_join_allowed: false,
      state: 'frozen',
      next_action: 'Use this exact asset-master version when freezing a snapshot.',
    } satisfies components['schemas']['CryptoAssetMasterResponse']
  }
  if (url.pathname === `/api/crypto-data/asset-masters/${CRYPTO_ASSET_MASTER_ID}/verify`) {
    return {
      asset_master_version: CRYPTO_ASSET_MASTER_ID,
      identity_count: 3,
      contract_identity_count: 1,
      source_manifest_ids: null,
      ticker_join_allowed: false,
      state: 'verified',
      next_action: 'Freeze a snapshot bound to this exact asset-master version.',
    } satisfies components['schemas']['CryptoAssetMasterResponse']
  }
  if (url.pathname === '/api/crypto-data/assets/contracts/ethereum/0xusdc') {
    return {
      schema_version: 1,
      coingecko_id: 'usd-coin',
      network: 'ethereum',
      contract_address: '0xusdc',
      native_asset: false,
      provider_symbols: [['coingecko', 'usd-coin'], ['geckoterminal', '0xusdc']],
      valid_from: '2026-08-15T00:00:00Z',
      valid_to: null,
      migration_lineage: [],
    } satisfies components['schemas']['CryptoAssetIdentityResponse']
  }
  if (url.pathname === '/api/crypto-data/storage') {
    return {
      state: 'ready',
      blocker: null,
      bulk_root_label: 'crypto-data',
      manifest_count: 6,
      next_action: 'Estimate one bounded dataset acquisition.',
      free_bytes: 1_800_000_000_000,
      total_bytes: 2_000_000_000_000,
      reserve_fraction: 0.15,
      minimum_free_bytes: 100_000_000_000,
      cache_bytes: 25_000_000,
    } satisfies components['schemas']['CryptoStorageResponse']
  }
  if (url.pathname === '/api/crypto-data/storage/inventory') {
    return {
      manifest_count: 6, snapshot_count: 1,
      counts_by_kind: { raw: 3, normalized: 3 },
      bytes_by_kind: { raw: 10_000_000, normalized: 20_000_000 },
      cache_bytes: 25_000_000, staging_count: 0,
      private_paths_exposed: false,
      next_action: 'Run storage-verify before relying on frozen snapshots.',
    } satisfies components['schemas']['CryptoStorageInventoryResponse']
  }
  if (url.pathname === '/api/crypto-data/storage/verify') {
    return {
      state: 'verified', manifest_count: 6, snapshot_count: 1,
      research_eligible_snapshot_count: 1, asset_master_count: 1, cache_bytes: 25_000_000,
      private_paths_exposed: false, next_action: 'Continue.',
    } satisfies components['schemas']['CryptoStorageVerifyResponse']
  }
  if (url.pathname === '/api/crypto-data/storage/cache/clean') {
    return {
      state: 'cleaned', removed_bytes: 25_000_000,
      immutable_artifacts_removed: 0, private_paths_exposed: false,
      next_action: 'Run storage-inventory to confirm current capacity.',
    } satisfies components['schemas']['CryptoCacheCleanResponse']
  }
  if (url.pathname === '/api/crypto-data/coverage') return CRYPTO_COVERAGE
  if (url.pathname === '/api/crypto-data/features' && route.request().method() === 'GET') {
    return {
      items: [], count: 0, research_authority: false, execution_authority: false,
      next_action: 'Create only a feature supported by exact qualified inputs.',
    } satisfies components['schemas']['CryptoFeatureListResponse']
  }
  if (url.pathname === '/api/crypto-data/features' && route.request().method() === 'POST') {
    return {
      manifest_id: '0'.repeat(64), feature_id: 'a'.repeat(64), feature_name: 'funding',
      method_version: 'crypto-features-v1', available_at: '2026-08-15T00:00:00Z',
      row_count: 200, artifact_sha256: 'b'.repeat(64), input_count: 1, state: 'frozen',
      research_authority: false, execution_authority: false,
      next_action: 'Bind this feature beside its exact frozen crypto snapshot.',
    } satisfies components['schemas']['CryptoFeatureResponse']
  }
  if (url.pathname === '/api/crypto-data/profiles' && route.request().method() === 'GET') {
    return {
      items: [CRYPTO_PROFILE_SUMMARY], count: 1, execution_authority: false,
      next_action: 'Create a fresh profile after catalog membership changes.',
    } satisfies components['schemas']['CryptoCoverageProfileListResponse']
  }
  if (url.pathname === '/api/crypto-data/profiles' && route.request().method() === 'POST') {
    return {
      ...CRYPTO_PROFILE_SUMMARY, state: 'frozen', binance_hourly_scopes: [],
      binance_hourly_missing_scopes: [['spot', 'USDT']],
      next_action: 'Acquire the complete prior-day scope.',
    } satisfies components['schemas']['CryptoCoverageProfileCreateResponse']
  }
  if (url.pathname === `/api/crypto-data/profiles/${CRYPTO_PROFILE_ID}`) {
    return {
      ...CRYPTO_PROFILE_SUMMARY,
      offset: Number(url.searchParams.get('offset') ?? 0),
      limit: Number(url.searchParams.get('limit') ?? 50),
      filtered_count: 1,
      filters: {
        provider: url.searchParams.get('provider'),
        family: url.searchParams.get('family'),
        category: url.searchParams.get('category'),
        frequency: url.searchParams.get('frequency'),
        cadence: url.searchParams.get('cadence'),
      },
      items: [CRYPTO_PROFILE_TASK], has_more: false, next_offset: null,
      next_action: 'Run only the intended bounded cadence batch.',
    } satisfies components['schemas']['CryptoCoverageProfilePageResponse']
  }
  if (url.pathname === `/api/crypto-data/profiles/${CRYPTO_PROFILE_ID}/batches`) {
    return { job_id: 'crypto-profile-job', status: 'running', session_id: null }
  }
  if (url.pathname === '/api/crypto-data/batches') {
    return {
      items: [], count: 0, execution_authority: false,
      next_action: 'Resume only a failed batch after resolving its blocker.',
    } satisfies components['schemas']['CryptoCoverageBatchListResponse']
  }
  if (url.pathname === `/api/crypto-data/profiles/${CRYPTO_PROFILE_ID}/liquidity-membership`) {
    return {
      manifest_id: '4'.repeat(64), profile_id: CRYPTO_PROFILE_ID,
      session: '2026-08-14', category: 'spot', quote_asset: 'USDT',
      universe_count: 1, selected_count: 1, state: 'frozen', execution_authority: false,
      next_action: 'Create a fresh profile.',
    } satisfies components['schemas']['CryptoLiquidityFreezeResponse']
  }
  if (url.pathname === `/api/crypto-data/profiles/${CRYPTO_PROFILE_ID}/one-minute-selection`) {
    return {
      profile_id: CRYPTO_SELECTED_PROFILE_ID, base_profile_id: CRYPTO_PROFILE_ID,
      selection_manifest_id: '5'.repeat(64), project_id: RESEARCH_CASE.project_id,
      case_revision: RESEARCH_PROPOSAL_OPTIONS.case_revision, selected_count: 1,
      frequency: '1m', acquisition_window: 'previous_complete_hour', state: 'frozen',
      execution_authority: false, next_action: 'Run the intended hourly page.',
    } satisfies components['schemas']['CryptoOneMinuteSelectionResponse']
  }
  if (url.pathname === '/api/crypto-data/estimate') {
    return {
      family: 'option_quotes',
      provider: 'bybit',
      instruments: 1,
      days: 30,
      frequency: '1h',
      estimated_rows: 720,
      estimated_bytes: 345_600,
      bounded: true,
      estimate_only: true,
      next_action: 'Verify storage, then start one bounded acquisition.',
    } satisfies components['schemas']['CryptoEstimateResponse']
  }
  if (url.pathname === '/api/crypto-data/acquisitions') {
    return { job_id: 'crypto-job-1', status: 'running', session_id: null }
  }
  if (url.pathname === '/api/crypto-data/snapshots') {
    return {
      snapshot_id: CRYPTO_SNAPSHOT_ID,
      member_count: 1,
      families: ['option_quotes'],
      providers: ['bybit'],
      asset_master_version: CRYPTO_ASSET_MASTER_ID,
      state: 'frozen',
      next_action: 'Verify the snapshot for the exact research purpose.',
      execution_authority: false,
    } satisfies components['schemas']['CryptoSnapshotCreateResponse']
  }
  if (url.pathname === `/api/crypto-data/snapshots/${CRYPTO_SNAPSHOT_ID}/verify`) {
    return {
      snapshot_id: CRYPTO_SNAPSHOT_ID,
      eligible: true,
      purpose: 'research',
      qualified_families: ['option_quotes'],
      supplemental_families: [],
      blockers: [],
      next_action: 'Bind this snapshot to the exact research proposal.',
      execution_authority: false,
    } satisfies components['schemas']['CryptoSnapshotVerifyResponse']
  }
  if (url.pathname === `/api/crypto-data/snapshots/${CRYPTO_SNAPSHOT_ID}/register`) {
    return {
      ref_id: `rd_${'c'.repeat(64)}`,
      dataset_kind: 'snapshot',
      instrument: 'BTC',
      provider: 'crypto-data-house',
      start_ts: '2026-08-15T00:00:00Z',
      end_ts: '2026-08-15T00:00:00Z',
      bar_duration_minutes: null,
      origin: {
        snapshot_id: CRYPTO_SNAPSHOT_ID,
        manifest_sha256: 'd'.repeat(64),
        snapshot_schema: 'CryptoSnapshotV1',
      },
      research_only: true,
      registered_by: 'owner',
      registered_at: '2026-08-15T00:00:00Z',
    } satisfies components['schemas']['CryptoSnapshotRegisterResponse']
  }
  if (url.pathname === `/api/crypto-data/quality/${CRYPTO_OPTION_MANIFEST_ID}`) {
    return {
      manifest_id: CRYPTO_OPTION_MANIFEST_ID,
      dataset: {
        provider: 'bybit', venue: 'bybit', market_type: 'option', family: 'option_quotes',
        instrument: 'BTC', base_asset: 'BTC', quote_asset: 'USDT',
        frequency: 'point_in_time_chain', units: 'provider_native',
        timestamp_convention: 'provider_event_utc',
      },
      quality: {
        schema_version: 1, dataset_sha256: 'b'.repeat(64),
        method_version: 'crypto-quality-v1', state: 'qualified', failures: [], warnings: [],
        observed_start: '2026-08-15T00:00:00Z', observed_end: '2026-08-15T00:00:00Z',
        row_count: 582, correction_lineage: [],
      },
      next_action: 'Select this dataset for a frozen snapshot.',
    } satisfies components['schemas']['CryptoQualityResponse']
  }
  if (url.pathname === '/api/crypto-data/assets/BTC') {
    return {
      schema_version: 1,
      coingecko_id: 'bitcoin', network: 'bitcoin', contract_address: null,
      native_asset: true, provider_symbols: [['bybit', 'BTC']],
      valid_from: '2009-01-03T00:00:00Z', valid_to: null, migration_lineage: [],
    } satisfies components['schemas']['CryptoAssetIdentityResponse']
  }
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/context-packets`) {
    return { items: [RESEARCH_PACKET], limit: 50, offset: 0 }
  }
  if (url.pathname === `/api/research/context-packets/${RESEARCH_PACKET.packet_id}`) {
    return RESEARCH_PACKET
  }
  if (url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}/notes`) {
    return { items: [RESEARCH_NOTE], limit: 100, offset: 0 }
  }
  if (options.mlDiagnostics && url.pathname === '/api/ml/experiments') {
    return { items: [ML_EXPERIMENT], limit: 50, offset: 0, has_more: false }
  }
  if (
    options.mlDiagnostics &&
    url.pathname === `/api/ml/exchanges/${ML_EXCHANGE_ID}/tear-sheet`
  ) {
    return ML_DIAGNOSTIC_TEARSHEET
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}/chart-bundle`) {
    return options.chartBundle
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}/figures`) {
    return { run_id: HEAVY_RUN_ID, kind: 'runs', figures: [] }
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}`) {
    return {
      run_id: HEAVY_RUN_ID,
      kind: 'runs',
      mtime: 0,
      manifest: { command: 'backtest_run', symbol: 'SPY', schema_version: 3 },
      has_equity: false,
      has_trades: Boolean(options.trades?.length),
      has_tearsheet: false,
      has_forecast: false,
      has_nulls: false,
      has_trials: false,
      has_forecast_paths: false,
      has_propfirm_paths: false,
      has_origins: false,
      research_gate_watermark: null,
    }
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}/native-tearsheet`) {
    return EMPTY_NATIVE_TEARSHEET
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}/trades`) {
    return options.trades ?? []
  }
  if (url.pathname === '/api/research-gate-overrides') {
    return options.researchGateOverride ? [ACTIVE_GATE_OVERRIDE] : []
  }
  if (options.researchGateOverride && url.pathname === `/api/runs/${WATERMARKED_RUN_ID}`) {
    return WATERMARKED_RUN_DETAIL
  }
  if (
    options.researchGateOverride
    && url.pathname === `/api/runs/${WATERMARKED_RUN_ID}/figures`
  ) {
    return { run_id: WATERMARKED_RUN_ID, kind: 'portfolio', figures: [] }
  }
  if (
    options.researchGateOverride
    && url.pathname === `/api/runs/${WATERMARKED_RUN_ID}/native-tearsheet`
  ) {
    return EMPTY_NATIVE_TEARSHEET
  }
  if (options.researchGateOverride && url.pathname === '/api/risk/scenario') {
    return {
      run_id: WATERMARKED_RUN_ID,
      confidence: 0.95,
      scenarios: [],
      provenance: {
        source_run_id: WATERMARKED_RUN_ID,
        source_command: 'backtest_portfolio',
        source_artifact: 'equity_curve.parquet',
        source_artifact_sha256: 'f'.repeat(64),
        snapshot_id: null,
        snapshot_hash: null,
        research_cutoff: null,
        as_of: null,
        timezone: 'UTC',
        derived_projection: true,
      },
    }
  }
  if (options.researchGateOverride && url.pathname === '/api/runs') {
    return { items: [WATERMARKED_RUN_ITEM], total: 1 }
  }
  if (url.pathname === '/api/runs') {
    const items = options.runs ?? []
    return { items, total: items.length }
  }
  if (url.pathname === `/api/runs/${LIBRARY_RUN.run_id}`) {
    return {
      run_id: LIBRARY_RUN.run_id,
      kind: 'runs',
      mtime: LIBRARY_RUN.mtime,
      manifest: { command: 'backtest_run', symbol: 'SPY', schema_version: 3 },
      has_equity: false,
      has_trades: false,
      has_tearsheet: false,
      has_forecast: false,
      has_nulls: false,
      has_trials: false,
      has_forecast_paths: false,
      has_propfirm_paths: false,
      has_origins: false,
    }
  }
  if (url.pathname === `/api/runs/${LIBRARY_RUN.run_id}/figures`) {
    return { run_id: LIBRARY_RUN.run_id, kind: 'runs', figures: [] }
  }
  if (url.pathname === '/api/symbols') return { symbols: [] }
  if (url.pathname === '/api/strategies' || url.pathname === '/api/commands') return []
  if (url.pathname === '/api/providers') return []
  if (url.pathname === '/api/system') return SYSTEM_STATUS
  if (url.pathname === '/api/jobs') return options.jobs ?? []
  if (url.pathname === '/api/workspaces') return []
  if (url.pathname === '/api/paper/sessions') return []
  if (url.pathname === '/api/paper/readiness') return {
    schema_version: 1,
    status: 'pending',
    paper_passed: false,
    requirements: [],
    blocking_events: [],
    futures_research_supported: false,
    live_capital_routing: 'absent',
    derived_from_elapsed_time: false,
  }
  if (url.pathname === '/api/screener/quote') {
    return {
      symbol: url.searchParams.get('symbol') ?? 'AAPL',
      current: 100,
      change: 0,
      percent_change: 0,
      open: 100,
      high: 100,
      low: 100,
      prev_close: 100,
    }
  }
  if (url.pathname === '/api/screener/news') {
    return { symbol: url.searchParams.get('symbol') ?? 'AAPL', items: [] }
  }
  if (options.researchGateLock && url.pathname === '/api/projects') {
    return { items: [GATED_PROJECT, UNGATED_PROJECT], limit: 50, offset: 0, has_more: false }
  }
  if (options.researchGateLock && url.pathname === `/api/projects/${GATED_PROJECT.project_id}`) {
    return projectDetail(GATED_PROJECT)
  }
  if (options.researchGateLock && url.pathname === `/api/projects/${UNGATED_PROJECT.project_id}`) {
    return projectDetail(UNGATED_PROJECT)
  }
  if (options.candidateProject && url.pathname === '/api/projects') {
    return { items: [CANDIDATE_PROJECT], limit: 100, offset: 0, has_more: false }
  }
  if (options.candidateProject && url.pathname === `/api/projects/${CANDIDATE_PROJECT.project_id}`) {
    return CANDIDATE_DETAIL
  }
  const workspaceMatch = url.pathname.match(/^\/api\/projects\/([^/]+)\/workspace(?:\/refresh)?$/)
  if (workspaceMatch) return projectWorkspace(decodeURIComponent(workspaceMatch[1]))
  const candidatePlanMatch = url.pathname.match(
    /^\/api\/projects\/project-hedged-basis\/experiments\/experiment-hedged-basis\/suite\/([^/]+)\/plan$/,
  )
  if (options.candidateProject && candidatePlanMatch) {
    const action = candidatePlanMatch[1] as components['schemas']['SuiteActionValue']
    return {
      schema_version: 1,
      project_id: CANDIDATE_PROJECT.project_id,
      experiment_id: CANDIDATE_EXPERIMENT_ID,
      action,
      stage: action === 'holdout_reveal' ? 'holdout' : 'baseline',
      current_stage_state: 'not_started',
      ready: action === 'holdout_reveal',
      blockers: action === 'holdout_reveal' ? [] : ['Fixture preview is intentionally blocked.'],
      steps: action === 'holdout_reveal' ? [{
        index: 1,
        label: 'Reveal exact one-shot fixture holdout',
        command: ['alpha', 'suite', 'run', '--action', 'holdout_reveal'],
        evidence_role: 'fixture_holdout',
      }] : [],
      estimated_workload: { class: 'bounded', description: 'One local immutable fixture step.' },
      governance: { owner_only_launch: true, browser_authority: false },
      resolved_experiment: CANDIDATE_DETAIL.experiments[0],
      resolved_strategy_version: CANDIDATE_DETAIL.versions[0],
    } satisfies components['schemas']['SuitePlan']
  }
  if (url.pathname === `/api/projects/${RESEARCH_CASE.project_id}`) {
    return projectDetail(GATED_PROJECT)
  }
  if (url.pathname === '/api/projects') return EMPTY_PAGE
  if (url.pathname === '/api/development/jobs') return EMPTY_PAGE
  if (url.pathname === '/api/evidence') return EMPTY_PAGE
  if (url.pathname === '/api/ml/experiments') return EMPTY_PAGE
  if (url.pathname === '/api/ml/experiments/preflight') {
    return {
      schema_version: 1,
      project_id: url.searchParams.get('project_id') ?? 'project-1',
      experiment_id: null,
      snapshot_id: null,
      universe_count: 0,
      aligned_sessions: 0,
      active_job_id: null,
      ready: false,
      checks: [
        {
          check_id: 'experiment',
          state: 'blocked',
          message: 'No current immutable experiment is selected.',
          recovery_action: 'Create or select an experiment in Development Center.',
        },
      ],
    }
  }
  if (url.pathname === '/api/ml/status') {
    return {
      available: true,
      worker_ready: true,
      active_job_id: null,
      concurrency_limit: 1,
      min_symbols: 20,
      min_aligned_sessions: 756,
      isolation: 'separate locked worker',
      message: null,
    }
  }
  throw new Error(`unmocked API request: ${route.request().method()} ${url.pathname}`)
}

async function preparePage(page: Page, options: MockOptions = {}): Promise<void> {
  await page.addInitScript(() => {
    localStorage.clear()

    class DeterministicEventSource extends EventTarget {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSED = 2
      readonly CONNECTING = 0
      readonly OPEN = 1
      readonly CLOSED = 2
      readonly url: string
      readonly withCredentials = false
      readyState = DeterministicEventSource.OPEN
      onopen: ((event: Event) => void) | null = null
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null

      constructor(url: string | URL) {
        super()
        this.url = String(url)
        queueMicrotask(() => {
          this.dispatchEvent(new MessageEvent('snapshot', { data: '{"jobs_running":0}' }))
        })
      }

      close(): void {
        this.readyState = DeterministicEventSource.CLOSED
      }
    }

    Object.defineProperty(window, 'EventSource', {
      configurable: true,
      value: DeterministicEventSource,
    })

    class DeterministicAssertionResponse {
      readonly authenticatorData = new Uint8Array([1, 2, 3]).buffer
      readonly clientDataJSON = new Uint8Array([4, 5, 6]).buffer
      readonly signature = new Uint8Array([7, 8, 9]).buffer
      readonly userHandle = null
    }

    class DeterministicPublicKeyCredential {
      readonly id = 'test-owner-credential'
      readonly type = 'public-key'
      readonly rawId = new Uint8Array([10, 11, 12]).buffer
      readonly authenticatorAttachment = 'platform'
      readonly response = new DeterministicAssertionResponse()
      getClientExtensionResults(): AuthenticationExtensionsClientOutputs {
        return {}
      }
    }

    Object.defineProperty(window, 'AuthenticatorAssertionResponse', {
      configurable: true,
      value: DeterministicAssertionResponse,
    })
    Object.defineProperty(window, 'PublicKeyCredential', {
      configurable: true,
      value: DeterministicPublicKeyCredential,
    })
    Object.defineProperty(navigator, 'credentials', {
      configurable: true,
      value: {
        get: async () => new DeterministicPublicKeyCredential(),
      },
    })
  })

  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      await route.abort('blockedbyclient')
      return
    }
    await route.continue()
  })
  let capturedInThisPage = false
  let researchDatasetReadCount = 0
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/research/datasets') {
      researchDatasetReadCount += 1
      if (researchDatasetReadCount > 1 && options.researchDataRefreshDelayMs) {
        await new Promise((resolve) => setTimeout(resolve, options.researchDataRefreshDelayMs))
      }
    }
    if (url.pathname === '/api/research/cases' && route.request().method() === 'POST') {
      capturedInThisPage = true
    }
    if (
      capturedInThisPage
      && url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}`
      && route.request().method() === 'GET'
    ) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(RESEARCH_CASE),
      })
      return
    }
    if (
      options.researchGateLock
      && route.request().method() === 'GET'
      && url.pathname === `/api/research/cases/${UNGATED_PROJECT.project_id}`
    ) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Research case not found' }),
      })
      return
    }
    const body = responseFor(route, options)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })

  await page.goto('')
  await expect(page.getByText('ALPHA', { exact: true })).toBeVisible()
}

async function expectReleaseAccessibility(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'])
    .analyze()
  const blocking = results.violations.filter(
    (violation) => violation.impact === 'serious' || violation.impact === 'critical',
  )
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([])
}

export function registerWorkstationTests(): void {
for (const item of SCREENS) {
  test(`${item.label} screen renders and clears the accessibility release gate`, async ({
    page,
  }) => {
    await preparePage(page)
    const tab = page.getByRole('tab', { name: item.label, exact: true })
    await tab.click()

    await expect(tab).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByText(/panel crashed/i)).toHaveCount(0)

    const expectedViewport = PROJECT_VIEWPORTS[test.info().project.name]
    expect(expectedViewport).toBeDefined()
    const viewport = page.viewportSize()
    expect(viewport).toEqual(expectedViewport)
    const shellBounds = await page.locator('.shell').boundingBox()
    expect(shellBounds?.width).toBe(expectedViewport.width)
    expect(shellBounds?.height).toBe(expectedViewport.height)
    // The page itself must never scroll sideways; wide content scrolls inside its own pane.
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      expectedViewport.width,
    )

    await expectReleaseAccessibility(page)
    if (
      test.info().project.name === 'chromium-reference' ||
      test.info().project.name === 'chromium-wide'
    ) {
      await page.evaluate(() => document.fonts.ready)
      await expect(page.locator('.shell')).toHaveScreenshot(`${item.id}-screen.png`, {
        animations: 'disabled',
        caret: 'hide',
        maxDiffPixelRatio: 0.02,
      })
    }
  })
}

test('screen tabs are keyboard operable', async ({ page }) => {
  await preparePage(page)
  const research = page.getByRole('tab', { name: 'Research', exact: true })
  await research.focus()
  await expect(research).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('tab', { name: 'Build', exact: true })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('tab', { name: 'Build', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('the library rail lists runs and opens one into the report', async ({ page }) => {
  await preparePage(page, { runs: [LIBRARY_RUN] })
  const rail = page.getByRole('navigation', { name: 'Library' })
  await expect(rail).toBeVisible()
  const firstRun = rail.locator('.library-row').first()
  await expect(firstRun).toBeVisible()
  await firstRun.click()
  // Opening a run switches to Results rather than spawning a floating window.
  await expect(page.getByRole('tab', { name: 'Results', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('Research Cockpit captures an idea through the bounded REST surface', async ({ page }) => {
  await preparePage(page)

  await page.getByRole('tab', { name: 'Research Case', exact: true }).click()

  await expect(page.locator('.panel-toolbar .title').filter({ hasText: 'Research Case' })).toBeVisible()
  await page.getByLabel('Raw research idea').fill(RESEARCH_RAW_IDEA)
  await page.getByRole('button', { name: 'capture · no compute' }).click()

  await expect(page.getByText('TRIAGE', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('APPROVAL UNAVAILABLE', { exact: true })).toBeVisible()
  await expect(page.getByText(RESEARCH_QUESTIONS[0].prompt, { exact: true })).toBeVisible()
  await expect(page.getByText(RESEARCH_QUESTIONS[1].prompt, { exact: true })).toBeVisible()
  await expect(page.getByText(RESEARCH_QUESTIONS[2].prompt, { exact: true })).toBeVisible()
  await expect(page.getByText(/Uses equal 60-minute bars and a four-trading-hour pattern window/)).toBeVisible()
  await expect(page.getByText(/D2 SEALED: research confirmation remains governed/)).toBeVisible()
  await expect(page.getByText(/SYNTHETIC D0 IS NOT REAL-MARKET EVIDENCE/)).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('all material questions and consequences stay visible at the supported viewport', async ({ page }) => {
  await preparePage(page)
  await page.getByLabel('Raw research idea').fill(RESEARCH_RAW_IDEA)
  await page.getByRole('button', { name: 'capture · no compute' }).click()

  const questions = page.getByLabel('Material research questions')
  await expect(questions).toBeVisible()
  await expect(page.getByText(RESEARCH_QUESTIONS[0].prompt, { exact: true })).toBeInViewport()
  await expect(page.getByText(RESEARCH_QUESTIONS[1].prompt, { exact: true })).toBeInViewport()
  await expect(page.getByText(RESEARCH_QUESTIONS[2].prompt, { exact: true })).toBeInViewport()
  await expect(page.getByText(RESEARCH_QUESTIONS[2].choices[0].consequence, { exact: true })).toBeInViewport()
})

test('a research decision requires fresh Touch ID and sends no caller actor', async ({ page }) => {
  let challenge: Record<string, unknown> | null = null
  await preparePage(page, { capturedOwnerAction: (body) => { challenge = body } })
  await page.getByLabel('Raw research idea').fill(RESEARCH_RAW_IDEA)
  await page.getByRole('button', { name: 'capture · no compute' }).click()

  await page.getByLabel('Decision reason').fill('The proposed operator is unavailable.')
  await page.getByRole('button', { name: 'Touch ID · reject exploration' }).click()

  await expect.poll(() => challenge).not.toBeNull()
  expect(challenge).toMatchObject({
    action_type: 'reject_exploration',
    project_id: RESEARCH_CASE.project_id,
    artifact_hash: 'a'.repeat(64),
    reason: 'The proposed operator is unavailable.',
    payload: { contract_id: RESEARCH_CONTRACT_ID },
  })
  expect(challenge).not.toHaveProperty('actor')
})

test('guided mode defaults and advanced detail is remembered only for its project', async ({ page }) => {
  await preparePage(page)
  await page.getByRole('tab', { name: 'Backlog', exact: true }).click()
  await page.getByRole('button', { name: new RegExp(RESEARCH_CASE.project_name) }).click()
  const guided = page.getByRole('button', { name: 'Guided', exact: true })
  const advanced = page.getByRole('button', { name: 'Advanced', exact: true })
  await expect(guided).toHaveAttribute('aria-pressed', 'true')
  await advanced.click()
  await expect(advanced).toHaveAttribute('aria-pressed', 'true')

  await page.locator('.context-chip').click()
  await page.getByPlaceholder('project id').fill('')
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Guided', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('tab', { name: 'Backlog', exact: true }).click()
  await page.getByRole('button', { name: new RegExp(RESEARCH_CASE.project_name) }).click()
  await expect(page.getByRole('button', { name: 'Advanced', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('Research Cockpit teaches the bounded terminal Gate Packet without upgrading evidence', async ({ page }) => {
  await preparePage(page)

  await page.getByRole('tab', { name: 'Research Case', exact: true }).click()
  await page.getByLabel('Research Case project ID').fill(RESEARCH_CASE.project_id)
  await page.getByRole('button', { name: 'open case' }).click()
  await expect(page.getByText('CLOSED', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'progress report' }).click()

  await expect(page.getByText('90-second Research Gate conclusion', { exact: true })).toBeVisible()
  await expect(page.getByText('NO TYPED NON SYNTHETIC EVIDENCE', { exact: true })).toBeVisible()
  await expect(page.getByText('NOT TESTED', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/strategy validated false · paper ready false · places orders false/)).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('Research Cockpit Decision tab assembles checklist, scorecard, packet, and history', async ({ page }) => {
  await preparePage(page)

  await page.getByRole('tab', { name: 'Research Case', exact: true }).click()
  await page.getByLabel('Research Case project ID').fill(RESEARCH_CASE.project_id)
  await page.getByRole('button', { name: 'open case' }).click()
  await expect(page.getByText('CLOSED', { exact: true }).first()).toBeVisible()

  await page.getByRole('tab', { name: 'Decision', exact: true }).click()
  // The fourteen spec-§10.1 questions render as typed statuses, never a numeric aggregate.
  await expect(page.getByText(/Edge-validation checklist · fourteen questions/)).toBeVisible()
  await expect(page.getByText('1. Does the effect exist?')).toBeVisible()
  await expect(page.getByText('14. How much uncertainty remains?')).toBeVisible()
  // The full scorecard, terminal gate packet, and append-only history ride the same view.
  await expect(page.getByText('Full readiness scorecard', { exact: true })).toBeVisible()
  await expect(page.getByText('MORE RESEARCH REQUIRED').first()).toBeVisible()
  await expect(page.getByText('90-second Research Gate conclusion', { exact: true })).toBeVisible()
  await expect(page.getByText(/INCONCLUSIVE · PARK · owner \(human\)/)).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('Research Cockpit Study tab preserves masking and owner-only D1 authority', async ({ page }) => {
  await preparePage(page)

  await page.getByRole('tab', { name: 'Research Case', exact: true }).click()
  await page.getByLabel('Research Case project ID').fill(RESEARCH_CASE.project_id)
  await page.getByRole('button', { name: 'open case' }).click()
  await page.getByRole('tab', { name: 'Study', exact: true }).click()

  await expect(page.getByLabel('Verified semantic study status')).toBeVisible()
  await expect(page.getByText('visible-1', { exact: true })).toBeVisible()
  await expect(page.getByText('8', { exact: true })).toBeVisible()
  await expect(page.getByText('bounded reversal', { exact: true })).toBeVisible()
  await expect(page.getByText('OWNER CLI ONLY', { exact: true })).toBeVisible()
  await expect(page.getByText(/Freeze the approved semantic definition with fresh Touch ID/)).toBeVisible()
  await expect(page.getByRole('button', { name: /launch.*D1/i })).toHaveCount(0)
  await expectReleaseAccessibility(page)
})

test('research workflow links the backlog, cockpit, evidence, and Codex panels', async ({ page }) => {
  await preparePage(page)

  await page.getByRole('tab', { name: 'Backlog', exact: true }).click()
  await expect(page.getByText('Needs you (1)')).toBeVisible()

  await page.getByRole('button', { name: new RegExp(RESEARCH_CASE.project_name) }).click()
  await page.getByRole('tab', { name: 'Research Case', exact: true }).click()
  await expect(page.getByText('CLOSED', { exact: true }).first()).toBeVisible()

  await page.getByRole('tab', { name: 'Evidence', exact: true }).click()
  await expect(page.getByRole('tab', { name: 'Evidence for', exact: true })).toBeVisible()
  // Literature claims render screened vs draft distinctly, claims map before bibliography.
  await page.getByLabel('Evidence sections').getByRole('tab', { name: 'Literature' }).click()
  await expect(page.getByText('SCREENED', { exact: true })).toBeVisible()
  await expect(page.getByText('DRAFT — UNSCREENED', { exact: true })).toBeVisible()
  await expect(page.getByText('Search concepts', { exact: true })).toBeVisible()
  await expect(page.getByText('Budget: 20 candidates · 5 full texts · explicit click only')).toBeVisible()
  await expect(page.getByText(/Decision support only/)).toBeVisible()
  await expect(page.getByText(/LEGACY — NO TEXT ANCHOR/).first()).toBeVisible()
  await page.getByRole('tab', { name: 'Falsification', exact: true }).click()
  await expect(page.getByText('Shuffled-label control shows no effect')).toBeVisible()
  await expect(page.getByText('NOT_TESTED', { exact: true }).first()).toBeVisible()
  // Evidence against renders with the same component and prominence as evidence for.
  await page.getByRole('tab', { name: 'Evidence against', exact: true }).click()
  await expect(page.getByText(/No typed findings of this direction exist yet/)).toBeVisible()

  // The linked case follows into the Codex panel, which fences commentary as never-evidence.
  await page.getByRole('tab', { name: 'Codex Research', exact: true }).click()
  await expect(page.getByText('MCP-ATTACHED · NO CHAT · NO API KEY', { exact: true })).toBeVisible()
  await expect(page.getByText(/RECORDING HAPPENS ON THE GOVERNED SEAMS/)).toBeVisible()
  await expect(page.getByText('CODEX COMMENTARY — NOT EVIDENCE', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /cp_f+/ }).click()
  await expect(page.getByText('"packet_schema": "ResearchContextPacketV1"')).toBeVisible()

  // The Research data panel serves registered refs with audit badges and the forever badge.
  await page.getByRole('tab', { name: 'Data Manager', exact: true }).click()
  await page.getByRole('tab', { name: 'Research Data', exact: true }).click()
  await expect(page.getByText('1 LIMITING', { exact: true })).toBeVisible()
  await expect(page.getByText('RESEARCH ONLY', { exact: true })).toBeVisible()
  await expect(page.getByText(/snapshot snap1 · manifest/)).toBeVisible()
  await expectReleaseAccessibility(page)
})

}

export async function cryptoDataCenterJourney(page: Page): Promise<void> {
  await preparePage(page, { researchDataRefreshDelayMs: 400 })

  await page.getByRole('tab', { name: 'Data Manager', exact: true }).click()
  await page.getByRole('tab', { name: 'Research Data', exact: true }).click()
  const center = page.getByRole('region', { name: 'Crypto Data Center' })
  await expect(center.getByText('Select qualified datasets for one exact frozen snapshot.')).toBeVisible()
  await center.getByRole('tab', { name: 'Assets & Contracts', exact: true }).click()
  await expect(center.getByLabel('Dataset family')).toHaveValue('asset_metadata')
  await expect(center.getByLabel('Instrument')).toHaveValue('all')
  await center.getByRole('button', { name: 'Build from latest qualified catalogs', exact: true }).click()
  await expect(center.getByText('FROZEN · 1 contract mappings', { exact: true })).toBeVisible()
  await center.getByLabel('Contract address').fill('0xusdc')
  await center.getByRole('button', { name: 'Resolve exact contract', exact: true }).click()
  await expect(center.getByText('usd-coin', { exact: true })).toBeVisible()
  await center.getByRole('button', { name: 'Verify identity map', exact: true }).click()
  await expect(center.getByText('VERIFIED · 1 contract mappings', { exact: true })).toBeVisible()
  await center.getByRole('tab', { name: 'CEX History', exact: true }).click()
  await center.getByLabel('Dataset family').selectOption('comparison_bars')
  await expect(center.getByLabel('Instrument')).toHaveValue('BTC/USD')
  await expect(center.getByLabel('Quote asset')).toHaveValue('USD')
  await expect(center.getByLabel('Market')).toHaveValue('spot')
  await expect(center.getByLabel('Frequency')).toHaveValue('1d')
  await expect(center.getByLabel('Start UTC')).toBeVisible()
  await center.getByRole('tab', { name: 'Derivatives & Funding', exact: true }).click()
  await center.getByLabel('Dataset family').selectOption('derivative_book_snapshots')
  await expect(center.getByLabel('Market').getByRole('option', { name: 'option' })).toHaveCount(1)
  await expect(center.getByLabel('Start UTC')).toHaveCount(0)
  await center.getByLabel('Dataset family').selectOption('instrument_catalog')
  await expect(center.getByLabel('Market').getByRole('option', { name: 'option' })).toHaveCount(1)
  await center.getByRole('tab', { name: 'Options & Volatility', exact: true }).click()
  await expect(center.getByLabel('Market')).toHaveValue('option')
  await expect(center.getByLabel('Market').getByRole('option')).toHaveCount(1)
  await expect(center.getByText('RECEIPT VERIFIED', { exact: true })).toBeVisible()
  await expect(center.getByLabel('Provider dataset capability')).toContainText(
    'Stored coverage: 2026-08-14T00:00:00+00:00',
  )
  await expect(center.getByText('option quotes · bybit/bybit').first()).toBeVisible()
  await expect(center.getByText('QUARANTINED', { exact: true })).toBeVisible()

  await center.getByRole('button', { name: 'Estimate storage', exact: true }).click()
  await expect(center.getByText(/720 rows · about/)).toBeVisible()
  await center.getByLabel('Frequency').selectOption('5m')
  await expect(center.getByText(/720 rows · about/)).toHaveCount(0)

  await center.getByRole('button', { name: 'Acquire & qualify', exact: true }).click()
  await expect(center.getByText(/Fetching one bounded provider response/)).toBeVisible()
  await expect(center.getByText(/normalized_manifest_id/)).toHaveCount(0)

  await center.getByLabel('Select qualified option_quotes BTC USDT').check()
  await expect(center.getByText('Freeze the 1 selected qualified dataset into a snapshot.')).toBeVisible()
  await center.getByRole('button', { name: 'Freeze selected snapshot', exact: true }).click()
  await expect(center.getByText('Frozen · 1 members', { exact: true })).toBeVisible()
  await center.getByRole('button', { name: 'Verify for research', exact: true }).click()
  await expect(center.getByText('ELIGIBLE', { exact: true })).toBeVisible()
  await expect(center.getByText(new RegExp(CRYPTO_SNAPSHOT_ID))).toBeHidden()
  await center.getByRole('button', { name: 'Register research-only dataset', exact: true }).click()
  await expect(center.getByText('REGISTERED · RESEARCH ONLY', { exact: true })).toBeVisible()
  await expect(page.getByText('REFRESHING REGISTERED DATASETS', { exact: true })).toBeVisible()
  await expect(page.getByText('Loading stored symbol inventory…', { exact: true })).toBeVisible()
  await expect(center.getByText(/does not make an incompatible case executable/)).toBeVisible()
  await expect(center.getByText(new RegExp(`rd_${'c'.repeat(64)}`))).toBeHidden()

  const qualifiedOption = center.locator('.crypto-dataset').filter({ hasText: 'USDT' }).first()
  await qualifiedOption.getByRole('button', { name: 'Quality', exact: true }).click()
  await expect(center.getByText(/Mechanical quality · BTC · option quotes/)).toBeVisible()
  await center.getByRole('tab', { name: 'Derivatives & Funding', exact: true }).click()
  await center.getByLabel('Select qualified funding BTCUSDT USDT').check()
  await center.getByRole('tab', { name: 'Coverage & Quality', exact: true }).click()
  await expect(center.getByText('EXACT INPUTS READY', { exact: true })).toBeVisible()
  await center.getByRole('button', { name: 'Freeze selected feature', exact: true }).click()
  await expect(center.getByText('FROZEN AND VERIFIED · funding', { exact: true })).toBeVisible()

  await center.getByRole('tab', { name: 'Storage & Jobs', exact: true }).click()
  await expect(center.getByText('Default coverage profile', { exact: true })).toBeVisible()
  await expect(center.getByText('binance 1', { exact: true })).toBeVisible()
  await expect(center.getByText('Run only the intended bounded cadence batch.')).toBeVisible()
  await center.getByRole('button', { name: 'Run these 1 tasks', exact: true }).click()
  await expect(center.getByText(/Running at most 25 exact tasks/)).toBeVisible()
  await center.getByLabel('Complete UTC session').fill('2026-08-14')
  await center.getByRole('button', { name: 'Freeze top-liquidity membership', exact: true }).click()
  await expect(center.getByText('FROZEN · 1 OF 1', { exact: true })).toBeVisible()
  const oneMinuteMarket = center.locator('.crypto-market-picker label').filter({ hasText: 'BTCUSDT' })
  await oneMinuteMarket.getByRole('checkbox').check()
  await expect(center.getByText('SELECT A RESEARCH CASE', { exact: true })).toBeVisible()
  await expect(center.getByRole('button', { name: 'Freeze 1 selected market', exact: true })).toBeDisabled()
  await expect(center.getByText(new RegExp(CRYPTO_PROFILE_ID))).toBeHidden()
  await expect(center.getByText('READY', { exact: true })).toBeVisible()
  await expect(center.getByText('1.8 TB free of 2.0 TB')).toBeVisible()
  await expect(center.getByText(/\/Volumes\//)).toHaveCount(0)
  await center.getByRole('button', { name: 'Inspect storage inventory', exact: true }).click()
  await expect(center.getByText(/6 manifests · 1 snapshots · 0 staged downloads/)).toBeVisible()
  await center.getByRole('button', { name: 'Verify all immutable data', exact: true }).click()
  await expect(center.getByText(/6 manifests and 1 snapshots re-hashed/)).toBeVisible()
  await center.getByRole('button', { name: 'Review cache cleanup', exact: true }).click()
  await expect(center.getByText('CONFIRM CACHE CLEANUP', { exact: true })).toBeVisible()
  await center.getByRole('button', { name: 'Confirm clean removable cache', exact: true }).click()
  await expect(center.getByText('CACHE CLEANED', { exact: true })).toBeVisible()
  await expect(center.getByText(/immutable artifacts removed: 0/)).toBeVisible()

  const overflow = await page.locator('.research-data-explorer').evaluate(
    (element) => element.scrollWidth - element.clientWidth,
  )
  expect(overflow).toBe(0)
  await expectReleaseAccessibility(page)
}

export function registerWorkstationFeatureTests(): void {
test('New Idea opens natural-language capture with zero trading-rule inputs', async ({ page }) => {
  await preparePage(page)

  await page.getByRole('button', { name: 'New Idea' }).click()
  await expect(page.getByRole('tab', { name: 'Research', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByRole('tab', { name: 'Research Case', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  const capture = page.getByLabel('Raw research idea')
  await expect(capture).toBeVisible()
  await expect(capture).toBeFocused()

  // Spec §2.4: the capture flow is one natural-language textarea plus an optional name
  // (and the explicit case-ID lookup) — no entry-rule, stop, target, indicator,
  // parameter, or optimisation input of any kind.
  const controls = page.locator(
    '.research-intake-grid input, .research-intake-grid textarea, .research-intake-grid select',
  )
  await expect(controls).toHaveCount(3)
  const descriptors = await controls.evaluateAll((nodes) =>
    nodes.map(
      (node) =>
        `${node.getAttribute('aria-label') ?? ''} ${node.getAttribute('placeholder') ?? ''}`,
    ),
  )
  for (const descriptor of descriptors) {
    expect(descriptor).not.toMatch(/entry|stop|target|indicator|param|optimi|rule|size|leverage/i)
  }
  await expectReleaseAccessibility(page)
})

test('running jobs expose exact runtime, bounded ETA, progress, and live output', async ({ page }) => {
  await preparePage(page, {
    jobs: [
      {
        job_id: 'job-progress-fixture',
        command: 'forecast eval AMZN --horizon 21',
        command_path: 'forecast eval',
        kind: 'forecast',
        status: 'running',
        created_at: Date.now() / 1_000 - 120,
        finished_at: null,
        elapsed_seconds: 120,
        current_step: 'Evaluating rolling forecast origin 8 of 20',
        progress_mode: 'estimated',
        progress_fraction: 0.4,
        eta_seconds: 180,
        eta_sample_count: 3,
        run_id: null,
        session_id: null,
        returncode: null,
        n_lines: 14,
      },
    ],
  })
  // Jobs sit under the Build screen, beside the lab that launches them.
  await page.getByRole('tab', { name: 'Build', exact: true }).click()

  await expect(page.getByText(/Elapsed\s+2m 0\ds/)).toBeVisible()
  await expect(page.getByText(/ETA\s+~3 min/)).toBeVisible()
  await expect(page.getByText(/Evaluating rolling forecast origin 8 of 20/)).toBeVisible()
  const progress = page.getByRole('progressbar', { name: 'Job forecast eval progress' })
  await expect(progress).toHaveAttribute('aria-valuenow', /4\d/)
  await page.getByRole('button', { name: 'live log' }).click()
  await expect(page.getByText(/Waiting for process output/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'hide log' })).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('a failed job row shows the CLI error message, never a box border', async ({ page }) => {
  const message = 'No data for XRP/USDT on binance before 2018-05-04 (first listed). Start there? (--start 2018-05-04)'
  await preparePage(page, {
    jobs: [
      {
        job_id: 'job-failed-fixture',
        command: 'data pull XRP/USDT --source ccxt --exchange binance --start 2015-01-01 --end 2026-06-30',
        command_path: 'data pull',
        kind: null,
        status: 'failed',
        created_at: Date.now() / 1_000 - 30,
        finished_at: Date.now() / 1_000 - 20,
        elapsed_seconds: 10,
        current_step: message,
        progress_mode: 'terminal',
        progress_fraction: null,
        eta_seconds: null,
        eta_sample_count: 0,
        run_id: null,
        session_id: null,
        returncode: 2,
        n_lines: 3,
      },
    ],
  })
  await page.getByRole('tab', { name: 'Build', exact: true }).click()
  await expect(page.getByTitle(message)).toBeVisible()
  await expect(page.getByText(/[─│╭╮╰╯]/)).toHaveCount(0)
  await expectReleaseAccessibility(page)
})

test('ML diagnostics render bounded Qlib evidence and the permanent authority warning', async ({ page }) => {
  await preparePage(page, { mlDiagnostics: true })
  await page.getByRole('tab', { name: 'Studios', exact: true }).click()
  await page.getByRole('tab', { name: 'ML diagnostics', exact: true }).click()

  await expect(page.locator('.rd-head').filter({ hasText: 'Score distribution' })).toBeVisible()
  await expect(page.locator('.rd-head').filter({ hasText: 'IC / RankIC timeline' })).toBeVisible()
  await expect(page.locator('.rd-head').filter({ hasText: 'Feature importance' })).toBeVisible()
  await expect(page.getByText(/MODEL NOT RECOMPUTED UNDER COUNTERFACTUAL/i).first()).toBeVisible()
  await expect(page.getByText('0.9.7', { exact: true })).toBeVisible()
  await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
  await expectReleaseAccessibility(page)
})

test('causal chart paginates evidence, selects an event, and exports exact OHLCV', async ({ page }) => {
  await preparePage(page, {
    chartBundle: causalChartBundle(),
    trades: CAUSAL_TRADES,
    runs: [HEAVY_LIBRARY_RUN],
  })
  await openHeavyPrice(page)

  await expect(page.getByText('205 bars', { exact: true })).toBeVisible()
  await expect(page.getByText(/1–80 \/ 91 RETURNED EVENTS/)).toBeVisible()
  await expect(page.getByText(/BACKEND PROJECTION TRUNCATED · MORE TRACE EVENTS EXIST/)).toBeVisible()
  await page.getByRole('button', { name: 'Next trace page' }).click()
  await expect(page.getByText(/81–91 \/ 91 RETURNED EVENTS/)).toBeVisible()

  // Selecting a trace event names it and draws its holding period on the chart. The
  // two-way link to the trade blotter is not asserted here: the blotter now lives inside
  // Run Detail on the Results screen, so the two are never on screen together.
  await page.locator('button.trace-event').filter({ hasText: '0091' }).click()
  await expect(page.getByText('trade · #91', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Previous trace page' }).click()
  await page.locator('button.trace-event').first().click()
  await expect(page.getByText('trade · #91', { exact: true })).toHaveCount(0)

  await page.getByText(/OHLCV TABLE AND EXACT CSV/i).click()
  await expect(page.getByText(/1–100 \/ 205 RETURNED BARS/)).toBeVisible()
  await page.getByRole('button', { name: 'Next OHLCV page' }).click()
  await expect(page.getByText(/101–200 \/ 205 RETURNED BARS/)).toBeVisible()

  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download exact returned OHLCV CSV' }).click()
  const download = await downloadEvent
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()
  const csv = await readFile(downloadPath!, 'utf8')
  const lines = csv.trimEnd().split('\n')
  expect(lines).toHaveLength(206)
  expect(lines[0]).toBe('timestamp_utc,open,high,low,close,volume')
  expect(lines[1]).toBe('2025-01-01T00:00:00.000Z,100,102,99,101,1000')
  expect(lines.at(-1)).toBe(
    `${new Date((CAUSAL_START_TS + 204 * 86_400) * 1_000).toISOString()},304,306,303,305,1204`,
  )
  await expectReleaseAccessibility(page)
})

test('dense causal chart layers cap visuals without hiding returned evidence', async ({ page }) => {
  await preparePage(page, { chartBundle: denseCausalChartBundle(), runs: [HEAVY_LIBRARY_RUN] })
  await openHeavyPrice(page)

  const executions = page.getByRole('button', { name: 'executions', exact: true })
  const decisions = page.getByRole('button', { name: 'decisions', exact: true })
  const all = page.getByRole('button', { name: 'all', exact: true })
  await expect(executions).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('90/180 markers shown', { exact: true })).toBeVisible()
  await decisions.click()
  await expect(decisions).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('90/180 markers shown', { exact: true })).toBeVisible()
  await all.click()
  await expect(all).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('140/180 markers shown', { exact: true })).toBeVisible()
  await expect(page.getByText(/1–80 \/ 180 RETURNED EVENTS/)).toBeVisible()
})

test('a screen mounts only what it shows', async ({ page }) => {
  const requested: string[] = []
  page.on('request', (request) => requested.push(new URL(request.url()).pathname))
  await preparePage(page)

  // Research is the opening screen. Hidden panes and other screens must not fetch.
  expect(requested).not.toContain('/api/screener/quote')
  expect(requested).not.toContain('/api/screener/news')
  expect(requested).not.toContain('/api/paper/sessions')

  await page.getByRole('tab', { name: 'Studios', exact: true }).click()
  await page.getByRole('tab', { name: 'Market Overview', exact: true }).click()
  await expect
    .poll(() => requested.filter((path) => path === '/api/screener/quote').length)
    .toBeGreaterThan(0)
})

test('legacy trace rerun opens the governed Development Center', async ({ page }) => {
  await preparePage(page, { chartBundle: causalChartBundle(false), runs: [HEAVY_LIBRARY_RUN] })
  await openHeavyPrice(page)

  await expect(page.getByText('TRACE UNAVAILABLE', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Rerun for causal trace' }).click()
  // The intent has to reach the shell: switch screens *and* surface the governed panel.
  await expect(page.getByRole('tab', { name: 'Build', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText('Development Center', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
})

test('research-gate override watermark reaches provider governance and run results', async ({ page }) => {
  await preparePage(page, { researchGateOverride: true })

  // Provider governance lists every active override with actor + recorded reason (spec §15).
  await page.getByRole('tab', { name: 'Operate', exact: true }).click()
  await page.getByRole('tab', { name: 'Providers & system', exact: true }).click()
  await expect(page.getByText('SPY exploratory probe')).toBeVisible()
  await expect(
    page.getByText('Owner accepted exploratory-only engine work before research completes.'),
  ).toBeVisible()

  // Selecting the watermarked run from the persistent Library opens its immutable results.
  await page.getByRole('navigation', { name: 'Library' }).locator('.library-row').first().click()
  await expect(page.getByRole('tab', { name: 'Results', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText(RESEARCH_GATE_WATERMARK).first()).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('open research gates lock strategy affordances on Develop and link to the case', async ({ page }) => {
  await preparePage(page, { researchGateLock: true })
  await page.getByRole('tab', { name: 'Operate', exact: true }).click()

  // Development Center auto-selects the research-required project and blocks versioning.
  await expect(page.getByText('RESEARCH GATE OPEN')).toHaveCount(1)
  await page.getByLabel('Clean source fingerprint').fill('git:0000000')
  await expect(page.getByRole('button', { name: 'Create immutable version' })).toBeDisabled()

  // Strategy Lab and Pipeline share the same backend gate and block strategy execution.
  await page.getByRole('tab', { name: 'Build', exact: true }).click()
  await expect(page.getByText('RESEARCH GATE OPEN')).toHaveCount(2)
  await expect(page.getByRole('button', { name: /Launch backtest run/ })).toBeDisabled()
  const preps = page.getByRole('button', { name: '▶ prep' })
  await expect(preps.first()).toBeEnabled() // 1 · Data — pulling history is not strategy work
  await expect(preps.nth(1)).toBeDisabled() // 2 · Backtest
  await expect(preps.nth(3)).toBeDisabled() // 4 · Optimize
  await expectReleaseAccessibility(page)

  // The case link lands on the Research desk with the holding case in focus.
  await page.getByRole('button', { name: /Open research case/ }).first().click()
  await expect(page.getByRole('tab', { name: 'Research', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByRole('tab', { name: 'Research Case', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText('Research Case', { exact: true }).first()).toBeVisible()

  // Non-research context — the grandfathered project re-enables every affordance.
  await page.getByRole('tab', { name: 'Build', exact: true }).click()
  await page.getByRole('tab', { name: 'Development Center', exact: true }).click()
  await page.getByLabel('Strategy project').selectOption(UNGATED_PROJECT.project_id)
  await page.getByLabel('Clean source fingerprint').fill('git:0000000')
  await expect(page.getByRole('button', { name: 'Create immutable version' })).toBeEnabled()
  await page.getByRole('tab', { name: 'Strategy Development', exact: true }).click()
  await expect(page.getByText('RESEARCH GATE OPEN')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Launch backtest run/ })).toBeEnabled()
  await page.getByRole('tab', { name: 'Development Next Step', exact: true }).click()
  await expect(preps.nth(1)).toBeEnabled()
})

}

export async function sandboxCandidateJourney(page: Page): Promise<void> {
  await preparePage(page, { candidateProject: true })
  await page.getByRole('tab', { name: 'Operate', exact: true }).click()

  const candidate = page.getByRole('region', { name: 'Sandbox hedged basis candidate' })
  await expect(candidate.getByText('Hedged basis candidate', { exact: true })).toBeVisible()
  await expect(candidate.getByText('SHORT BYBIT LINEAR PERPETUAL', { exact: true })).toBeVisible()
  await expect(candidate.getByText('LONG BINANCE SPOT', { exact: true })).toBeVisible()
  await expect(candidate.getByText('40 bp total round trip', { exact: true })).toBeVisible()
  await expect(candidate.getByText('365-DAY CRYPTO / 1,095 PERIODS', { exact: true })).toBeVisible()
  await expect(candidate.getByText('two_leg_return_replay', { exact: true })).toBeVisible()
  await expect(candidate.getByText('UNSUPPORTED_MULTI_VENUE_PAPER', { exact: true })).toBeVisible()
  await expect(
    candidate.getByText('Promoted contract and exact snapshot are reverified by the server for every run.'),
  ).toBeVisible()

  await expect(page.getByText('Owner checkpoints · trusted CLI only', { exact: true })).toBeVisible()
  await expect(page.getByRole('textbox', { name: /owner/i })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /freeze candidate/i })).toHaveCount(0)

  await page.getByRole('button', { name: 'Holdout reveal · trusted CLI' }).click()
  await expect(page.getByText('TRUSTED CLI OWNER CHECKPOINT', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Trusted CLI required' })).toBeDisabled()
  await expectReleaseAccessibility(page)
}

export function registerReferenceTests(): void {
test('@reference-only cold shell and screen switch meet workstation latency budgets', async ({ page }) => {
  await preparePage(page)

  const coldShellMs = await page.evaluate(() => performance.now())
  expect(coldShellMs).toBeLessThan(1_500)

  const switchMs = await page.evaluate(async () => {
    const tab = [...document.querySelectorAll<HTMLButtonElement>('.screen-tab')].find(
      (button) => button.textContent?.trim() === 'Operate',
    )
    if (!tab) throw new Error('the Operate screen tab is unavailable')
    const started = performance.now()
    tab.click()
    for (let frame = 0; frame < 12; frame += 1) {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
      if (document.body.textContent?.includes('Development Center')) {
        return performance.now() - started
      }
    }
    throw new Error('the Operate screen did not render within 12 animation frames')
  })
  expect(switchMs).toBeLessThan(100)
})

test('@reference-only 25k bars and 200 annotations remain interactively responsive', async ({ page }) => {
  test.setTimeout(45_000)
  const bundle = heavyChartBundle()
  await preparePage(page, { chartBundle: bundle, runs: [HEAVY_LIBRARY_RUN] })

  const renderStarted = Date.now()
  await openHeavyPrice(page)

  await expect(page.getByText(`${HEAVY_BAR_COUNT} bars`, { exact: true })).toBeVisible({
    timeout: 12_000,
  })
  const chart = page.locator('.price-chart-canvas-wrap')
  await expect(chart).toBeVisible()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())))
  expect(Date.now() - renderStarted).toBeLessThan(12_000)

  await chart.hover()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())))
  const before = await chart.screenshot()
  const interactionStarted = Date.now()
  await page.mouse.wheel(0, -600)
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  )
  const after = await chart.screenshot()

  expect(after.equals(before)).toBe(false)
  expect(Date.now() - interactionStarted).toBeLessThan(2_000)

  const cadence = await chart.evaluate(async (element) => {
    const measure = async (interactive: boolean) => {
      const intervals: number[] = []
      let previous = performance.now()
      for (let frame = 0; frame < 60; frame += 1) {
        await new Promise<void>((resolve) =>
          requestAnimationFrame((timestamp) => {
            intervals.push(timestamp - previous)
            previous = timestamp
            if (interactive) {
              element.dispatchEvent(
                new WheelEvent('wheel', {
                  bubbles: true,
                  cancelable: true,
                  deltaY: frame % 2 ? 24 : -24,
                }),
              )
            }
            resolve()
          }),
        )
      }
      const measured = intervals.slice(1).sort((left, right) => left - right)
      const percentile = (fraction: number): number =>
        measured[Math.min(measured.length - 1, Math.floor(measured.length * fraction))]!
      return {
        medianFrameMs: percentile(0.5),
        p99FrameMs: percentile(0.99),
        overBudgetRatio: measured.filter((interval) => interval > 20).length / measured.length,
      }
    }
    return { baseline: await measure(false), interactive: await measure(true) }
  })
  // A 60 Hz desk has a 16.67 ms frame budget. Headless Chromium on macOS periodically reports
  // 25–27 ms rAF intervals even with no dispatched interaction, so compare chart navigation with
  // an immediately adjacent no-input baseline instead of misclassifying host scheduler jitter.
  expect(cadence.interactive.medianFrameMs).toBeLessThanOrEqual(18)
  expect(cadence.interactive.overBudgetRatio).toBeLessThanOrEqual(
    cadence.baseline.overBudgetRatio + 0.05,
  )
  expect(cadence.interactive.p99FrameMs).toBeLessThanOrEqual(34)
})
}
