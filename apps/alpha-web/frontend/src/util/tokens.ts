// Runtime bridge from CSS custom properties to canvas-land (uPlot / lightweight-charts cannot
// read CSS vars). Single source of truth stays in index.css; this reads the computed values
// once and caches them. The hardcoded fallbacks keep pure-node tests (vitest, no DOM) working.

export interface ChartTokens {
  ink: string
  dim: string
  muted: string
  grid: string
  line: string
  accent: string
  up: string
  down: string
  gold: string
  band: string
  font: string
  verdict: Record<'A' | 'B' | 'C' | 'D' | 'F', string>
}

const FALLBACK: ChartTokens = {
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
  font: '11px "JetBrains Mono Variable", ui-monospace, monospace',
  verdict: { A: '#2ea04a', B: '#7cb342', C: '#d7a63b', D: '#e07b39', F: '#ef5350' },
}

let cached: ChartTokens | null = null

function cssVar(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  const v = styles.getPropertyValue(name).trim()
  return v || fallback
}

/** Read the chart color tokens from the live stylesheet (cached after first call). */
export function readTokens(): ChartTokens {
  if (cached) return cached
  if (typeof document === 'undefined') return FALLBACK
  const s = getComputedStyle(document.documentElement)
  cached = {
    ink: cssVar(s, '--ink', FALLBACK.ink),
    dim: cssVar(s, '--ink-dim', FALLBACK.dim),
    muted: cssVar(s, '--muted', FALLBACK.muted),
    grid: FALLBACK.grid,
    line: cssVar(s, '--line', FALLBACK.line),
    accent: cssVar(s, '--accent', FALLBACK.accent),
    up: cssVar(s, '--up', FALLBACK.up),
    down: cssVar(s, '--down', FALLBACK.down),
    gold: cssVar(s, '--gold', FALLBACK.gold),
    band: cssVar(s, '--accent-soft', FALLBACK.band),
    font: FALLBACK.font,
    verdict: {
      A: cssVar(s, '--verdict-a', FALLBACK.verdict.A),
      B: cssVar(s, '--verdict-b', FALLBACK.verdict.B),
      C: cssVar(s, '--verdict-c', FALLBACK.verdict.C),
      D: cssVar(s, '--verdict-d', FALLBACK.verdict.D),
      F: cssVar(s, '--verdict-f', FALLBACK.verdict.F),
    },
  }
  return cached
}
