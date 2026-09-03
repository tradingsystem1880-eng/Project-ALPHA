// Runtime bridge from CSS custom properties to canvas-land (uPlot / lightweight-charts cannot
// read CSS vars). Charts are canvas surfaces, so they read the generated `--canvas-*` tokens
// (mirrors of the figure theme), never the light chrome palette. The hardcoded fallbacks keep
// pure-node tests (vitest, no DOM) working and are drift-tested against the theme document.

export interface ChartTokens {
  bg: string
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
}

export const FALLBACK: ChartTokens = {
  bg: '#000000',
  ink: '#e0e0e0',
  dim: '#c8c8c8',
  muted: '#c8c8c8',
  grid: '#2a2a2a',
  line: '#e0e0e0',
  accent: '#316ac5',
  up: '#2fc36a',
  down: '#e5484d',
  gold: '#ffd400',
  band: 'rgba(49, 106, 197, 0.14)',
  font: '11px Verdana, Tahoma, "DejaVu Sans", sans-serif',
}

/** `#rrggbb` → `rgba(...)` at the given alpha — canvas/SVG shades derive from the tokens
 *  instead of re-hardcoding rgba literals (non-hex inputs pass through unchanged). */
export function withAlpha(color: string, alpha: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(color.trim())
  if (!m) return color
  const n = parseInt(m[1], 16)
  return `rgba(${(n >> 16) & 0xff}, ${(n >> 8) & 0xff}, ${n & 0xff}, ${alpha})`
}

let cached: ChartTokens | null = null

function cssVar(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  const v = styles.getPropertyValue(name).trim()
  return v || fallback
}

/** Read the canvas tokens from the live stylesheet (cached after first call). */
export function readTokens(): ChartTokens {
  if (cached) return cached
  if (typeof document === 'undefined') return FALLBACK
  const s = getComputedStyle(document.documentElement)
  const accent = cssVar(s, '--canvas-accent', FALLBACK.accent)
  cached = {
    bg: cssVar(s, '--canvas-bg', FALLBACK.bg),
    ink: cssVar(s, '--canvas-ink', FALLBACK.ink),
    dim: cssVar(s, '--canvas-ink-dim', FALLBACK.dim),
    muted: cssVar(s, '--canvas-muted', FALLBACK.muted),
    grid: cssVar(s, '--canvas-grid', FALLBACK.grid),
    line: cssVar(s, '--canvas-line', FALLBACK.line),
    accent,
    up: cssVar(s, '--canvas-up', FALLBACK.up),
    down: cssVar(s, '--canvas-down', FALLBACK.down),
    gold: cssVar(s, '--canvas-gold', FALLBACK.gold),
    band: withAlpha(accent, 0.14),
    font: cssVar(s, '--canvas-font', FALLBACK.font),
  }
  return cached
}
