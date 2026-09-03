// What the toolbar asks of the price chart (artboard 1-Terminal): series type, crosshair, grid and
// a zoom step. A tiny external store like `chartHover` so the toolbar never imports the chart.

import { useSyncExternalStore } from 'react'

export type ChartType = 'candles' | 'bars' | 'line'

export interface ChartControls {
  type: ChartType
  crosshair: boolean
  grid: boolean
  /** Zoom steps away from fit-to-content; each step scales bar spacing by ZOOM_FACTOR. */
  zoom: number
}

export const ZOOM_FACTOR = 1.25
export const ZOOM_LIMIT = 6

const DEFAULT: ChartControls = { type: 'candles', crosshair: true, grid: true, zoom: 0 }
let state: ChartControls = DEFAULT
const listeners = new Set<() => void>()

export function getChartControls(): ChartControls {
  return state
}

export function setChartControls(patch: Partial<ChartControls>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

export function resetChartControls(): void {
  setChartControls(DEFAULT)
}

/** One zoom step in or out, clamped so the chart can never collapse or blow up. */
export function zoomStep(zoom: number, direction: 1 | -1): number {
  return Math.max(-ZOOM_LIMIT, Math.min(ZOOM_LIMIT, zoom + direction))
}

export function barSpacingFor(base: number, zoom: number): number {
  if (!Number.isFinite(base) || base <= 0) throw new Error(`chart zoom: invalid base spacing ${base}`)
  return base * ZOOM_FACTOR ** zoom
}

export function useChartControls(): ChartControls {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => state,
  )
}
