/**
 * The canvas token mirror must not drift from the figure theme.
 *
 * Python renders figures from `alpha_dark.json`; the SPA styles the page from CSS custom
 * properties and mirrors them here for canvas-land, which cannot read CSS variables. Three
 * copies of one palette is two chances to disagree, and a disagreement shows up as a figure
 * that does not match the panel it sits in.
 *
 * The stylesheet half of this guard lives in `tests/unit/test_theme_drift.py`: Vitest stubs
 * CSS imports, so the stylesheet is not readable from here, and Python can read both files
 * with no bundler involved.
 */

import { describe, expect, it } from 'vitest'

import themeDocument from '../../../../../packages/alpha-research/src/alpha_research/figures/themes/alpha_dark.json'
import { FALLBACK } from './tokens'

const theme = themeDocument as unknown as Record<string, string>

/** Only what canvas-land actually draws with; surfaces are CSS-only. */
const MIRRORED = ['line', 'grid', 'ink', 'muted', 'accent', 'up', 'down', 'gold'] as const

describe('canvas tokens mirror the figure theme', () => {
  it.each(MIRRORED)('%s matches', (name) => {
    const mirror = FALLBACK as unknown as Record<string, string>
    expect(mirror[name]?.toLowerCase()).toBe(theme[name])
  })

  it('maps dim onto the theme ink_dim', () => {
    expect(FALLBACK.dim.toLowerCase()).toBe(theme.ink_dim)
  })

  it('reserves the substrate colour for figures only', () => {
    // Price sits behind the finding; it must stay distinct from the accent it recedes against.
    expect(theme.substrate).toBeDefined()
    expect(theme.substrate).not.toBe(theme.accent)
    expect(Object.values(FALLBACK)).not.toContain(theme.substrate)
  })
})
