import { describe, expect, it } from 'vitest'

import {
  buildFoldTimeline,
  buildScorePlot,
  buildTrainingHistory,
  isoToEpochSeconds,
  type MlFoldDiagnosticProjection,
} from './mlTearsheetModel'

function fold(overrides: Partial<MlFoldDiagnosticProjection> = {}): MlFoldDiagnosticProjection {
  return {
    fold: 0,
    fit_count: 1,
    train_rows: 10_000,
    validation_rows: 2_400,
    test_rows: 2_500,
    best_iteration: 42,
    model_hash: '1'.repeat(64),
    normalization: {
      method: 'train_only_median_then_zscore',
      statistics_hash: '2'.repeat(64),
      all_missing_train_features: 0,
    },
    training_history: {
      valid: { l2: [0.4, 0.3] },
      train: { l2: [0.3, 0.2, 0.1] },
    },
    boundaries: {
      train_start: '2020-01-01T00:00:00Z',
      train_end: '2021-12-31T00:00:00Z',
      validation_start: '2022-01-01T00:00:00Z',
      validation_end: '2022-06-30T00:00:00Z',
      test_start: '2022-07-01T00:00:00Z',
      test_end: '2022-12-31T00:00:00Z',
    },
    ...overrides,
  }
}

describe('ML tear-sheet display models', () => {
  it('maps only artifact score quantiles onto the declared min/max range', () => {
    const model = buildScorePlot({
      min: -1,
      max: 1,
      mean: 0.1,
      std: 0.5,
      q05: -0.8,
      q25: -0.25,
      q50: 0,
      q75: 0.25,
      q95: 0.8,
    })

    expect(model.positions.q05).toBeCloseTo(10)
    expect(model.positions.q25).toBeCloseTo(37.5)
    expect(model.positions.q50).toBeCloseTo(50)
    expect(model.positions.q75).toBeCloseTo(62.5)
    expect(model.positions.q95).toBeCloseTo(90)
    expect(model.positions.mean).toBeCloseTo(55)
    expect(buildScorePlot({
      min: 2,
      max: 2,
      mean: 2,
      std: 0,
      q05: 2,
      q25: 2,
      q50: 2,
      q75: 2,
      q95: 2,
    }).positions.q50).toBe(50)
  })

  it('orders training curves deterministically and pads no invented numeric values', () => {
    const model = buildTrainingHistory(fold())

    expect(model.iterations).toEqual([1, 2, 3])
    expect(model.curves).toEqual([
      { label: 'train · l2', values: [0.3, 0.2, 0.1] },
      { label: 'valid · l2', values: [0.4, 0.3, null] },
    ])
  })

  it('preserves exact train, validation, and test boundaries across folds', () => {
    const second = fold({
      fold: 1,
      boundaries: {
        train_start: '2020-06-01T00:00:00Z',
        train_end: '2022-06-30T00:00:00Z',
        validation_start: '2022-07-01T00:00:00Z',
        validation_end: '2022-12-31T00:00:00Z',
        test_start: '2023-01-01T00:00:00Z',
        test_end: '2023-06-30T00:00:00Z',
      },
    })
    const model = buildFoldTimeline([fold(), second])

    expect(model?.segments.map((segment) => segment.fold)).toEqual([0, 1])
    expect(model?.start).toBe(Date.parse('2020-01-01T00:00:00Z') / 1_000)
    expect(model?.end).toBe(Date.parse('2023-06-30T00:00:00Z') / 1_000)
    expect(buildFoldTimeline([])).toBeNull()
  })

  it('fails loud on an invalid diagnostic timestamp', () => {
    expect(() => isoToEpochSeconds(['not-a-timestamp'])).toThrow('invalid ML diagnostic timestamp')
  })
})
