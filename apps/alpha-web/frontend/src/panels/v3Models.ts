import type {
  ChartAnnotation,
  ChartBundle,
  ChartIndicator,
  DevelopmentStage,
  ForecastPaths,
  NativeCalendarReturn,
  ProjectDetail,
  StageState,
} from '../api/types'

export interface EvidenceMarker {
  id: string
  sequenceId: number
  kind: 'decision' | 'fill' | 'entry' | 'exit'
  barTs: number
  exactTs: number
  label: string
  tone: 'selection' | 'positive' | 'negative' | 'neutral'
}

export interface DecisionEvidence {
  indicators: ChartIndicator[]
  annotations: ChartAnnotation[]
}

export function evidenceForDecision(
  bundle: ChartBundle,
  sequenceId: number,
): DecisionEvidence {
  const isDecision = bundle.trace.some(
    (event) => event.sequence_id === sequenceId && event.event_type === 'decision',
  )
  if (!isDecision) return { indicators: [], annotations: [] }
  return {
    indicators: bundle.indicators.filter((row) => row.decision_sequence_id === sequenceId),
    annotations: bundle.annotations.filter((row) => row.decision_sequence_id === sequenceId),
  }
}

function nearestBarAtOrBefore(ts: number, bars: number[]): number | null {
  const first = bars[0]
  const last = bars.at(-1)
  // ALPHA's current market-data contract is daily UTC. A close-time decision belongs to the
  // midnight-stamped candle on the same UTC day, but no event may escape the visible day range.
  if (first === undefined || last === undefined || ts < first || ts >= last + 24 * 60 * 60) {
    return null
  }
  let match: number | null = null
  for (const barTs of bars) {
    if (barTs > ts) break
    match = barTs
  }
  return match
}

export function buildEvidenceMarkers(bundle: ChartBundle, barTimestamps: number[]): EvidenceMarker[] {
  if (bundle.trace_status !== 'available' || barTimestamps.length === 0) return []
  const markers: EvidenceMarker[] = []
  for (const row of bundle.trace) {
    if (row.event_type === 'decision') {
      const barTs = nearestBarAtOrBefore(row.ts, barTimestamps)
      if (barTs !== null) {
        markers.push({
          id: `${row.sequence_id}:decision`,
          sequenceId: row.sequence_id,
          kind: 'decision',
          barTs,
          exactTs: row.ts,
          label: row.signal === null ? 'D' : `D ${row.signal > 0 ? '+' : row.signal < 0 ? '−' : '0'}`,
          tone: 'selection',
        })
      }
      continue
    }
    if (row.event_type === 'fill') {
      const barTs = nearestBarAtOrBefore(row.ts, barTimestamps)
      if (barTs !== null) {
        markers.push({
          id: `${row.sequence_id}:fill`,
          sequenceId: row.sequence_id,
          kind: 'fill',
          barTs,
          exactTs: row.ts,
          label: row.side === 'SELL' ? 'F SELL' : 'F BUY',
          tone: row.side === 'SELL' ? 'negative' : 'positive',
        })
      }
      continue
    }
    if (row.event_type === 'trade' && row.entry_ts !== null && row.exit_ts !== null) {
      const entryBar = nearestBarAtOrBefore(row.entry_ts, barTimestamps)
      const exitBar = nearestBarAtOrBefore(row.exit_ts, barTimestamps)
      if (entryBar !== null) {
        markers.push({
          id: `${row.sequence_id}:entry`,
          sequenceId: row.sequence_id,
          kind: 'entry',
          barTs: entryBar,
          exactTs: row.entry_ts,
          label: 'ENTRY',
          tone: 'neutral',
        })
      }
      if (exitBar !== null) {
        markers.push({
          id: `${row.sequence_id}:exit`,
          sequenceId: row.sequence_id,
          kind: 'exit',
          barTs: exitBar,
          exactTs: row.exit_ts,
          label: 'EXIT',
          tone:
            row.realized_return === null
              ? 'neutral'
              : row.realized_return >= 0
                ? 'positive'
                : 'negative',
        })
      }
    }
  }
  return markers.sort((left, right) => left.barTs - right.barTs || left.id.localeCompare(right.id))
}

export function terminalReturns(paths: ForecastPaths, originClose: number): Array<{ sample: number; value: number }> {
  if (!(originClose > 0)) return []
  return paths.samples.flatMap((path) => {
    const terminal = path.closes.at(-1)
    return terminal === undefined ? [] : [{ sample: path.sample, value: terminal / originClose - 1 }]
  })
}

export interface CalendarRow {
  year: number
  months: Array<number | null>
}

export function buildCalendarRows(values: NativeCalendarReturn[]): CalendarRow[] {
  const years = new Map<number, Array<number | null>>()
  for (const value of values) {
    const row = years.get(value.year) ?? Array<number | null>(12).fill(null)
    if (value.month >= 1 && value.month <= 12) row[value.month - 1] = value.return_value
    years.set(value.year, row)
  }
  return [...years.entries()]
    .sort(([left], [right]) => left - right)
    .map(([year, months]) => ({ year, months }))
}

export const DEVELOPMENT_STAGES: ReadonlyArray<{ id: DevelopmentStage; label: string }> = [
  { id: 'hypothesis', label: 'Hypothesis & falsification' },
  { id: 'data', label: 'Data, universe & sealed holdout' },
  { id: 'strategy', label: 'Immutable strategy version' },
  { id: 'baseline', label: 'Baseline discovery' },
  { id: 'oos', label: 'Inner OOS / walk-forward' },
  { id: 'robustness', label: 'Nulls & robustness' },
  { id: 'optimization', label: 'Parameter research' },
  { id: 'portfolio', label: 'Portfolio / cross-asset' },
  { id: 'candidate', label: 'Candidate freeze' },
  { id: 'holdout', label: 'Locked final holdout' },
  { id: 'paper', label: 'Sandbox paper' },
  { id: 'decision', label: 'Accept, reject or revise' },
  { id: 'kronos', label: 'Kronos evaluation' },
  { id: 'ml', label: 'Qlib ML experiment' },
]

export interface ProjectStageRow {
  id: DevelopmentStage
  label: string
  state: StageState
  runId: string | null
  linkId: string | null
}

export function projectStageRows(project: ProjectDetail | null): ProjectStageRow[] {
  const experimentId = project?.current_experiment_id ?? null
  const links = (project?.stage_run_links ?? []).filter(
    (candidate) => candidate.experiment_id === experimentId,
  )
  const states = (project?.stage_states ?? []).filter(
    (candidate) => candidate.experiment_id === experimentId,
  )
  return DEVELOPMENT_STAGES.map((stage) => {
    const link = links
      .filter((candidate) => candidate.stage === stage.id)
      .sort((left, right) => right.linked_at.localeCompare(left.linked_at))[0]
    const state = states.find((candidate) => candidate.stage === stage.id)
    return {
      ...stage,
      state: state?.state ?? link?.state ?? 'not_started',
      runId: link?.run_id ?? null,
      linkId: link?.link_id ?? null,
    }
  })
}
