// Enumerated-state → chip-class mapping shared by every research surface.
// States are the scorecard/card/finding vocabularies — never numeric scores.

const GOOD_STATES = new Set([
  'complete',
  'supported',
  'strong',
  'passed',
  'plausible',
  'adequate',
  'meaningful',
  'low',
  'supporting',
])

const BAD_STATES = new Set([
  'missing',
  'unsupported',
  'failed',
  'weak',
  'high',
  'negligible',
  'contradictory',
  'blocked',
])

export function stateChipClass(state: string): string {
  if (GOOD_STATES.has(state)) return 'chip pass'
  if (BAD_STATES.has(state)) return 'chip fail'
  return 'chip'
}

// Typed finding statuses (the D1/D2 vocabulary) are uppercase; TESTED, INCONCLUSIVE, and
// NOT_TESTED stay neutral — an exploratory result is not a pass.
const GOOD_FINDINGS = new Set(['SUPPORTED', 'PASSED', 'STABLE', 'CLEARS_HURDLE'])

const BAD_FINDINGS = new Set(['CONTRADICTED', 'FAILED', 'UNSTABLE', 'BELOW_HURDLE', 'INVALID'])

export function findingChipClass(status: string): string {
  if (GOOD_FINDINGS.has(status)) return 'chip pass'
  if (BAD_FINDINGS.has(status)) return 'chip fail'
  return 'chip'
}
