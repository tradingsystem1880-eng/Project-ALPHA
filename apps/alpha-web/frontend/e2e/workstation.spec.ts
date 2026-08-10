import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import type { components } from '../src/api/generated'
import { deriveResearchChecklist } from '../src/panels/researchChecklistModel'

const DESKS = [
  { id: 'research', label: 'RESEARCH', activePanel: 'Research Cockpit' },
  { id: 'market', label: 'MARKET', activePanel: 'Market Chart' },
  { id: 'development', label: 'DEVELOP', activePanel: 'Development Center' },
  { id: 'kronos', label: 'KRONOS', activePanel: 'Kronos Forecast Studio' },
  { id: 'ml', label: 'ML LAB', activePanel: 'ML Signal Tear Sheet' },
  { id: 'portfolio', label: 'PORTFOLIO', activePanel: 'Portfolio Evidence' },
  { id: 'operations', label: 'OPS', activePanel: 'Providers & System' },
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

// Typed against the generated contract so ANY future ResearchCase drift fails the
// frontend type gate instead of silently passing a stale mocked shape to e2e.
const RESEARCH_CASE: components['schemas']['ResearchCase'] = {
  schema_version: 1,
  project_id: 'research-project-1',
  project_name: 'SPY double bottom',
  phase: 'triage',
  execution_state: 'idle',
  active_contract_id: 'research-contract-1',
  active_contract: {
    contract_id: 'research-contract-1',
    project_id: 'research-project-1',
    scope: 'exploration',
    parent_contract_id: null,
    payload: {
      raw_idea: RESEARCH_RAW_IDEA,
      approval_ready: false,
      blocking_questions: [
        'Which equal-duration chart construction is intended?',
        'When does the event become knowable?',
        'What is the primary economic endpoint?',
      ],
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
  exploration_contract_id: 'research-contract-1',
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
  unresolved_questions: { count: 3, items: RESEARCH_CASE.active_contract.payload.blocking_questions as string[] },
  recommendation: {
    value: 'MORE RESEARCH REQUIRED',
    reasons: ['10 of 12 readiness dimensions are untested.', '3 unresolved questions remain.'],
  },
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
      outstanding_questions: RESEARCH_CASE.active_contract.payload.blocking_questions as string[],
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
        },
      ],
      sources: [],
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

// The checklist rides the TS twin so the mock can never drift from the derivation the
// panel actually renders; the twin itself is pinned to Python by the committed fixture.
const RESEARCH_DECISION_VIEW: components['schemas']['ResearchDecisionView'] = {
  view_schema: 'ResearchDecisionViewV1',
  project_id: RESEARCH_CASE.project_id,
  phase: 'closed',
  d2_state: 'sealed',
  next_action: 'Research Case is closed.',
  checklist: deriveResearchChecklist({
    inputs_schema: 'ResearchScorecardInputsV1',
    phase: 'closed',
    outcome: 'INCONCLUSIVE',
    disposition: 'park',
    d2_state: 'sealed',
    hypothesis_complete_fields: 1,
    hypothesis_partial_fields: 0,
    hypothesis_total_fields: 14,
    registered_dataset_count: 0,
    screened_claim_count: 0,
    blocking_questions: RESEARCH_CASE.active_contract.payload.blocking_questions as string[],
    confounders_resolved: [],
    confounders_unresolved: ['day of week', 'volatility regime'],
    untested_work: ['No typed D1 or D2 empirical result is present.'],
    attempt_count: 0,
    primary_result_status: 'NOT_TESTED',
    practical_magnitude_status: 'NOT_TESTED',
    confirmation_classification: null,
    power_status: 'NOT_TESTED',
    negative_controls_status: 'NOT_TESTED',
    multiplicity_status: 'NOT_TESTED',
    mechanism_status: 'NOT_TESTED',
    stability_parameter_status: 'NOT_TESTED',
    stability_temporal_status: 'NOT_TESTED',
    stability_transportability_status: 'NOT_TESTED',
  }),
  scorecard: RESEARCH_SCORECARD,
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

interface MockOptions {
  chartBundle?: unknown
  trades?: unknown[]
  mlDiagnostics?: boolean
  jobs?: unknown[]
}

function responseFor(route: Route, options: MockOptions): unknown {
  const url = new URL(route.request().url())
  if (url.pathname === '/api/research/cases' && route.request().method() === 'POST') {
    return {
      project: { project_id: RESEARCH_CASE.project_id },
      contract: RESEARCH_CASE.active_contract,
      case: RESEARCH_CASE,
    }
  }
  if (
    url.pathname === `/api/research/cases/${RESEARCH_CASE.project_id}`
    && route.request().method() === 'GET'
  ) return RESEARCH_CLOSED_CASE
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
    }
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}/native-tearsheet`) {
    return EMPTY_NATIVE_TEARSHEET
  }
  if (options.chartBundle && url.pathname === `/api/runs/${HEAVY_RUN_ID}/trades`) {
    return options.trades ?? []
  }
  if (url.pathname === '/api/runs') return { items: [], total: 0 }
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
  if (url.pathname === '/api/projects') return EMPTY_PAGE
  if (url.pathname === '/api/development/jobs') return EMPTY_PAGE
  if (url.pathname === '/api/evidence') return EMPTY_PAGE
  if (url.pathname === '/api/ml/experiments') return EMPTY_PAGE
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
  })

  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.hostname !== '127.0.0.1') {
      await route.abort('blockedbyclient')
      return
    }
    await route.continue()
  })
  await page.route('**/api/**', async (route) => {
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

for (const desk of DESKS) {
  test(`${desk.label} desk renders and clears the accessibility release gate`, async ({ page }) => {
    await preparePage(page)
    const deskControl = page.getByLabel('DESK')
    await deskControl.selectOption(desk.id)

    await expect(deskControl).toHaveValue(desk.id)
    await expect(page.getByText(desk.activePanel, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(/panel crashed/i)).toHaveCount(0)

    const expectedViewport = PROJECT_VIEWPORTS[test.info().project.name]
    expect(expectedViewport).toBeDefined()
    const viewport = page.viewportSize()
    expect(viewport).toEqual(expectedViewport)
    const shellBounds = await page.locator('.shell').boundingBox()
    expect(shellBounds?.width).toBe(expectedViewport.width)
    expect(shellBounds?.height).toBe(expectedViewport.height)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      expectedViewport.width,
    )

    await expectReleaseAccessibility(page)
    if (
      test.info().project.name === 'chromium-reference' ||
      test.info().project.name === 'chromium-wide'
    ) {
      await page.evaluate(() => document.fonts.ready)
      await expect(page.locator('.shell')).toHaveScreenshot(`${desk.id}-desk.png`, {
        animations: 'disabled',
        caret: 'hide',
        maxDiffPixelRatio: 0.02,
      })
    }
  })
}

test('desk control is keyboard operable', async ({ page }) => {
  await preparePage(page)
  const deskControl = page.getByLabel('DESK')

  await page.keyboard.press('Tab')
  await expect(deskControl).toBeFocused()
  await page.keyboard.press('d')

  await expect(deskControl).toHaveValue('development')
  await expect(page.getByText('Development Center', { exact: true }).first()).toBeVisible()
})

test('Research Cockpit captures an idea through the bounded REST surface', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport Cockpit gate')
  await preparePage(page)

  await page.getByRole('button', { name: /Search/ }).click()
  await page.getByRole('option', { name: /Research Cockpit/ }).click()

  await expect(page.locator('.panel-toolbar .title').filter({ hasText: 'Research Cockpit' })).toBeVisible()
  await page.getByLabel('Raw research idea').fill(RESEARCH_RAW_IDEA)
  await page.getByRole('button', { name: 'capture · no compute' }).click()

  await expect(page.getByText('TRIAGE', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('GATE 1 OPERATOR UNAVAILABLE', { exact: true })).toBeVisible()
  await expect(page.getByText(/D2 SEALED: research confirmation remains governed/)).toBeVisible()
  await expect(page.getByText(/SYNTHETIC D0 IS NOT REAL-MARKET EVIDENCE/)).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('Research Cockpit teaches the bounded terminal Gate Packet without upgrading evidence', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport terminal-packet gate')
  await preparePage(page)

  await page.getByRole('button', { name: /Search/ }).click()
  await page.getByRole('option', { name: /Research Cockpit/ }).click()
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

test('Research Cockpit Decision tab assembles checklist, scorecard, packet, and history', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport decision-view gate')
  await preparePage(page)

  await page.getByRole('button', { name: /Search/ }).click()
  await page.getByRole('option', { name: /Research Cockpit/ }).click()
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

test('Research Command Center desk drives the cockpit and evidence hub from the backlog', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport command-center gate')
  await preparePage(page)

  await page.getByLabel('DESK').selectOption('research')
  await expect(page.getByText('Needs you (1)')).toBeVisible()
  // Both the Evidence Hub and the Codex Bench start honestly empty.
  await expect(page.getByText('NO CASE SELECTED', { exact: true })).toHaveCount(2)

  await page.getByRole('button', { name: new RegExp(RESEARCH_CASE.project_name) }).click()
  await expect(page.getByText('CLOSED', { exact: true }).first()).toBeVisible()

  await expect(page.getByRole('tab', { name: 'Evidence for', exact: true })).toBeVisible()
  // Literature claims render screened vs draft distinctly, claims map before bibliography.
  await page.getByRole('tab', { name: 'Literature', exact: true }).click()
  await expect(page.getByText('SCREENED', { exact: true })).toBeVisible()
  await expect(page.getByText('DRAFT — UNSCREENED', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Falsification', exact: true }).click()
  await expect(page.getByText('Shuffled-label control shows no effect')).toBeVisible()
  await expect(page.getByText('NOT_TESTED', { exact: true }).first()).toBeVisible()
  // Evidence against renders with the same component and prominence as evidence for.
  await page.getByRole('tab', { name: 'Evidence against', exact: true }).click()
  await expect(page.getByText(/No typed findings of this direction exist yet/)).toBeVisible()

  // The Codex Bench shows every recorded packet and fences commentary as never-evidence.
  await expect(page.getByText('MCP-ATTACHED · NO CHAT · NO API KEY', { exact: true })).toBeVisible()
  await expect(page.getByText(/RECORDING HAPPENS ON THE GOVERNED SEAMS/)).toBeVisible()
  await expect(page.getByText('CODEX COMMENTARY — NOT EVIDENCE', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /cp_f+/ }).click()
  await expect(page.getByText('"packet_schema": "ResearchContextPacketV1"')).toBeVisible()

  // The Research Data tab serves registered refs with audit badges and the forever badge.
  await page.getByRole('tab', { name: 'Research Data', exact: true }).click()
  await expect(page.getByText('1 LIMITING', { exact: true })).toBeVisible()
  await expect(page.getByText('RESEARCH ONLY', { exact: true })).toBeVisible()
  await expect(page.getByText(/snapshot snap1 · manifest/)).toBeVisible()
  await expectReleaseAccessibility(page)
})

test('New Idea opens natural-language capture with zero trading-rule inputs', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport new-idea gate')
  await preparePage(page)

  await page.getByRole('button', { name: 'New Idea' }).click()
  await expect(page.getByLabel('DESK')).toHaveValue('research')
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

test('running jobs expose exact runtime, bounded ETA, progress, and live output', async (
  { page },
  testInfo,
) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport job progress gate')
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
  await page.getByLabel('DESK').selectOption('operations')

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

test('ML desk renders bounded Qlib diagnostics and the permanent authority warning', async (
  { page },
  testInfo,
) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport projection gate')
  await preparePage(page, { mlDiagnostics: true })
  await page.getByLabel('DESK').selectOption('ml')

  await expect(page.locator('.rd-head').filter({ hasText: 'Score distribution' })).toBeVisible()
  await expect(page.locator('.rd-head').filter({ hasText: 'IC / RankIC timeline' })).toBeVisible()
  await expect(page.locator('.rd-head').filter({ hasText: 'Feature importance' })).toBeVisible()
  await expect(page.getByText(/MODEL NOT RECOMPUTED UNDER COUNTERFACTUAL/i).first()).toBeVisible()
  await expect(page.getByText('0.9.7', { exact: true })).toBeVisible()
  await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
  await expectReleaseAccessibility(page)
})

test('causal chart paginates evidence, exports exact OHLCV, and links keyboard trade selection', async (
  { page },
  testInfo,
) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport interaction gate')
  await preparePage(page, { chartBundle: causalChartBundle(), trades: CAUSAL_TRADES })
  await page.locator('.research-context-summary').click()
  await page.getByPlaceholder('run id').fill(HEAVY_RUN_ID)
  await page.getByRole('button', { name: 'done' }).click()

  await expect(page.getByText('205 bars', { exact: true })).toBeVisible()
  await expect(page.getByText(/1–80 \/ 91 RETURNED EVENTS/)).toBeVisible()
  await expect(page.getByText(/BACKEND PROJECTION TRUNCATED · MORE TRACE EVENTS EXIST/)).toBeVisible()
  await page.getByRole('button', { name: 'Next trace page' }).click()
  await expect(page.getByText(/81–91 \/ 91 RETURNED EVENTS/)).toBeVisible()

  const tradeRow = page.locator('tr.trade-row').filter({ hasText: 'AAPL.SIM' })
  await tradeRow.click()
  await expect(page.getByText('trade · #91', { exact: true })).toBeVisible()
  await expect(tradeRow).toHaveClass(/selected/)
  await page.locator('button.trace-event').filter({ hasText: '0091' }).click()
  await expect(page.getByText('trade · #91', { exact: true })).toBeVisible()
  await expect(tradeRow).toHaveClass(/selected/)

  await page.getByRole('button', { name: 'Previous trace page' }).click()
  await page.locator('button.trace-event').first().click()
  await expect(tradeRow).not.toHaveClass(/selected/)
  await tradeRow.focus()
  await page.keyboard.press('Enter')
  await expect(tradeRow).toHaveClass(/selected/)
  await expect(page.getByText('trade · #91', { exact: true })).toBeVisible()

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

test('dense causal chart layers cap visuals without hiding returned evidence', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport interaction gate')
  await preparePage(page, { chartBundle: denseCausalChartBundle() })
  await page.locator('.research-context-summary').click()
  await page.getByPlaceholder('run id').fill(HEAVY_RUN_ID)
  await page.getByRole('button', { name: 'done' }).click()

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

test('inactive Dockview tabs do not start their data requests', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport request gate')
  const requested: string[] = []
  page.on('request', (request) => requested.push(new URL(request.url()).pathname))
  await preparePage(page)

  expect(requested).not.toContain('/api/runs')
  expect(requested).not.toContain('/api/screener/quote')
  expect(requested).not.toContain('/api/screener/news')
  await page.getByRole('tab', { name: 'Runs', exact: true }).click()
  await expect.poll(() => requested.filter((path) => path === '/api/runs').length).toBe(1)
})

test('legacy trace rerun opens the governed Development Center', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport governance gate')
  await preparePage(page, { chartBundle: causalChartBundle(false) })
  await page.locator('.research-context-summary').click()
  await page.getByPlaceholder('run id').fill(HEAVY_RUN_ID)
  await page.getByRole('button', { name: 'done' }).click()

  await expect(page.getByText('TRACE UNAVAILABLE', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Rerun for causal trace' }).click()
  await expect(page.getByText('Development Center', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/panel crashed/i)).toHaveCount(0)
})

test('cold shell and cached desk switch meet workstation latency budgets', async (
  { page },
  testInfo,
) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport performance gate')
  await preparePage(page)

  const coldShellMs = await page.evaluate(() => performance.now())
  expect(coldShellMs).toBeLessThan(1_500)

  const switchMs = await page.evaluate(async () => {
    const select = document.querySelector<HTMLSelectElement>('.desk-control select')
    if (!select) throw new Error('desk selector is unavailable')
    const started = performance.now()
    select.value = 'development'
    select.dispatchEvent(new Event('change', { bubbles: true }))
    for (let frame = 0; frame < 12; frame += 1) {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
      if (document.body.textContent?.includes('Development Center')) {
        return performance.now() - started
      }
    }
    throw new Error('development desk did not render within 12 animation frames')
  })
  expect(switchMs).toBeLessThan(100)
})

test('25k bars and 200 annotations remain interactively responsive', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-reference', 'reference viewport performance gate')
  test.setTimeout(45_000)
  const bundle = heavyChartBundle()
  await preparePage(page, { chartBundle: bundle })

  const renderStarted = Date.now()
  await page.locator('.research-context-summary').click()
  await page.getByPlaceholder('run id').fill(HEAVY_RUN_ID)
  await page.getByRole('button', { name: 'done' }).click()

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
