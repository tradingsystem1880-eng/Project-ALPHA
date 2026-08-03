import type { components } from '../api/generated'
import type { MlExperimentPage, MlExperimentSummary, MlTearSheetProjection } from '../api/types'

type Schema = components['schemas']

export type { MlTearSheetProjection }
export type MlExperimentSummaryProjection = MlExperimentSummary
export type MlFoldDiagnosticProjection = Schema['MlFoldDiagnostic']

export function mlExperimentPlaceholderLabel(
  experiments: MlExperimentPage | null,
  error: string | null,
): string | null {
  if (error) return 'EXPERIMENT QUERY FAILED'
  if (experiments === null) return 'LOADING EXPERIMENTS…'
  return experiments.items.length === 0 ? 'NO VALIDATED EXPERIMENT' : null
}

export interface ScorePlotModel {
  min: number
  max: number
  positions: {
    q05: number
    q25: number
    q50: number
    q75: number
    q95: number
    mean: number
  }
}

export interface TrainingCurve {
  label: string
  values: (number | null)[]
}

export interface TrainingHistoryModel {
  iterations: number[]
  curves: TrainingCurve[]
}

export interface FoldSegment {
  fold: number
  train: readonly [number, number]
  validation: readonly [number, number]
  test: readonly [number, number]
}

export interface FoldTimelineModel {
  start: number
  end: number
  segments: FoldSegment[]
}

function finiteTimestamp(value: string): number {
  const timestamp = Date.parse(value) / 1_000
  if (!Number.isFinite(timestamp)) throw new Error(`invalid ML diagnostic timestamp: ${value}`)
  return timestamp
}

export function buildScorePlot(
  score: NonNullable<MlTearSheetProjection['score_distribution']>,
): ScorePlotModel {
  const span = score.max - score.min
  const position = (value: number): number => {
    if (span === 0) return 50
    return Math.max(0, Math.min(100, ((value - score.min) / span) * 100))
  }
  return {
    min: score.min,
    max: score.max,
    positions: {
      q05: position(score.q05),
      q25: position(score.q25),
      q50: position(score.q50),
      q75: position(score.q75),
      q95: position(score.q95),
      mean: position(score.mean),
    },
  }
}

export function buildTrainingHistory(fold: MlFoldDiagnosticProjection): TrainingHistoryModel {
  const raw = Object.entries(fold.training_history)
    .sort(([left], [right]) => left.localeCompare(right))
    .flatMap(([dataset, metrics]) =>
      Object.entries(metrics)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([metric, values]) => ({ label: `${dataset} · ${metric}`, values })),
    )
  const length = Math.max(0, ...raw.map((curve) => curve.values.length))
  return {
    iterations: Array.from({ length }, (_, index) => index + 1),
    curves: raw.map((curve) => ({
      label: curve.label,
      values: Array.from({ length }, (_, index) => curve.values[index] ?? null),
    })),
  }
}

export function buildFoldTimeline(folds: MlFoldDiagnosticProjection[]): FoldTimelineModel | null {
  if (folds.length === 0) return null
  const segments = folds.map((fold) => ({
    fold: fold.fold,
    train: [
      finiteTimestamp(fold.boundaries.train_start),
      finiteTimestamp(fold.boundaries.train_end),
    ] as const,
    validation: [
      finiteTimestamp(fold.boundaries.validation_start),
      finiteTimestamp(fold.boundaries.validation_end),
    ] as const,
    test: [
      finiteTimestamp(fold.boundaries.test_start),
      finiteTimestamp(fold.boundaries.test_end),
    ] as const,
  }))
  const values = segments.flatMap((segment) => [
    ...segment.train,
    ...segment.validation,
    ...segment.test,
  ])
  return { start: Math.min(...values), end: Math.max(...values), segments }
}

export function isoToEpochSeconds(values: string[]): number[] {
  return values.map(finiteTimestamp)
}
