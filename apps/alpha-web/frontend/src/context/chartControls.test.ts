import { beforeEach, describe, expect, it } from 'vitest'

import { ZOOM_LIMIT, barSpacingFor, getChartControls, resetChartControls, setChartControls, zoomStep } from './chartControls'

describe('chartControls', () => {
  beforeEach(() => resetChartControls())

  it('starts as candles with crosshair and grid on at fit zoom', () => {
    expect(getChartControls()).toEqual({ type: 'candles', crosshair: true, grid: true, zoom: 0 })
  })

  it('patches one field at a time', () => {
    setChartControls({ type: 'line' })
    setChartControls({ grid: false })
    expect(getChartControls()).toMatchObject({ type: 'line', grid: false, crosshair: true })
  })

  it('clamps zoom steps and scales bar spacing geometrically', () => {
    expect(zoomStep(0, 1)).toBe(1)
    expect(zoomStep(ZOOM_LIMIT, 1)).toBe(ZOOM_LIMIT)
    expect(zoomStep(-ZOOM_LIMIT, -1)).toBe(-ZOOM_LIMIT)
    expect(barSpacingFor(6, 0)).toBe(6)
    expect(barSpacingFor(6, 1)).toBeCloseTo(7.5)
    expect(barSpacingFor(6, -1)).toBeCloseTo(4.8)
    expect(() => barSpacingFor(0, 1)).toThrow(/invalid base spacing/)
  })
})
