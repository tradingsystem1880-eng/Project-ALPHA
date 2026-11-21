import { describe, expect, it } from 'vitest'

import { sourceTag } from './sourceTagModel'

describe('source tag', () => {
  it('says plain words, in a neutral tone, for bars stored before identity was recorded', () => {
    const tag = sourceTag({ source: 'yfinance', venue: null, timeframe: '1D', quality_status: 'legacy_unqualified' })
    expect(tag.text).toBe('Yahoo daily bars · identity not recorded')
    expect(tag.tone).toBe('kind')
    expect(tag.title).toContain('alpha data pull')
  })

  it('shows the venue and quality for qualified bars', () => {
    expect(sourceTag({ source: 'tiingo', venue: 'NYSE', timeframe: '1D', quality_status: 'owner_approved' }).text)
      .toBe('Tiingo daily bars · NYSE · owner approved')
  })
})
