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
