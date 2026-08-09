// TypeScript twin of `alpha_cli.research_gate_packet.derive_research_scorecard`.
// Change a state table or basis string there -> change it here; the committed fixture
// `__fixtures__/researchScorecard.json` is asserted by BOTH pytest and vitest, so a
// one-sided edit fails one of the suites (the bands.ts <-> verdict.py pattern).

export const SCORECARD_DIMENSION_IDS = [
  'hypothesis_definition',
  'data_quality',
  'sample_adequacy',
  'effect_existence',
  'effect_size',
  'temporal_stability',
  'cross_asset_stability',
  'regime_robustness',
  'falsification',
  'mechanism',
  'literature',
  'data_mining_risk',
] as const

export type ScorecardDimensionId = typeof SCORECARD_DIMENSION_IDS[number]

export interface ResearchScorecardInputs {
  inputs_schema: 'ResearchScorecardInputsV1'
  phase: string
  outcome: string | null
  disposition: string | null
  d2_state: string
  hypothesis_complete_fields: number
  hypothesis_partial_fields: number
  hypothesis_total_fields: number
  registered_dataset_count: number
  audited_dataset_count?: number
  audit_blocking_count?: number
  audit_limiting_count?: number
  screened_claim_count: number
  blocking_questions: string[]
  confounders_resolved: string[]
  confounders_unresolved: string[]
  untested_work: string[]
  attempt_count: number
  primary_result_status: string
  practical_magnitude_status: string
  confirmation_classification: string | null
  power_status: string
  negative_controls_status: string
  multiplicity_status: string
  mechanism_status: string
  stability_parameter_status: string
  stability_temporal_status: string
  stability_transportability_status: string
}

export interface ResearchScorecardDimensionRow {
  dimension_id: ScorecardDimensionId
  label: string
  state: string
  basis: string
}

export interface ResearchScorecardResult {
  scorecard_schema: 'ResearchReadinessScorecardV1'
  dimensions: ResearchScorecardDimensionRow[]
  unresolved_questions: { count: number; items: string[] }
  recommendation: { value: string; reasons: string[] }
}

function dimension(
  dimensionId: ScorecardDimensionId,
  label: string,
  state: string,
  basis: string,
): ResearchScorecardDimensionRow {
  return { dimension_id: dimensionId, label, state, basis }
}

function stabilityState(state: string): string {
  if (state === 'STABLE') return 'strong'
  if (state === 'NOT_TESTED') return 'not_tested'
  return state === 'UNSTABLE' ? 'weak' : 'mixed'
}

export function deriveResearchScorecard(
  inputs: ResearchScorecardInputs,
): ResearchScorecardResult {
  const complete = inputs.hypothesis_complete_fields
  const partial = inputs.hypothesis_partial_fields
  const total = inputs.hypothesis_total_fields || 14
  let hypothesisState = 'partial'
  if (complete === total) hypothesisState = 'complete'
  else if (complete + partial === 0) hypothesisState = 'missing'

  const datasetCount = inputs.registered_dataset_count
  const auditedCount = inputs.audited_dataset_count ?? 0
  const auditBlocking = inputs.audit_blocking_count ?? 0
  const auditLimiting = inputs.audit_limiting_count ?? 0
  let dataQualityState = 'not_tested'
  let dataQualityBasis = 'No registered research datasets.'
  if (datasetCount > 0) {
    if (auditBlocking > 0) {
      dataQualityState = 'blocked'
      dataQualityBasis = `${auditBlocking} blocking data-audit findings.`
    } else if (auditedCount === 0) {
      dataQualityState = 'adequate'
      dataQualityBasis = `${datasetCount} registered datasets; not yet audited.`
    } else if (auditLimiting > 0) {
      dataQualityState = 'weak'
      dataQualityBasis = `${auditLimiting} limiting data-audit findings.`
    } else {
      dataQualityState = 'strong'
      dataQualityBasis = 'Every registered dataset audited with no findings.'
    }
  }
  const claimCount = inputs.screened_claim_count
  const classification = inputs.confirmation_classification
  const magnitude = inputs.practical_magnitude_status
  const power = inputs.power_status
  const negativeControls = inputs.negative_controls_status
  const multiplicity = inputs.multiplicity_status
  const mechanism = inputs.mechanism_status
  const temporal = inputs.stability_temporal_status
  const transport = inputs.stability_transportability_status

  let effectExistence: string
  let effectBasis: string
  if (classification === 'SUPPORTED') {
    effectExistence = 'supported'
    effectBasis = 'Sealed confirmation supported the registered claim.'
  } else if (classification === 'CONTRADICTED') {
    effectExistence = 'unsupported'
    effectBasis = 'Sealed confirmation contradicted the registered claim.'
  } else if (classification === 'INCONCLUSIVE' || classification === 'INVALID') {
    effectExistence = 'mixed'
    effectBasis = `Sealed confirmation classified the claim ${classification}.`
  } else if (inputs.primary_result_status === 'TESTED') {
    effectExistence = 'mixed'
    effectBasis = 'Exploratory result only; the sealed confirmation has not run.'
  } else {
    effectExistence = 'not_tested'
    effectBasis = 'No primary-result evidence has been recorded.'
  }

  let effectSize: string
  let sizeBasis: string
  if (magnitude === 'CLEARS_HURDLE') {
    effectSize = 'meaningful'
    sizeBasis = 'Recorded magnitude clears the registered hurdle.'
  } else if (magnitude === 'BELOW_HURDLE') {
    effectSize = 'negligible'
    sizeBasis = 'Recorded magnitude is below the registered hurdle.'
  } else if (magnitude === 'INCONCLUSIVE') {
    effectSize = 'marginal'
    sizeBasis = 'Recorded magnitude is inconclusive at the hurdle.'
  } else {
    effectSize = 'not_tested'
    sizeBasis = 'No practical-magnitude evidence exists.'
  }

  let sampleState: string
  let sampleBasis: string
  if (power === 'PASSED') {
    sampleState = 'adequate'
    sampleBasis = 'The registered power gate passed.'
  } else if (power === 'NOT_TESTED') {
    sampleState = 'not_tested'
    sampleBasis = 'No power evidence has been recorded.'
  } else {
    sampleState = 'weak'
    sampleBasis = `The recorded power finding is ${power}.`
  }

  let falsificationState: string
  let falsificationBasis: string
  if (negativeControls === 'PASSED') {
    falsificationState = 'passed'
    falsificationBasis = 'Registered negative controls passed.'
  } else if (negativeControls === 'FAILED') {
    falsificationState = 'failed'
    falsificationBasis = 'Registered negative controls failed.'
  } else if (negativeControls === 'NOT_TESTED') {
    falsificationState = 'not_tested'
    falsificationBasis = 'The registered falsifiers have not run.'
  } else {
    falsificationState = 'mixed'
    falsificationBasis = `The negative-control finding is ${negativeControls}.`
  }

  let mechanismState: string
  let mechanismBasis: string
  if (mechanism === 'SUPPORTED' || mechanism === 'PASSED' || mechanism === 'OBSERVED') {
    mechanismState = 'plausible'
    mechanismBasis = 'The recorded mechanism finding supports it.'
  } else if (mechanism === 'CONTRADICTED' || mechanism === 'FAILED') {
    mechanismState = 'unsupported'
    mechanismBasis = 'The recorded mechanism finding fails.'
  } else if (mechanism === 'NOT_TESTED') {
    mechanismState = 'not_tested'
    mechanismBasis = 'No mechanism evidence has been recorded.'
  } else {
    mechanismState = 'unclear'
    mechanismBasis = `The mechanism finding is ${mechanism}.`
  }

  let miningState: string
  let miningBasis: string
  if (multiplicity === 'PASSED') {
    miningState = 'low'
    miningBasis = 'Registered multiplicity accounting passed.'
  } else if (multiplicity === 'FAILED') {
    miningState = 'high'
    miningBasis = 'Registered multiplicity accounting failed.'
  } else if (multiplicity === 'NOT_TESTED') {
    miningState = 'low'
    miningBasis =
      'All analysis families are contract-registered; unregistered attempts are impossible.'
  } else {
    miningState = 'medium'
    miningBasis = `The multiplicity finding is ${multiplicity}.`
  }

  const dimensions: ResearchScorecardDimensionRow[] = [
    dimension(
      'hypothesis_definition',
      'Hypothesis definition',
      hypothesisState,
      `${complete} of ${total} hypothesis-card fields are complete.`,
    ),
    dimension('data_quality', 'Data quality', dataQualityState, dataQualityBasis),
    dimension('sample_adequacy', 'Sample adequacy', sampleState, sampleBasis),
    dimension('effect_existence', 'Effect existence', effectExistence, effectBasis),
    dimension('effect_size', 'Effect size', effectSize, sizeBasis),
    dimension(
      'temporal_stability',
      'Temporal stability',
      stabilityState(temporal),
      `The recorded temporal-stability finding is ${temporal}.`,
    ),
    dimension(
      'cross_asset_stability',
      'Cross-asset stability',
      transport === 'STABLE' ? 'strong' : transport === 'NOT_TESTED' ? 'not_tested' : 'mixed',
      `The recorded transportability finding is ${transport}.`,
    ),
    dimension(
      'regime_robustness',
      'Regime robustness',
      'not_tested',
      'No regime-decomposition evidence exists yet.',
    ),
    dimension('falsification', 'Falsification', falsificationState, falsificationBasis),
    dimension('mechanism', 'Mechanism', mechanismState, mechanismBasis),
    dimension(
      'literature',
      'Literature',
      claimCount === 0 ? 'insufficient' : 'mixed',
      claimCount === 0
        ? 'No screened claim-level literature evidence.'
        : `${claimCount} screened claims; directional aggregation pending.`,
    ),
    dimension('data_mining_risk', 'Data-mining risk', miningState, miningBasis),
  ]

  const unresolvedItems = [
    ...inputs.blocking_questions,
    ...inputs.confounders_unresolved.map((item) => `Unresolved confounder: ${item}`),
    ...inputs.untested_work,
  ]

  let recommendation: string
  let reasons: string[]
  if (inputs.outcome === 'CONTRADICTED') {
    recommendation = 'EVIDENCE DOES NOT SUPPORT CONTINUATION'
    reasons = ['Sealed confirmation contradicted the registered claim.']
  } else if (inputs.outcome === 'INVALID') {
    recommendation = 'REFORMULATE HYPOTHESIS'
    reasons = ['The confirmation run was invalid under the registered protocol.']
  } else if (inputs.outcome === 'SUPPORTED') {
    recommendation = 'READY FOR STRATEGY RESEARCH'
    reasons = [
      'Sealed confirmation supported the registered claim at the frozen alpha and '
        + 'minimum effect.',
    ]
  } else if (hypothesisState === 'missing') {
    recommendation = 'REFORMULATE HYPOTHESIS'
    reasons = ['The hypothesis card has no complete or partial fields.']
  } else {
    const untested = dimensions.filter((entry) => entry.state === 'not_tested').length
    recommendation = 'MORE RESEARCH REQUIRED'
    reasons = [
      `${untested} of ${dimensions.length} readiness dimensions are untested.`,
      `${unresolvedItems.length} unresolved questions remain.`,
    ]
  }

  return {
    scorecard_schema: 'ResearchReadinessScorecardV1',
    dimensions,
    unresolved_questions: { count: unresolvedItems.length, items: unresolvedItems },
    recommendation: { value: recommendation, reasons },
  }
}
