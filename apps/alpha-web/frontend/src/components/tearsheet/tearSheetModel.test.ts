import { describe, expect, it } from 'vitest'
import type { RunSeries } from '../../api/types'
import { ariaSummary, bandSpans, buildStack, heldSpans, inMarket, priceReason, readoutAt } from './tearSheetModel'

const DAY = 86400
const T0 = Date.UTC(2020, 0, 1) / 1000

function series(over: Partial<RunSeries> = {}): RunSeries {
  return {
    run_id: 'abcd00000000beef',
    ts: [0, 1, 2, 3, 4].map(i => T0 + i * DAY),
    equity: [1, 1.1, 1.2, 0.9, 1],
    drawdown: [0, 0, 0, -0.25, -1 / 6],
    benchmark: [null, 1, 1.02, 1.04, 1.06],
    exposure: null,
    trades: [{ entry_ts: T0 + DAY, exit_ts: T0 + 3 * DAY, side: 'long', entry_price: 101, exit_price: 103, realized_return: 0.0198 }],
    bands: {
      tradable: { first_ts: '2020-01-02T00:00:00+00:00', last_ts: '2020-01-05T00:00:00+00:00' },
      scored: { first_ts: '2020-01-03T00:00:00+00:00', last_ts: '2020-01-05T00:00:00+00:00' },
      folds: [{ index: 0, start_ts: '2020-01-03T00:00:00+00:00', end_ts: '2020-01-04T00:00:00+00:00' }],
    },
    price: { status: 'available', ts: [0, 1, 2, 3, 4].map(i => T0 + i * DAY), close: [100, 101, 102, 103, 104] },
    bounds: { points: { original: 5, returned: 5, truncated: false, sampling: 'all' }, trades: { original: 1, returned: 1, truncated: false, cap: 2000 } },
    provenance: { artifact_sha256: {} },
    ...over,
  }
}

describe('inMarket', () => {
  it('is yes from the entry day up to the exit day', () => {
    const { trades } = series()
    expect(inMarket(trades, T0)).toBe(false)
    expect(inMarket(trades, T0 + DAY)).toBe(true)
    expect(inMarket(trades, T0 + 2 * DAY)).toBe(true)
    expect(inMarket(trades, T0 + 3 * DAY)).toBe(false)
  })
})

describe('readoutAt', () => {
  it('reads the stored values at the nearest day', () => {
    const r = readoutAt(series(), T0 + 3 * DAY + 100)
    expect(r.date).toBe('2020-01-04')
    expect(r.close).toBe(103)
    expect(r.equity).toBe(0.9)
    expect(r.benchmark).toBe(1.04)
    expect(r.drawdown).toBe(-0.25)
    expect(r.inMarket).toBe(false)
  })
  it('keeps a missing benchmark and a missing price as null', () => {
    const r = readoutAt(series({ price: { status: 'bars_changed_since_run', ts: [], close: [] } }), T0)
    expect(r.benchmark).toBeNull()
    expect(r.close).toBeNull()
  })
  it('says yes inside a held trade', () => {
    expect(readoutAt(series(), T0 + DAY).inMarket).toBe(true)
  })
})

describe('buildStack', () => {
  it('converts seconds to milliseconds and drops missing benchmark points', () => {
    const stack = buildStack(series(), false)
    expect(stack.equity.x[0]).toBe(T0 * 1000)
    expect(stack.benchmark?.x).toHaveLength(4)
    expect(stack.drawdown.y).toEqual([0, 0, 0, -0.25, -1 / 6])
    expect(stack.price?.close).toHaveLength(5)
  })
  it('keeps the stored equity values on a log axis and marks the axis type', () => {
    const stack = buildStack(series(), true)
    expect(stack.equity.y).toEqual([1, 1.1, 1.2, 0.9, 1])
    expect(stack.logScale).toBe(true)
  })
  it('has no price pane when price is not available', () => {
    expect(buildStack(series({ price: { status: 'price_not_saved_with_run', ts: [], close: [] } }), false).price).toBeNull()
    expect(buildStack(series({ price: null }), false).price).toBeNull()
  })
  it('puts entry and exit markers on the stored prices at the stored times', () => {
    const stack = buildStack(series(), false)
    expect(stack.entries).toEqual({ x: [(T0 + DAY) * 1000], y: [101] })
    expect(stack.exits).toEqual({ x: [(T0 + 3 * DAY) * 1000], y: [103] })
  })
  it('does not draw a log axis for equity that is not positive', () => {
    expect(buildStack(series({ equity: [1, 0, 1, 1, 1] }), true).logScale).toBe(false)
  })
})

describe('heldSpans and bandSpans', () => {
  it('shades each trade from entry to exit', () => {
    expect(heldSpans(series().trades)).toEqual([{ from: (T0 + DAY) * 1000, to: (T0 + 3 * DAY) * 1000 }])
  })
  it('labels tested periods and folds in plain words', () => {
    const spans = bandSpans(series().bands)
    expect(spans.map(s => s.label)).toEqual(['Period the rule could trade', 'Scored test period', 'Walk-forward test 1'])
    expect(spans[0].from).toBe(Date.UTC(2020, 0, 2))
    expect(spans[2].to).toBe(Date.UTC(2020, 0, 4))
  })
  it('skips a band with no stored dates', () => {
    expect(bandSpans({ tradable: null, scored: null, folds: [] })).toEqual([])
  })
})

describe('priceReason', () => {
  it('gives a plain reason for each refusal', () => {
    expect(priceReason('bars_changed_since_run')).toMatch(/changed since this run/)
    expect(priceReason('price_not_saved_with_run')).toMatch(/did not record/)
    expect(priceReason('price_unavailable')).toMatch(/could not be read/)
    expect(priceReason('snapshot_unavailable')).toMatch(/not saved/)
    expect(priceReason('available')).toBeNull()
  })
})

describe('ariaSummary', () => {
  it('states the same facts the panes show', () => {
    const text = ariaSummary(series())
    expect(text).toContain('5 days')
    expect(text).toContain('2020-01-01')
    expect(text).toContain('1 trade')
    expect(text).toContain('deepest drawdown shown -25.0%')
    expect(text).toContain('walk-forward')
  })
  it('names why price is missing', () => {
    expect(ariaSummary(series({ price: null }))).toContain('price pane not shown')
  })
})
