import { describe, expect, it } from 'vitest'
import { replaceIndicator, readFavorites } from './indicatorPickerModel'

describe('indicator editing', () => {
  it('replaces specs without changing patterns or duplicating a series', () => {
    expect(replaceIndicator({ indicators: ['sma:20', 'sma:50'], patterns: ['swings'] }, 'sma:20', 'sma:50')).toEqual({ indicators: ['sma:50'], patterns: ['swings'] })
  })
  it('rejects invalid parameters', () => {
    expect(() => replaceIndicator({ indicators: ['macd:12:26:9'], patterns: [] }, 'macd:12:26:9', 'macd:30:20:9')).toThrow('fast window')
  })
  it('drops invalid saved favourites', () => {
    expect(readFavorites(['ema:100', 'nonsense', 'ema:100', 3])).toEqual(['ema:100'])
    expect(readFavorites(null)).toEqual([])
  })
})
