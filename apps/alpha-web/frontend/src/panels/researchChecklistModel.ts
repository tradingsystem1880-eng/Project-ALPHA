// TypeScript twin of `alpha_cli.research_gate_packet.derive_research_checklist` (spec §10.1).
// Change a question binding or answer string there -> change it here; the committed fixture
// `__fixtures__/researchChecklist.json` is asserted by BOTH pytest and vitest, so a
// one-sided edit fails one of the suites (the bands.ts <-> verdict.py pattern).

import type { ResearchScorecardInputs } from './researchScorecardModel'

export const CHECKLIST_QUESTION_IDS = [
  'effect_exists',
  'practical_magnitude',
  'temporal_stability',
  'sample_breadth',
  'transportability',
  'regime_dependence',
  'parameter_neighborhood',
  'falsification',
  'data_artifact',
  'leakage',
  'mechanism',
  'economic_hurdle',
  'observation_count',
  'residual_uncertainty',
] as const

export type ChecklistQuestionId = typeof CHECKLIST_QUESTION_IDS[number]

export interface ResearchChecklistQuestionRow {
  question_id: ChecklistQuestionId
  number: number
  question: string
  binding: string
  status: string
  answer: string
}

export interface ResearchChecklistResult {
  checklist_schema: 'ResearchEdgeChecklistV1'
  questions: ResearchChecklistQuestionRow[]
}

function question(
  questionId: ChecklistQuestionId,
  number: number,
  text: string,
  binding: string,
  status: string,
  answer: string,
): ResearchChecklistQuestionRow {
  return { question_id: questionId, number, question: text, binding, status, answer }
}

export function deriveResearchChecklist(
  inputs: ResearchScorecardInputs,
): ResearchChecklistResult {
  const classification = inputs.confirmation_classification || null
  const primaryStatus = inputs.primary_result_status
  const magnitude = inputs.practical_magnitude_status
  const power = inputs.power_status
  const negativeControls = inputs.negative_controls_status
  const mechanism = inputs.mechanism_status
  const parameter = inputs.stability_parameter_status
  const temporal = inputs.stability_temporal_status
  const transport = inputs.stability_transportability_status
  const datasetCount = inputs.registered_dataset_count
  const auditedCount = inputs.audited_dataset_count ?? 0
  const auditBlocking = inputs.audit_blocking_count ?? 0
  const auditLimiting = inputs.audit_limiting_count ?? 0
  const supportingClaims = inputs.screened_supporting_count ?? 0
  const contradictingClaims = inputs.screened_contradicting_count ?? 0

  let effectStatus: string
  let effectAnswer: string
  if (classification !== null) {
    effectStatus = classification
    effectAnswer = `Sealed confirmation classified the registered claim ${classification}.`
  } else if (primaryStatus === 'TESTED') {
    effectStatus = 'TESTED'
    effectAnswer = 'An exploratory primary result exists; the sealed confirmation has not run.'
  } else {
    effectStatus = 'NOT_TESTED'
    effectAnswer = 'No primary-result evidence has been recorded.'
  }

  const magnitudeAnswers: Record<string, string> = {
    CLEARS_HURDLE: 'The recorded magnitude clears the registered minimum effect.',
    BELOW_HURDLE: 'The recorded magnitude is below the registered minimum effect.',
    NOT_TESTED: 'No practical-magnitude evidence exists.',
  }
  let breadthAnswer: string
  if (power === 'PASSED') {
    breadthAnswer = 'The effective event clusters support the interval beyond one small sample.'
  } else if (power === 'NOT_TESTED') {
    breadthAnswer = 'No effective-sample evidence has been recorded.'
  } else {
    breadthAnswer = `The recorded power finding is ${power}.`
  }
  const falsificationAnswers: Record<string, string> = {
    PASSED: 'Registered negative controls passed.',
    FAILED: 'Registered negative controls failed.',
    NOT_TESTED: 'The registered falsifiers have not run.',
  }
  let artifactStatus: string
  let artifactAnswer: string
  if (datasetCount === 0 || auditedCount === 0) {
    artifactStatus = 'NOT_TESTED'
    artifactAnswer = 'No registered dataset has been audited.'
  } else if (auditBlocking > 0) {
    artifactStatus = 'FAILED'
    artifactAnswer = `${auditBlocking} blocking data-audit findings.`
  } else if (auditLimiting > 0) {
    artifactStatus = 'INCONCLUSIVE'
    artifactAnswer = `${auditLimiting} limiting data-audit findings.`
  } else {
    artifactStatus = 'PASSED'
    artifactAnswer = 'Every registered dataset audited with no findings.'
  }
  const leakageAnswers: Record<string, string> = {
    PASSED: 'The registered control battery, including the lead-lag leakage screen, passed.',
    FAILED: 'A registered control failed; review the lead-lag leakage screen.',
    NOT_TESTED:
      'The lead-lag leakage screen has not run; look-ahead stays structurally '
      + 'guarded by the point-in-time firewall.',
  }
  let countAnswer: string
  if (power === 'PASSED') {
    countAnswer = 'The effective clusters clear the ten-cluster reliability floor.'
  } else if (power === 'INCONCLUSIVE') {
    countAnswer = 'The effective clusters sit below the ten-cluster reliability floor.'
  } else if (power === 'NOT_TESTED') {
    countAnswer = 'No power evidence has been recorded.'
  } else {
    countAnswer = `The recorded power finding is ${power}.`
  }
  const unresolvedCount =
    inputs.blocking_questions.length + inputs.confounders_unresolved.length
  const untestedCount = inputs.untested_work.length

  const questions: ResearchChecklistQuestionRow[] = [
    question('effect_exists', 1, 'Does the effect exist?', 'primary result', effectStatus,
      effectAnswer),
    question(
      'practical_magnitude',
      2,
      'Is it large enough to matter?',
      'practical magnitude vs registered minimum effect',
      magnitude,
      magnitudeAnswers[magnitude] ?? `The recorded magnitude finding is ${magnitude}.`,
    ),
    question(
      'temporal_stability',
      3,
      'Is it stable through time?',
      'temporal stability',
      temporal,
      `The recorded temporal-stability finding is ${temporal}.`,
    ),
    question(
      'sample_breadth',
      4,
      'Does it exist beyond one small sample?',
      'effective sample and registered subsamples',
      power,
      breadthAnswer,
    ),
    question(
      'transportability',
      5,
      'Does it exist across relevant assets, or only one?',
      'cross-asset transportability',
      transport,
      `The recorded transportability finding is ${transport}.`,
    ),
    question(
      'regime_dependence',
      6,
      'Is it regime-dependent?',
      'regime decomposition',
      'NOT_TESTED',
      'No regime-decomposition evidence exists yet.',
    ),
    question(
      'parameter_neighborhood',
      7,
      'Does it survive alternative definitions?',
      'parameter neighborhood',
      parameter,
      `The recorded parameter-neighborhood finding is ${parameter}.`,
    ),
    question(
      'falsification',
      8,
      'Does it survive falsification tests?',
      'placebo, negative controls, and registered nulls',
      negativeControls,
      falsificationAnswers[negativeControls]
        ?? `The negative-control finding is ${negativeControls}.`,
    ),
    question(
      'data_artifact',
      9,
      'Is it likely a data artifact?',
      'data-quality audit findings',
      artifactStatus,
      artifactAnswer,
    ),
    question(
      'leakage',
      10,
      'Is it likely look-ahead or leakage?',
      'future-poison and lead-lag diagnostics',
      negativeControls,
      leakageAnswers[negativeControls]
        ?? `The registered control battery is ${negativeControls}.`,
    ),
    question(
      'mechanism',
      11,
      'Is there a plausible mechanism?',
      'mechanism finding and screened claims',
      mechanism,
      `The recorded mechanism finding is ${mechanism}; ${supportingClaims} supporting `
        + `and ${contradictingClaims} contradicting screened claims.`,
    ),
    question(
      'economic_hurdle',
      12,
      'Could the magnitude survive realistic costs?',
      'economic-hurdle check (last rung)',
      'NOT_TESTED',
      'No economic-hurdle evidence exists; cost realism is the last rung before '
        + 'strategy work.',
    ),
    question(
      'observation_count',
      13,
      'Do we have enough observations?',
      'power and the low-cluster floor',
      power,
      countAnswer,
    ),
    question(
      'residual_uncertainty',
      14,
      'How much uncertainty remains?',
      'intervals and untested work',
      'TESTED',
      `${unresolvedCount} unresolved questions and ${untestedCount} untested `
        + 'workstreams remain.',
    ),
  ]
  return { checklist_schema: 'ResearchEdgeChecklistV1', questions }
}
