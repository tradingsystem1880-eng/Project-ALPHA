import type { EvidenceLevel } from './types'

// Order matters: it is the confidence ladder from the Atlas schema.
export const LEVELS: readonly EvidenceLevel[] = [
  'unknown',
  'declared',
  'implemented',
  'connected',
  'tested',
  'observed',
]

const COLORS: Record<EvidenceLevel, string> = {
  unknown: '#8a93a6',
  declared: '#6f7ff2',
  implemented: '#d9a03f',
  connected: '#3fb8c9',
  tested: '#4cc38a',
  observed: '#b07ff2',
}

const HINTS: Record<EvidenceLevel, string> = {
  unknown: 'discovered, but nothing anchors it — review queue',
  declared: 'documented only; no verified code anchor',
  implemented: 'code exists and is anchored by documentation',
  connected: 'wired into a cross-layer chain',
  tested: 'at least one test validates it',
  observed: 'proven by runtime traces (reserved, Phase 7)',
}

export function levelColor(level: EvidenceLevel): string {
  return COLORS[level]
}

export function levelHint(level: EvidenceLevel): string {
  return HINTS[level]
}
