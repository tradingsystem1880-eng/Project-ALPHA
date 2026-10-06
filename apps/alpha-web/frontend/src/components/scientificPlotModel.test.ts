import { describe, expect, it } from 'vitest'
import { plotBounds, scientificValues, nearestTimestamp, seriesSummary, trailingWindow, dateWindow, recordedCsv } from './scientificPlotModel'
describe('scientific plot values', () => {
  it('preserves backend null gaps instead of connecting unavailable values', () => {
    const points = [{ time: 10, value: 2 }, { time: 20, value: null }, { time: 30, value: 4 }]
    expect(scientificValues(points).x).toEqual([10000, 20000, 30000])
    expect(Number.isNaN(scientificValues(points).y[1])).toBe(true)
    expect(points[1].value).toBeNull()
  })
  it('fits finite values without mistaking zero or negative values for missing', () => {
    expect(plotBounds([{ time: 10, value: -2 }, { time: 20, value: 0 }, { time: 30, value: null }])).toEqual({ x: [10000, 30000], y: [-2.16, 0.16] })
    expect(plotBounds([{ time: 10, value: 2 }, { time: 10, value: 3 }]).x).toEqual([10000, 11000])
    expect(plotBounds([])).toEqual({ x: [0, 1], y: [0, 1] })
  })
  it('binary searches timestamps and clears outside the source coverage', () => {
    expect(nearestTimestamp([10, 20, 30], 19)).toBe(20)
    expect(nearestTimestamp([10, 20, 30], 5)).toBeNull()
    expect(nearestTimestamp([], 20)).toBeNull()
  })
})

describe('chart exploration uses only returned evidence', () => {
  it('summarizes observed zeros/negatives and preserves missing last values', () => {
    expect(seriesSummary([{ time: 10, value: -2 }, { time: 20, value: 0 }, { time: 30, value: null }])).toEqual({ total: 3, missing: 1, first: 10, last: 30, minimum: -2, maximum: 0, latest: null })
    expect(seriesSummary([])).toEqual({ total: 0, missing: 0, first: null, last: null, minimum: null, maximum: null, latest: null })
  })
  it('anchors trailing windows to the last returned timestamp and clips to coverage', () => {
    expect(trailingWindow([{ time: 1, value: null }, { time: 864001, value: 2 }], 3)).toEqual([604801, 864001])
    expect(trailingWindow([{ time: 1, value: 0 }, { time: 20, value: 2 }], 30)).toEqual([1, 20])
    expect(trailingWindow([], 30)).toBeNull()
  })
  it('interprets dates as inclusive UTC days and rejects invalid/outside windows', () => {
    const points = [{ time: Date.parse('2024-01-01T12:00:00Z') / 1000, value: 2 }, { time: Date.parse('2024-01-03T12:00:00Z') / 1000, value: null }]
    expect(dateWindow(points, '2024-01-02', '2024-01-03')).toEqual([Date.parse('2024-01-02T00:00:00Z') / 1000, points[1].time])
    expect(dateWindow(points, '2024-01-03', '2024-01-02')).toBeNull()
    expect(dateWindow(points, '2024-02-30', '2024-03-01')).toBeNull()
    expect(dateWindow(points, '2025-01-01', '2025-01-02')).toBeNull()
    expect(dateWindow([{ time: Date.parse('2024-01-01T00:00:00Z') / 1000, value: 2 }, { time: Date.parse('2024-01-03T00:00:00Z') / 1000, value: 3 }], '2024-01-03', '2024-01-03')).toBeNull()
  })
  it('exports exact values including zero, negative and null, with escaped labels', () => {
    expect(recordedCsv([{ time: 0, value: -2 }, { time: 1, value: null }, { time: 2, value: 0 }], 'Equity, "USD"')).toBe('timestamp_utc,"Equity, ""USD"""\n1970-01-01T00:00:00.000Z,-2\n1970-01-01T00:00:01.000Z,\n1970-01-01T00:00:02.000Z,0\n')
  })
})
