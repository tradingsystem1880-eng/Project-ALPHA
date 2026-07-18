// Chart colors for canvas-land, sourced from the CSS tokens at runtime via util/tokens.ts
// (single source of truth in index.css; the fallbacks there match these values byte-for-byte,
// so a pre-CSS read in dev degrades to identical colors).

import { readTokens } from './tokens'

const T = readTokens()

export const CHART = {
  ink: T.ink,
  dim: T.dim,
  muted: T.muted,
  grid: T.grid,
  line: T.line,
  accent: T.accent,
  up: T.up,
  down: T.down,
  gold: T.gold,
  band: T.band,
  font: T.font,
} as const

// Shared uPlot axis style (spread into per-axis configs, e.g. `{ ...AXIS, scale: 'y' }`).
export const AXIS = {
  stroke: CHART.muted,
  font: CHART.font,
  grid: { stroke: CHART.grid, width: 1 },
  ticks: { stroke: CHART.grid, width: 1 },
}
