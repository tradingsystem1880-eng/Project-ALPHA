// Chart colors, kept in lockstep with the CSS tokens in index.css (canvas can't read CSS vars).

export const CHART = {
  ink: '#e8ecf3',
  dim: '#aab3c4',
  muted: '#737d90',
  grid: '#1a212d',
  line: '#1d2431',
  accent: '#4f8dff',
  up: '#2ea04a',
  down: '#ef5350',
  gold: '#d7a63b',
  band: 'rgba(79, 141, 255, 0.14)',
  font: '11px "JetBrains Mono", ui-monospace, monospace',
} as const

// Shared uPlot axis style (spread into per-axis configs, e.g. `{ ...AXIS, scale: 'y' }`).
export const AXIS = {
  stroke: CHART.muted,
  font: CHART.font,
  grid: { stroke: CHART.grid, width: 1 },
  ticks: { stroke: CHART.grid, width: 1 },
}
