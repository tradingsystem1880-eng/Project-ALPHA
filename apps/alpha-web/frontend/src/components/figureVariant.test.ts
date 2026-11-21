import { describe, expect, it } from 'vitest'

import { explanationSentences, otherVariant, toggleLabel, variantFileName } from './figureVariant'

describe('figure variants', () => {
  it('toggles between the plain chart and the annotated chart', () => {
    expect(otherVariant('plain')).toBe('annotated')
    expect(otherVariant('annotated')).toBe('plain')
  })

  it('names what the toggle shows next', () => {
    expect(toggleLabel('plain')).toBe('Show annotated')
    expect(toggleLabel('annotated')).toBe('Show plain chart')
  })

  it('keeps the sentences of the explanation in order and drops blanks', () => {
    expect(explanationSentences([' One. ', '', 'Two.', '   '])).toEqual(['One.', 'Two.'])
    expect(explanationSentences(undefined)).toEqual([])
  })

  it('puts the variant in the saved file name', () => {
    expect(variantFileName('equity_underwater', 'annotated', 'png')).toBe('equity_underwater.annotated.png')
  })
})
