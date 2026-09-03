// What the price chart is showing right now, for the status bar: the hovered bar's OHLC and
// how many bars are loaded. A tiny external store so the chart never imports the shell.

import { useSyncExternalStore } from 'react'

import type { Candle } from '../api/types'

export interface ChartHover {
  bar: Candle | null
  barsLoaded: number
}

let state: ChartHover = { bar: null, barsLoaded: 0 }
const listeners = new Set<() => void>()

export function setChartHover(patch: Partial<ChartHover>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

export function useChartHover(): ChartHover {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => state,
  )
}
