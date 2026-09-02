import { describe, expect, it } from 'vitest'

import { TIMEFRAMES, timeframeButtons, venueLabel, windowTitle } from './toolbarModel'

describe('toolbarModel', () => {
  it('shows the five classic timeframes in order and disables what the data house lacks', () => {
    expect([...TIMEFRAMES]).toEqual(['M15', 'H1', 'H4', 'D1', 'W1'])
    const buttons = timeframeButtons(['D1'])
    expect(buttons.map((item) => item.label)).toEqual(['M15', 'H1', 'H4', 'D1', 'W1'])
    expect(buttons.find((item) => item.label === 'D1')).toEqual({ label: 'D1', disabled: false, reason: null })
    for (const item of buttons.filter((button) => button.label !== 'D1')) {
      expect(item.disabled).toBe(true)
      expect(item.reason).toBe('daily data only')
    }
  })

  it('titles the window from the profile and the active context', () => {
    expect(windowTitle('crypto', { symbol: 'BTC/USDT', venue: 'Binance', timeframe: 'D1' })).toBe(
      'ALPHA Terminal — Crypto — [BTC/USDT · Binance · D1]',
    )
    expect(windowTitle('equities', { symbol: 'AAPL', venue: null, timeframe: 'D1' })).toBe(
      'ALPHA Terminal — Equities — [AAPL · D1]',
    )
    expect(windowTitle('equities', null)).toBe('ALPHA Terminal — Equities')
    expect(windowTitle('crypto', { symbol: null, venue: 'Binance', timeframe: 'D1' })).toBe(
      'ALPHA Terminal — Crypto',
    )
  })

  it('reads the venue from the profile manifest', () => {
    expect(venueLabel('crypto')).toBe('Binance')
    expect(venueLabel('equities')).toBeNull()
  })
})
