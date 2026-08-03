// Run-scoped causal selection shared by independently docked chart and trade-table panels.

import { useSyncExternalStore } from 'react'

import type { ChartTraceEvent, TradeRow } from '../api/types'

export interface ChartSelection {
  runId: string
  sequenceId: number | null
  instrumentId: string | null
  entryTs: number | null
  exitTs: number | null
}

let state: ChartSelection | null = null
const listeners = new Set<() => void>()

function epoch(value: string | number | null | undefined): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value !== 'string' || !value) return null
  const millis = Date.parse(value)
  return Number.isFinite(millis) ? millis / 1_000 : null
}

function publish(next: ChartSelection | null): void {
  state = next
  listeners.forEach((listener) => listener())
}

export function selectTradeRow(runId: string, trade: TradeRow): void {
  publish({
    runId,
    sequenceId: null,
    instrumentId: typeof trade.instrument_id === 'string' ? trade.instrument_id : null,
    entryTs: epoch(trade.entry_ts),
    exitTs: epoch(trade.exit_ts),
  })
}

function isDescendantOf(
  event: ChartTraceEvent,
  ancestorSequenceId: number,
  bySequence: ReadonlyMap<number, ChartTraceEvent>,
): boolean {
  let parent = event.parent_sequence_id
  const visited = new Set<number>()
  while (parent !== null && !visited.has(parent)) {
    if (parent === ancestorSequenceId) return true
    visited.add(parent)
    parent = bySequence.get(parent)?.parent_sequence_id ?? null
  }
  return false
}

export function matchingTradeTrace(
  event: ChartTraceEvent,
  trace: ChartTraceEvent[],
): ChartTraceEvent | null {
  if (event.event_type === 'trade') return event
  const bySequence = new Map(trace.map((candidate) => [candidate.sequence_id, candidate]))
  const fills =
    event.event_type === 'fill'
      ? [event]
      : trace.filter(
          (candidate) =>
            candidate.event_type === 'fill' &&
            candidate.instrument_id === event.instrument_id &&
            isDescendantOf(candidate, event.sequence_id, bySequence),
        )
  const trades = trace.filter(
    (candidate) =>
      candidate.event_type === 'trade' && candidate.instrument_id === event.instrument_id,
  )
  for (const fill of fills) {
    const direct = trades.find((trade) => trade.parent_sequence_id === fill.sequence_id)
    if (direct) return direct
    const timestampMatch = trades.find(
      (trade) => sameTime(trade.entry_ts, fill.ts) || sameTime(trade.exit_ts, fill.ts),
    )
    if (timestampMatch) return timestampMatch
  }
  return null
}

export function selectTraceEvent(
  runId: string,
  event: ChartTraceEvent,
  trace: ChartTraceEvent[] = [],
): void {
  const trade = matchingTradeTrace(event, trace)
  publish({
    runId,
    sequenceId: event.sequence_id,
    instrumentId: event.instrument_id,
    entryTs: trade?.entry_ts ?? event.entry_ts,
    exitTs: trade?.exit_ts ?? event.exit_ts,
  })
}

export function clearChartSelection(): void {
  publish(null)
}

export function getChartSelection(): ChartSelection | null {
  return state
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useChartSelection(): ChartSelection | null {
  return useSyncExternalStore(subscribe, getChartSelection, getChartSelection)
}

function sameTime(left: number | null, right: number | null): boolean {
  return left !== null && right !== null && Math.abs(left - right) < 0.001
}

export function selectionMatchesTrade(
  selection: ChartSelection | null,
  runId: string,
  trade: TradeRow,
): boolean {
  if (!selection || selection.runId !== runId) return false
  const instrument = typeof trade.instrument_id === 'string' ? trade.instrument_id : null
  return (
    selection.instrumentId === instrument &&
    sameTime(selection.entryTs, epoch(trade.entry_ts)) &&
    sameTime(selection.exitTs, epoch(trade.exit_ts))
  )
}

export function matchingTraceSequence(
  selection: ChartSelection | null,
  runId: string,
  trace: ChartTraceEvent[],
): number | null {
  if (!selection || selection.runId !== runId) return null
  if (
    selection.sequenceId !== null &&
    trace.some((event) => event.sequence_id === selection.sequenceId)
  ) {
    return selection.sequenceId
  }
  const match = trace.find(
    (event) =>
      event.event_type === 'trade' &&
      event.instrument_id === selection.instrumentId &&
      sameTime(event.entry_ts, selection.entryTs) &&
      sameTime(event.exit_ts, selection.exitTs),
  )
  return match?.sequence_id ?? null
}
