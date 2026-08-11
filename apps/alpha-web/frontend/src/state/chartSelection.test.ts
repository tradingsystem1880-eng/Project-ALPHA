import { beforeEach, describe, expect, it } from 'vitest'

import type { ChartTraceEvent, TradeRow } from '../api/types'
import {
  clearChartSelection,
  getChartSelection,
  matchingTradeTrace,
  matchingTraceSequence,
  selectTraceEvent,
  selectTradeRow,
  selectionMatchesTrade,
} from './chartSelection'

const trade: TradeRow = {
  instrument_id: 'AAPL.SIM',
  entry_ts: '2026-01-05T00:00:00Z',
  exit_ts: '2026-01-09T00:00:00Z',
}

const traceTrade = {
  sequence_id: 44,
  event_type: 'trade',
  instrument_id: 'AAPL.SIM',
  entry_ts: Date.parse(String(trade.entry_ts)) / 1_000,
  exit_ts: Date.parse(String(trade.exit_ts)) / 1_000,
} as ChartTraceEvent

describe('run-scoped chart selection', () => {
  beforeEach(clearChartSelection)

  it('maps a trade-table selection to the immutable trace sequence', () => {
    selectTradeRow('run-a', trade)
    const selection = getChartSelection()
    expect(selectionMatchesTrade(selection, 'run-a', trade)).toBe(true)
    expect(selectionMatchesTrade(selection, 'run-b', trade)).toBe(false)
    expect(matchingTraceSequence(selection, 'run-a', [traceTrade])).toBe(44)
  })

  it('maps a chart marker back to the matching trade row', () => {
    selectTraceEvent('run-a', traceTrade)
    const selection = getChartSelection()
    expect(selection?.sequenceId).toBe(44)
    expect(selectionMatchesTrade(selection, 'run-a', trade)).toBe(true)
    expect(matchingTraceSequence(selection, 'run-a', [traceTrade])).toBe(44)
  })

  it('keeps the selected causal event while resolving its descendant fill to a trade row', () => {
    const decision = {
      ...traceTrade,
      sequence_id: 1,
      event_type: 'decision',
      parent_sequence_id: null,
      entry_ts: null,
      exit_ts: null,
    } as ChartTraceEvent
    const order = {
      ...decision,
      sequence_id: 2,
      event_type: 'order',
      parent_sequence_id: 1,
    } as ChartTraceEvent
    const fill = {
      ...decision,
      sequence_id: 3,
      event_type: 'fill',
      parent_sequence_id: 2,
      ts: traceTrade.entry_ts!,
    } as ChartTraceEvent
    const linkedTrade = {
      ...traceTrade,
      parent_sequence_id: 9,
    } as ChartTraceEvent
    const trace = [decision, order, fill, linkedTrade]

    expect(matchingTradeTrace(decision, trace)?.sequence_id).toBe(44)
    selectTraceEvent('run-a', decision, trace)

    const selection = getChartSelection()
    expect(selection?.sequenceId).toBe(1)
    expect(selectionMatchesTrade(selection, 'run-a', trade)).toBe(true)
  })
})
