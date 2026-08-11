import { describe, expect, it } from 'vitest'

import { runKindMatches } from './runBrowserModel'

describe('runKindMatches', () => {
  it('keeps both portfolio-compatible run families in the curated desk', () => {
    const allowed = ['portfolio', 'cross_sectional']

    expect(runKindMatches('portfolio', 'all', allowed)).toBe(true)
    expect(runKindMatches('cross_sectional', 'all', allowed)).toBe(true)
    expect(runKindMatches('forecast', 'all', allowed)).toBe(false)
  })

  it('applies a selected kind within the allowed set', () => {
    const allowed = ['portfolio', 'cross_sectional']

    expect(runKindMatches('portfolio', 'cross_sectional', allowed)).toBe(false)
    expect(runKindMatches('cross_sectional', 'cross_sectional', allowed)).toBe(true)
  })
})
