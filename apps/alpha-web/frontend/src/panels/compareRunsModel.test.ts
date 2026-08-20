import { describe, expect, it } from 'vitest'

import { uniqueComparisonMaximum } from './compareRunsModel'

describe('comparison winner semantics', () => {
  it('returns no winner for ties, missing metrics, or a single comparable run', () => {
    expect(uniqueComparisonMaximum([0, 0])).toBeNull()
    expect(uniqueComparisonMaximum([null, null])).toBeNull()
    expect(uniqueComparisonMaximum([0.2, null])).toBeNull()
  })

  it('returns the unique maximum only when two or more runs are comparable', () => {
    expect(uniqueComparisonMaximum([0.1, 0.3, 0.2])).toBe(0.3)
  })
})
