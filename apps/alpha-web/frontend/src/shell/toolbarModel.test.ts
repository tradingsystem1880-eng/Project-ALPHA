import { describe, expect, it } from 'vitest'

import { TIMEFRAMES, chartHeader, timeframeButtons, venueLabel, windowTitle } from './toolbarModel'

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

  it('titles the window the artboard way from the profile and the active context', () => {
    expect(windowTitle('crypto', { symbol: 'BTC/USDT', timeframe: 'D1' })).toBe('ALPHA Terminal — Crypto — [BTCUSDT,D1]')
    expect(windowTitle('equities', { symbol: 'AAPL', timeframe: 'D1' })).toBe('ALPHA Terminal — Equities — [AAPL,D1]')
    expect(windowTitle('equities', null)).toBe('ALPHA Terminal — Equities')
    expect(windowTitle('crypto', { symbol: null, timeframe: 'D1' })).toBe('ALPHA Terminal — Crypto')
    // Any other document is titled by its own name — a report by its display name.
    expect(windowTitle('crypto', { symbol: 'BTC/USDT', timeframe: 'D1' }, 'sma D1 — BTC/USDT · run 1a2b3c4d')).toBe(
      'ALPHA Terminal — Crypto — [sma D1 — BTC/USDT · run 1a2b3c4d]',
    )
  })

  it('reads the venue from the profile manifest', () => {
    expect(venueLabel('crypto')).toBe('Binance')
    expect(venueLabel('equities')).toBeNull()
  })

  it('writes the chart document header without inventing a venue or a window', () => {
    expect(chartHeader('BTC/USDT', 'Binance', '2019-01-01', null)).toBe('BTCUSDT,D1 · Binance · 2019-01-01 → latest')
    expect(chartHeader('AAPL', null, null, '2026-06-30')).toBe('AAPL,D1 · start → 2026-06-30')
    expect(chartHeader(null, null, null, null)).toBe('No symbol')
  })
})
